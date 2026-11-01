"""Explicitly started local service. The GUI owns no acquisition resources."""
import argparse
import hashlib
from pathlib import Path
import socketserver
import threading
import time
from .backend import RunController
from .core.schema import require
from .evidence import loads, dumps
from .ipc import envelope, receive, send
from .presentation import View, METRICS
from .scenarios import Scenario
from .storage import RunReader


class Service:
    def __init__(self):
        self.lock = threading.RLock()
        self.view_lock = threading.Lock()
        self.controller = self.worker = self.reader = self.view = None
        self.error = None
        self.acks = {}
        self.sequence = 0
        self.cached = self.cached_view = None
        self.next_refresh = 0

    def _execute(self, controller):
        try:
            controller.execute()
        except Exception as exc:
            with self.lock:
                self.error = str(exc)

    def state(self):
        with self.lock:
            c = self.controller
            run = self.reader.run if self.reader else c.run if c else None
            active = bool(self.worker and self.worker.is_alive())
            return dict(run_id=run.run_id if run else c.run_id if c else None,
                execution_status='failed' if self.error else run.execution_status if run else 'draft',
                evaluation_status=run.evaluation_status if run else 'not_evaluated',
                integrity_status=run.integrity_status if run and not self.error else 'unknown',
                reason=self.error or (run.stop_reason if run else None),
                can_start=not active, can_stop=bool(active and c.active and not c.stop.is_set()),
                out=str(self.view.root) if self.view else None,
                issues=list(self.reader.issues) if self.reader else [])

    def command(self, req):
        kind, p, ident = req['message_type'], req['payload'], req['id']
        if kind in ('hello','get_status','snapshot_request'):
            require(not p, 'Consulta deve ter payload vazio')
            if kind == 'hello':
                return envelope('hello_ack', {'service':'FO-IMU', 'max_hz':5}, ident)
            if kind == 'get_status':
                return envelope('run_state', self.state(), ident)
            return envelope('snapshot', self.snapshot(), ident)
        fields = {'start_run': {'command_id','scenario','out'}, 'stop_run': {'command_id','run_id','reason'},
                  'open_run': {'command_id','path'}}
        require(kind in fields and set(p) == fields[kind], 'Comando ou campos inválidos')
        cid = p['command_id']
        require(type(cid) is str and 0 < len(cid) <= 128, 'command_id inválido')
        body = dumps([kind,p])
        require(len(body) <= 65536, 'Comando excede 64 KiB')
        signature = hashlib.sha256(body).digest()
        with self.lock:
            if cid in self.acks:
                previous, ack = self.acks[cid]
                require(signature == previous, 'Mesmo command_id com outro conteúdo')
                return envelope('command_ack', dict(ack, duplicate=True), ident)
            require(len(self.acks) < 256, 'Limite de comandos da sessão atingido')
            if kind == 'stop_run':
                c = self.controller
                require(c is not None and c.run_id == p['run_id'], 'Run alvo incorreta')
                ack = c.request_stop(cid, p['reason'])
            else:
                require(self.state()['can_start'], 'Existe Run ativa')
                path = p['out' if kind == 'start_run' else 'path']
                require(type(path) is str and 0 < len(path.strip()) <= 4096, 'Caminho inválido')
                root = Path(path).resolve()
                if kind == 'start_run':
                    require(not root.exists(), 'Diretório de saída já existe')
                    s = Scenario.from_dict(p['scenario'])
                    require(s.transport.kind == 'virtual' and s.resource_limits.max_memory_bytes is None, 'Requer transporte virtual sem limite de RSS')
                    c = RunController(s, root)
                    self.controller, self.reader, self.error = c, None, None
                    self.view = View(root, s.rate.value)
                    self.worker = threading.Thread(target=self._execute, args=(c,), name='controller', daemon=False)
                    self.worker.start()
                    run_id = c.run_id
                else:
                    reader = RunReader(root, strict=False)
                    self.reader, self.controller, self.error = reader, None, None
                    self.view = View(root, reader.scenario.rate.value,
                                     None if reader.run.integrity_status == 'complete' else reader.confirmed)
                    run_id = reader.run.run_id
                ack = dict(accepted=True, run_id=run_id, out=str(root))
            ack = dict(ack, command_id=cid, operation=kind, duplicate=False)
            self.acks[cid] = signature, ack
            return envelope('command_ack', ack, ident)

    def snapshot(self):
        with self.view_lock:
            with self.lock:
                view, c = self.view, self.controller
                state = self.state()
            if self.cached and view is self.cached_view and time.monotonic() < self.next_refresh:
                return self.cached
            parts = [envelope('run_state', state)]
            if view:
                try:
                    parts.extend(self._parts(view, c, state))
                except (ValueError, KeyError, OSError, TypeError) as exc:
                    parts.append(envelope('error', dict(code='presentation', detail=str(exc))))
            self.sequence += 1
            self.cached = dict(sequence=self.sequence, produced_monotonic_ns=time.monotonic_ns(), messages=parts)
            self.cached_view = view
            self.next_refresh = time.monotonic() + .2
            return self.cached

    def _parts(self, view, controller, state):
        view.advance()
        health = {}
        if controller:
            for name, attr in [('rx','rx'), ('writer','writes')]:
                channel = getattr(controller, attr, None)
                if channel:
                    health[name] = channel.snapshot()
            health['workers'] = {k: t.is_alive() for k,t in controller.threads.copy().items()}
        metrics = dict(view.metrics)
        origin = 'Prefixo de registros observados'
        parts = []
        if state['can_start']:
            verified = state['integrity_status'] == 'complete'
            metrics_path = view.root/'diagnostics/metrics.json'
            if verified and metrics_path.is_file():
                final = loads(metrics_path.read_bytes())['metrics']
                metrics = {k: final.get(k) for k in METRICS}
                origin = 'Métricas finais da Run'
            pipeline_path = view.root/'system/pipeline.json'
            if verified and pipeline_path.is_file():
                health = loads(pipeline_path.read_bytes())
            report_path = view.root/'report.md'
            report = None
            if report_path.is_file():
                with report_path.open(encoding='utf-8') as f:
                    report = f.read(262144)
            truth = None
            path = view.root/'truth/summary.jsonl'
            if verified and path.is_file():
                with path.open('rb') as f:
                    truth = loads(f.readline(65536))
            parts.append(envelope('run_finished', dict(report=report, truth=truth)))
        health['presentation_backlog_bytes'] = view.backlog
        parts.extend([envelope('metrics_snapshot', dict(values=metrics, origin=origin)),
                      envelope('signal_snapshot', dict(rows=list(view.frames), rate_hz=view.rate, clock_id='experiment', meaning='host_receive')),
                      envelope('event_snapshot', dict(events=list(view.events))),
                      envelope('pipeline_health', health)])
        return parts


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        ident = None
        self.request.settimeout(5)
        try:
            req = receive(self.request)
            ident = req['id']
            reply = self.server.service.command(req)
            send(self.request, reply)
        except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
            try:
                send(self.request, envelope('error', dict(code='invalid_request', detail=str(exc)), ident))
            except OSError:
                pass


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self, port):
        self.service = Service()
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1', port), Handler)

    def process_request(self, sock, address):
        if not self.slots.acquire(False):
            self.shutdown_request(sock)
            return
        try:
            super().process_request(sock, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, sock, address):
        try:
            super().process_request_thread(sock, address)
        finally:
            self.slots.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Serviço local da bancada FO-IMU')
    parser.add_argument('--port', default=8877, type=int)
    with Server(parser.parse_args().port) as server:
        print('READY', server.server_address[1], flush=True)
        try:
            server.serve_forever(.2)
        except KeyboardInterrupt:
            pass
