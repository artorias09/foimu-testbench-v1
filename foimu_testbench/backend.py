"""Headless lifecycle and three bounded worker stages. GUI-independent."""
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Condition, Event as Flag, Lock, Thread
from typing import Literal
import queue
import time
import uuid
from .core import ClockDefinition, Event, TimePoint
from .core.schema import Model, require
from .core.contracts import TRANSITIONS
from .scenarios import Scenario
from .provenance import new_run, collect_identity
from .evidence import ObservedChunk, WriteBatch, WriteItem, dumps, record_item
from .processing import Processing
from .storage import RunWriter, atomic_json


@dataclass(frozen=True, kw_only=True)
class BackendOptions(Model):
    rx_bytes: int = 8*1024*1024
    writer_bytes: int = 8*1024*1024
    queue_items: int = 16384
    barrier_every: int = 128
    checkpoint_every: int = 128
    worker_timeout_ns: int = 5_000_000_000
    shutdown_timeout_ns: int = 5_000_000_000
    record_emissions: bool = True
    scheduling: Literal['virtual_barriers','unpaced_stress'] = 'virtual_barriers'

    def validate(self):
        require(all(x>0 for x in (self.rx_bytes,self.writer_bytes,self.queue_items,self.barrier_every,
            self.checkpoint_every,self.worker_timeout_ns,self.shutdown_timeout_ns)), 'Limites devem ser positivos')


class Overload(RuntimeError):
    def __init__(self, queue_name, stats, rejected_bytes):
        super().__init__('Fila obrigatória saturada: '+queue_name)
        self.details = dict(queue=queue_name, stats=stats, rejected_bytes=rejected_bytes,
                            reason='Limite de bytes ou itens; nenhum descarte autorizado')


class BoundedChannel:
    def __init__(self, name, max_bytes, max_items):
        self.name, self.max_bytes, self.max_items = name,max_bytes,max_items
        self.cv = Condition()
        self.items = deque()
        self.closed = False
        self.pending = self.bytes = self.peak_bytes = self.peak_items = self.total_items = self.total_bytes = 0

    def put(self, value):
        weight = value.weight
        with self.cv:
            if self.closed:
                raise RuntimeError('Fila fechada: '+self.name)
            if self.bytes+weight>self.max_bytes or len(self.items)>=self.max_items:
                raise Overload(self.name,self._snapshot(),weight)
            self.items.append(value)
            self.bytes += weight
            self.pending += 1
            self.total_items += 1
            self.total_bytes += weight
            self.peak_bytes = max(self.bytes,self.peak_bytes)
            self.peak_items = max(len(self.items),self.peak_items)
            self.cv.notify_all()

    def get(self, timeout=.02):
        with self.cv:
            if not self.items and not self.closed:
                self.cv.wait(timeout)
            if not self.items:
                if self.closed: return None
                raise queue.Empty
            value = self.items.popleft()
            self.bytes -= value.weight
            return value

    def done(self):
        with self.cv:
            self.pending -= 1
            self.cv.notify_all()

    def close(self):
        with self.cv:
            self.closed = True
            self.cv.notify_all()

    def _snapshot(self):
        return dict(items=len(self.items),bytes=self.bytes,peak_items=self.peak_items,
                    peak_bytes=self.peak_bytes,enqueued_items=self.total_items,enqueued_bytes=self.total_bytes,
                    pending=self.pending,limit_bytes=self.max_bytes,limit_items=self.max_items)

    def snapshot(self):
        with self.cv:
            return self._snapshot()


