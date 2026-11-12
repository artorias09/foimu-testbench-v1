import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from foimu_testbench.ipc import request
from foimu_testbench.storage import RunReader


def check(value, detail):
    if not value:
        raise RuntimeError('Gate P3: ' + detail)


def wait_until(predicate, timeout):
    limit = time.monotonic()+timeout
    while time.monotonic() < limit:
        if predicate(): return
        threading.Event().wait(.05)
    raise TimeoutError('Prazo excedido em ' + predicate.__name__)


class Backend:
    def __init__(self, root, guarded=False):
        self.root = root
        self.guarded = guarded
        args = [sys.executable,'-u','-m','foimu_testbench.service','--port','0']
        if guarded:
            # Explicit test fixture. A barrier holds the writer after a real prefix
            # until the parent has verified that the real GUI process is gone.
            script = """
from pathlib import Path
import threading,sys,time
import foimu_testbench.service as s
from foimu_testbench.backend import BackendOptions, RunController
def factory(recipe, out):
    n=0
    def hook(name,body):
        nonlocal n
        if name=='observed/wire.bin':
            n+=1
            if n==128:
                limit=time.monotonic()+30
                while not (out.parent/'release').exists():
                    if time.monotonic()>limit: raise TimeoutError('Barreira do teste')
                    threading.Event().wait(.02)
    return RunController(recipe,out,writer_hook=hook,options=BackendOptions(worker_timeout_ns=40_000_000_000))
s.RunController=factory
with s.Server(0) as server:
    print('READY',server.server_address[1],flush=True)
    server.serve_forever(.2)
"""
            args = [sys.executable,'-u','-c',script]
        self.log = (root/'backend.log').open('w',encoding='utf-8')
        self.proc = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=self.log,text=True)
        ready = queue.Queue(1)
        threading.Thread(target=lambda: ready.put(self.proc.stdout.readline()),daemon=True).start()
        try:
            line = ready.get(timeout=15)
            check(line.startswith('READY '), 'Serviço indisponível')
            self.port = int(line.split()[1])
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.proc.poll() is None: self.proc.terminate()
        self.proc.communicate(timeout=15)
        self.log.close()

    def state(self):
        return request(self.port,'get_status')['payload']


def exercise(backend, case, scenario, mode, source=None):
    case.mkdir()
    (case/'scenario.json').write_text(scenario.to_json(),encoding='utf-8')
    root = source or case/'run'
    env = os.environ.copy()
    if sys.platform != 'win32' and not env.get('DISPLAY'):
        env.setdefault('QT_QPA_PLATFORM','offscreen')
    args = [sys.executable,'-m','tools.p3_probe',str(backend.port),str(case),mode,str(root)]
    with (case/'qt.log').open('w',encoding='utf-8') as log:
        gui = subprocess.Popen(args,stdout=log,stderr=log,env=env)
        try:
            if mode == 'kill':
                wait_until(lambda: (case/'active').exists() or gui.poll() is not None,40)
                check(gui.poll() is None and backend.state()['execution_status']=='running','Kill requer GUI e Run ativas')
                gui.kill()
                gui.wait(timeout=10)
                data = {'killed_while_running':True}
            else:
                check(gui.wait(timeout=165)==0,'Erro do cliente Qt em '+str(case))
                data = json.loads((case/'gui.json').read_bytes())
                check(data['ok'],'Cliente não atingiu o estado solicitado')
            if backend.guarded:
                check(backend.state()['execution_status']=='running','Backend deixou de executar antes de liberar o dreno')
                (case/'release').touch()
            wait_until(lambda: backend.state()['can_start'],90)
            reader = RunReader(root,strict=mode!='partial')
            if mode=='partial':
                check(reader.run.execution_status=='interrupted_recovered','Recuperação incorreta')
            else:
                expected = 'cancelled' if mode=='stop' else 'completed'
                check(reader.run.execution_status==expected and reader.run.integrity_status=='complete','Estado terminal incorreto')
                check((root/'report.md').exists(),'Relatório ausente')
                metrics = json.loads((root/'diagnostics/metrics.json').read_bytes())['metrics']
                data['metrics'] = {k:metrics[k] for k in ('frames_accepted','packets_lost','checksum_errors','framing_errors')}
            return data
        finally:
            if gui.poll() is None: gui.kill()
            gui.wait(timeout=10)