class RunController:
    def __init__(self, scenario, out, *, source_root=None, options=None, run_id=None,
                 source_factory=None, writer_hook=None, parent_run_id=None, operation='acquisition', derivation=None):
        # The only config crossing threads is canonical bytes; callers retain no live references.
        self.scenario_json = scenario.to_json().encode()
        self.options_json = (options or BackendOptions()).to_json().encode()
        self.out = Path(out)
        self.source_root = Path(source_root or Path(__file__).resolve().parents[1])
        self.run_id = run_id or str(uuid.uuid4())
        self.source_factory = source_factory
        self.writer_hook = writer_hook
        self.parent_run_id, self.operation = parent_run_id,operation
        self.derivation = None if derivation is None else dumps(derivation)
        self.stop = Flag()
        self.lock = Lock()
        self.failure_by_worker = {}
        self.progress = {}
        self.commands = {}
        self.active = self.used = False
        self.stop_command = None
        self.control_seq = 0
        self.logged_commands = set()
        self.run = None
        self.writer = None
        self.processing = None
        self.threads = {}

    def request_stop(self, command_id, reason):
        require(type(command_id) is str and bool(command_id.strip()),'command_id obrigatório')
        require(type(reason) is str and bool(reason.strip()),'Motivo obrigatório')
        with self.lock:
            if command_id in self.commands:
                return dict(self.commands[command_id], duplicate=True)
            ack = dict(command_id=command_id,reason=reason,requested_ns=time.monotonic_ns(),
                       clock_id='host-monotonic',accepted=self.active and self.stop_command is None,
                       duplicate=False)
            if len(self.commands)>=64:
                return dict(ack,accepted=False,result='Limite de 64 comandos')
            self.commands[command_id] = ack
            if ack['accepted']:
                self.stop_command = command_id
                self.stop.set()
            return dict(ack)

    def _beat(self, name):
        with self.lock:
            self.progress[name] = time.monotonic_ns()

    def _failure(self, name, exc):
        with self.lock:
            if name not in self.failure_by_worker:
                self.failure_by_worker[name] = dict(worker=name,error_type=type(exc).__name__,message=str(exc),
                    detected_ns=time.monotonic_ns(),clock_id='host-monotonic',details=getattr(exc,'details',{}))
        self.stop.set()

    def _control(self, kind, payload, *, direct=False):
        event = Event(event_id=f'controller:{self.control_seq}',run_id=self.run_id,producer_id='controller',
            producer_seq=self.control_seq,domain='control',epistemic_status='observed_fact',kind=kind,
            component_path='FO-IMU/Host',time=TimePoint(clock_id='host-monotonic',meaning='control',value=time.monotonic_ns()),
            payload=payload)
        self.control_seq += 1
        batch = WriteBatch((WriteItem('control/actions.jsonl',event.to_json().encode()+b'\n'),))
        if direct: self.writer.append(batch)
        else: self.writes.put(batch)

    def _log_commands(self):
        with self.lock: commands=list(self.commands.values())
        for ack in commands:
            if ack['command_id'] not in self.logged_commands:
                self._control('stop_requested',ack)
                self._control('stop_ack',dict(command_id=ack['command_id'],accepted=ack['accepted']))
                self.logged_commands.add(ack['command_id'])

    def _transition(self, target, reason=None, direct=False):
        old = self.run.execution_status
        self.run = self.run.transition(target,reason)
        self._control('execution_transition',{'from':old,'to':target,'reason':self.run.stop_reason},direct=direct)
        # Controller owns run.json; writer never writes it.
        atomic_json(self.out/'run.json',self.run.to_dict())

    def _barrier(self):
        for channel in (self.rx,self.writes):
            with channel.cv:
                while channel.pending:
                    if self.failure_by_worker:
                        return
                    channel.cv.wait(.02)
                    self._beat('rx')

    def _rx_worker(self):
        from .emission import VirtualSource
        source = None
        offset = seq = ns = 0
        epoch = '0'
        ended = False
        try:
            source = (self.source_factory(self.scenario_json,self.run_id,self.writes.put) if self.source_factory else
                      VirtualSource(self.scenario_json,self.run_id,self.writes.put,record_emissions=self.options.record_emissions))
            self.rx.put(ObservedChunk.make(b'',ns=0,offset=0,seq=seq,kind='epoch'))
            seq += 1
            while not self.stop.is_set():
                reading = source.read()
                self._beat('rx')
                if reading is None: break
                ns = reading.ns
                if reading.kind=='epoch' and seq==1 and reading.epoch=='0' and ns==0:
                    continue  # replay's initial declaration was already emitted
                chunk = ObservedChunk.make(reading.data,ns=ns,offset=offset,seq=seq,kind=reading.kind,
                                           epoch=reading.epoch,origin=reading.origin)
                self.rx.put(chunk)
                offset += len(reading.data)
                epoch = reading.epoch
                seq += 1
                if reading.kind=='end':
                    ended=True
                    break
                if self.options.scheduling=='virtual_barriers' and seq%self.options.barrier_every==0:
                    self._barrier()
            if not ended and not self.failure_by_worker:
                self.rx.put(ObservedChunk.make(b'',ns=ns,offset=offset,seq=seq,kind='end',epoch=epoch))
        except BaseException as exc:
            self._failure('rx',exc)
        finally:
            if source is not None:
                try: source.close()
                except BaseException as exc: self._failure('rx',exc)
            self.rx.close()
            self._beat('rx')

    def _processing_worker(self):
        scenario = Scenario.from_json(self.scenario_json)
        p = Processing(self.run_id,scenario.rate.value,round(scenario.diagnostic_policy.stream_timeout.value*1e9))
        self.processing = p
        try:
            while True:
                try: chunk=self.rx.get()
                except queue.Empty:
                    self._beat('processing');continue
                if chunk is None: break
                try: self.writes.put(p.consume(chunk))
                finally: self.rx.done()
                self._beat('processing')
        except BaseException as exc:
            self._failure('processing',exc)
        finally:
            self._beat('processing')

    def _writer_worker(self):
        failed = False
        try:
            while True:
                try: batch=self.writes.get()
                except queue.Empty:
                    self._beat('writer');continue
                if batch is None: break
                try: self.writer.append(batch)
                finally: self.writes.done()
                self._beat('writer')
        except BaseException as exc:
            failed = True
            self._failure('writer',exc)
        finally:
            try: self.writer.close(checkpoint=not failed)
            except BaseException as exc: self._failure('writer',exc)
            self._beat('writer')

    def _monitor(self):
        now = time.monotonic_ns()
        with self.lock: progress=dict(self.progress)
        for name,thread in self.threads.items():
            if thread.is_alive() and now-progress[name]>=self.options.worker_timeout_ns:
                exc=RuntimeError('worker_progress: prazo sem progresso excedido')
                exc.details=dict(deadline_ns=progress[name]+self.options.worker_timeout_ns,
                                 detection_delay_ns=now-progress[name]-self.options.worker_timeout_ns)
                self._failure(name,exc)

    def execute(self):
        require(not self.used,'Controlador não pode ser reutilizado')
        self.used = True
        scenario = Scenario.from_json(self.scenario_json)
        self.options = BackendOptions.from_json(self.options_json)
        require(scenario.transport.kind=='virtual','P2 executa transporte virtual e replay; TCP v1 permanece disponível')
        require(scenario.resource_limits.max_memory_bytes is None,
                'Limite total de RSS não implementado; configure limites das filas em BackendOptions')
        for action in scenario.scheduled_actions:
            rule=next(r for r in scenario.fault_rules if r.rule_id==action.rule_id)
            require(not action.enabled or rule.kind=='jitter_s' or rule.every>0,'Ação não pode habilitar every=0')
        self.run = new_run(scenario,self.source_root,run_id=self.run_id)
        if self.source_factory is not None or self.writer_hook is not None:
            self.run=replace(self.run,limitations=['Adaptador/hook externo à receita declarativa; implementação fornecida pela API e não serializada'])
        self.run = replace(self.run,clocks=self.run.clocks+[ClockDefinition(clock_id='host-monotonic',kind='monotonic_local')],
                           parent_run_id=self.parent_run_id,operation=self.operation)
        self.writer = RunWriter(self.out,self.run,scenario,checkpoint_every=self.options.checkpoint_every,
                                max_disk_bytes=scenario.resource_limits.max_disk_bytes,hook=None)
        atomic_json(self.out/'backend.resolved.json',self.options.to_dict())
        if self.derivation is not None:
            from .evidence import loads
            atomic_json(self.out/'derivation.json',loads(self.derivation))
        self.rx = BoundedChannel('rx',self.options.rx_bytes,self.options.queue_items)
        self.writes = BoundedChannel('writer',self.options.writer_bytes,self.options.queue_items)
        try:
            for state in ('validated','prepared','armed'):
                self._transition(state,direct=True)
            self.run = replace(self.run,started_at=TimePoint(clock_id='catalog-utc',meaning='catalog',value=time.time_ns()))
            self._transition('running',direct=True)
            self.writer.checkpoint()
            self.writer.hook=self.writer_hook
            with self.lock: self.active=True
            for name,target in (('writer',self._writer_worker),('processing',self._processing_worker),('rx',self._rx_worker)):
                self._beat(name)
                t=Thread(target=target,name='foimu-'+name,daemon=True)
                self.threads[name]=t;t.start()
            stop_at = None
            while self.threads['rx'].is_alive() or self.threads['processing'].is_alive():
                self._monitor()
                self._log_commands()
                if self.stop.is_set():
                    if stop_at is None: stop_at=time.monotonic_ns()
                    if time.monotonic_ns()-stop_at>self.options.shutdown_timeout_ns:
                        self._failure('controller',RuntimeError('Prazo de dreno excedido'))
                        break
                self.threads['rx'].join(.01)
                self.threads['processing'].join(.01)
        except KeyboardInterrupt:
            self.request_stop('keyboard-interrupt','Interrupção pelo operador')
        except BaseException as exc:
            self._failure('controller',exc)
        finally:
            with self.lock: self.active=False
        # Independent join budgets: RX, processing, then writer after input closes.
        # Time spent draining an earlier worker never consumes the next budget.
        for name in ('rx','processing'):
            t=self.threads.get(name)
            if t: t.join(self.options.shutdown_timeout_ns/1e9)
        try:
            self._log_commands()
            reason = ('Falha operacional: '+', '.join(self.failure_by_worker)) if self.failure_by_worker else (
                self.commands[self.stop_command]['reason'] if self.stop_command else 'Condição de término atingida')
            if self.run.execution_status=='running': self._transition('stopping',reason)
            if self.run.execution_status=='stopping': self._transition('finalizing')
        except BaseException as exc:
            self._failure('controller',exc)
        self.writes.close()
        writer_thread=self.threads.get('writer')
        if writer_thread: writer_thread.join(self.options.shutdown_timeout_ns/1e9)
        alive=[name for name,t in self.threads.items() if t.is_alive()]
        if alive: self._failure('controller',RuntimeError('Workers não encerrados: '+', '.join(alive)))
        if not self.threads and not self.writer.closed:
            self.writer.close(checkpoint=False)
        return self._finalize(scenario,alive)

    def _finalize(self, scenario, alive):
        from .validation import evaluate_run, truth_summary
        from .reporting import report_text
        candidate=self.run
        metrics=self.processing.metrics() if self.processing and 'processing' not in alive else {}
        health=dict(schema_version=2,rx=self.rx.snapshot(),writer=self.writes.snapshot(),
                    failures=list(self.failure_by_worker.values()),workers_alive=alive,
                    scheduling=self.options.scheduling,throughput_claim=False,
                    persisted_wire_bytes=self.writer.sizes.get('observed/wire.bin',0),
                    checkpoint_wire_bytes=self.writer.confirmed.get('observed/wire.bin',{}).get('size_bytes',0))
        complete=not self.failure_by_worker and not alive and self.processing is not None and self.processing.ended
        status='completed' if complete else ('aborted' if alive else 'failed')
        if complete and self.stop_command: status='cancelled'
        reason=candidate.stop_reason or ('Condição de término atingida' if complete else 'Falha operacional')
        if not complete: reason='Falha operacional: '+', '.join(self.failure_by_worker)
        previous_status=candidate.execution_status
        if status in TRANSITIONS[previous_status]:
            candidate=candidate.transition(status,reason)
        candidate=replace(candidate,execution_status=status,integrity_status='complete' if complete else 'partial',
                         stop_reason=reason,ended_at=TimePoint(clock_id='catalog-utc',meaning='catalog',value=time.time_ns()))
        try:
            final_identity=collect_identity(self.source_root)
            changed=final_identity.hashes!=candidate.code_identity.hashes or final_identity.commit!=candidate.code_identity.commit
            candidate=replace(candidate,final_code_identity=final_identity,sources_changed=changed,
                limitations=candidate.limitations+(['Fontes mudaram durante a Run; reprodução exata não demonstrada'] if changed else []))
            truth=truth_summary(self.out) if not alive else None
            candidate=evaluate_run(candidate,metrics,truth)
            atomic_json(self.out/'diagnostics/metrics.json',dict(schema_version=2,domain='observed_and_diagnostic',metrics=metrics))
            atomic_json(self.out/'system/pipeline.json',health)
            atomic_json(self.out/'validation/results.json',dict(schema_version=2,evaluation_status=candidate.evaluation_status,
                results=[r.to_dict() for r in candidate.results]))
            # Single controller-owned emergency/terminal journal, never shared with the data writer.
            with (self.out/'storage/terminal.jsonl').open('ab',buffering=0) as f:
                f.write(dumps(dict(schema_version=2,kind='execution_transition_prepared',committed_by='run.json',from_status=previous_status,to_status=candidate.execution_status,execution_status=candidate.execution_status,
                    integrity_status=candidate.integrity_status,stop_reason=reason,failures=health['failures'],
                    commands=[dict(a,effective_status=status) for a in self.commands.values()]))+b'\n')
            if not alive:
                candidate=replace(candidate,artifacts=self.writer.manifest(candidate.integrity_status))
            from .evidence import loads
            events=[]
            if not alive:
                for name in ('observed/events.jsonl','diagnostics/events.jsonl'):
                    path=self.out/name
                    if path.exists():
                        with path.open('rb') as f:
                            for _ in range(10):
                                line=f.readline()
                                if not line: break
                                try: events.append(loads(line))
                                except ValueError: break
            (self.out/'report.md').write_text(report_text(candidate,scenario,metrics,truth,health,events),encoding='utf-8')
            if not alive:
                candidate=replace(candidate,artifacts=self.writer.manifest(candidate.integrity_status))
            self.writer.check_disk_budget(replacement_run=candidate.to_dict())
            atomic_json(self.out/'run.json',candidate.to_dict())
        except BaseException as exc:
            self._failure('finalization',exc)
            candidate=replace(candidate,execution_status='failed',integrity_status='partial',
                evaluation_status='inconclusive' if candidate.criteria else 'not_evaluated',results=[],
                stop_reason='Falha na finalização: '+str(exc))
            health['failures']=list(self.failure_by_worker.values())
            try:
                atomic_json(self.out/'run.json',candidate.to_dict())
                with (self.out/'storage/finalization_error.jsonl').open('ab') as f:
                    f.write(dumps(dict(schema_version=2,worker='finalization',error_type=type(exc).__name__,message=str(exc)))+b'\n')
                atomic_json(self.out/'system/pipeline.json',health)
                atomic_json(self.out/'validation/results.json',dict(schema_version=2,
                    evaluation_status=candidate.evaluation_status,results=[]))
                (self.out/'report.md').write_text(report_text(candidate,scenario,metrics,None,health),encoding='utf-8')
                if not alive: candidate=replace(candidate,artifacts=self.writer.manifest('partial'))
                atomic_json(self.out/'run.json',candidate.to_dict())
            except OSError: pass  # The API still returns failure; old nonterminal metadata enables recovery.
        self.run=candidate
        self.health=health
        return self.run
