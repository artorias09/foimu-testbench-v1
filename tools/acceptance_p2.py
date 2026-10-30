"""Explicit P2 gates. Run from the repository root; all outputs use a new directory."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from foimu_testbench.backend import RunController, BackendOptions
from foimu_testbench.core import AcceptanceCriterion
from foimu_testbench.scenarios import Scenario, import_v1
from foimu_testbench.storage import RunReader, atomic_json
from foimu_testbench.replay import replay_run
from foimu_testbench.emission import VirtualSource
from foimu_testbench.protocol import encode, decode


def check(condition, message):
    if not condition: raise RuntimeError('Aceitação P2 falhou: '+message)


def metrics(path):
    return json.loads((path/'diagnostics/metrics.json').read_text())['metrics']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    root=Path(args.out).resolve();root.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    print('Suíte completa e aceitação legada de 1 milhão',flush=True)
    with (root/'legacy-console.txt').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-m','tools.acceptance','--out',str(root/'legacy')],stdout=log,stderr=subprocess.STDOUT,check=True)
    legacy=json.loads((root/'legacy/summary.json').read_text())
    check(legacy['unit_integration_tests']>=105,'Descoberta incompleta de testes')
    check(legacy['normal_packets']==1_000_000,'Milhão não executado')
    check(legacy['normal_metrics']['packets_received']==1_000_000,'Contagem normal legada')
    for key in ('packets_lost','checksum_errors','framing_errors'):
        check(legacy['normal_metrics'][key]==0,'Erro normal legado: '+key)
    for name,case in legacy['scenarios'].items():
        if name=='jitter':check(case['packets_received']==1001,'Jitter legado')
        else:
            check(case['packets_received']==901 and case['packets_lost']==100,'Oráculo legado '+name)
            expected=0 if name=='loss' else 1 if name=='header' else 101
            check(case['checksum_errors']==expected,'Checksum legado '+name)
    print('Run virtual v2: 6000 oportunidades, fragmentação v1',flush=True)
    s=Scenario.from_json(Path('configs/v2/normal.json').read_bytes())
    t=time.perf_counter();normal=RunController(s,root/'normal').execute();normal_wall=time.perf_counter()-t
    check(normal.evaluation_status=='passed' and normal.integrity_status=='complete','Run normal não aprovada')
    m=metrics(root/'normal');check(m['frames_accepted']==6000,'Contagem v2')
    for key in ('packets_lost','checksum_errors','framing_errors'):check(m[key]==0,key)
    RunReader(root/'normal')
    print('Replay fiel da Run v2',flush=True)
    t=time.perf_counter();replayed=replay_run(root/'normal',root/'replay');replay_wall=time.perf_counter()-t
    check(replayed.evaluation_status=='passed','Replay não aprovado')
    check(m==metrics(root/'replay'),'Métricas de replay divergentes')
    check((root/'normal/observed/wire.bin').read_bytes()==(root/'replay/observed/wire.bin').read_bytes(),'Wire de replay')
    print('Falha de checksum com oráculo explícito',flush=True)
    fault=replace(import_v1({'packets':1001,'faults':{'checksum_every':10}}),acceptance_criteria=[
        AcceptanceCriterion(criterion_id='frames',metric='frames_accepted',domain='observed',operator='eq',expected=901,unit='frames'),
        AcceptanceCriterion(criterion_id='candidates',metric='checksum_errors',domain='observed',operator='eq',expected=101,unit='candidates')])
    fault_run=RunController(fault,root/'fault').execute();check(fault_run.evaluation_status=='passed','Oráculo de falha v2')
    RunReader(root/'fault')
    print('Writer lento por barreira de teste e sobrecarga explícita',flush=True)
    entered=threading.Event();release=threading.Event();rx_advanced=threading.Event();once=[]
    def hook(path,body):
        if path=='observed/wire.bin' and not once:
            once.append(True);entered.set()
            if not release.wait(5):raise TimeoutError('Writer não liberado pelo ensaio')
    def factory(cfg,rid,sink):
        source=VirtualSource(cfg,rid,sink);read=source.read;count=0
        def tracked_read():
            nonlocal count
            result=read();count+=1
            if count==80:rx_advanced.set()
            return result
        source.read=tracked_read
        return source
    slow=RunController(import_v1({'packets':200,'chunk_sizes':[53]}),root/'slow',source_factory=factory,writer_hook=hook)
    results=[];thread=threading.Thread(target=lambda:results.append(slow.execute()))
    thread.start()
    try:check(entered.wait(5) and rx_advanced.wait(5),'RX bloqueada diretamente pelo writer')
    finally:release.set();thread.join(15)
    check(not thread.is_alive() and results and results[0].integrity_status=='complete','Dreno do writer lento')
    check(metrics(root/'slow')['frames_accepted']==200,'Perda com writer lento')
    RunReader(root/'slow')
    overload=RunController(import_v1({'packets':100}),root/'overload',options=BackendOptions(writer_bytes=1000,scheduling='unpaced_stress'))
    over=overload.execute();check(over.execution_status=='failed' and over.integrity_status=='partial','Sobrecarga mascarada')
    check(any(x['error_type']=='Overload' for x in overload.health['failures']),'Evento de sobrecarga ausente')
    print('Morte do backend durante escrita e recuperação sem alterar origem',flush=True)
    script='''
import os,sys
from foimu_testbench.backend import RunController,BackendOptions
from foimu_testbench.scenarios import import_v1
n=0
def hook(path,body):
    global n
    if path=='observed/wire.bin':
        n+=1
        if n==3:os._exit(19)
RunController(import_v1({'packets':100,'chunk_sizes':[53]}),sys.argv[1],writer_hook=hook,
    options=BackendOptions(checkpoint_every=1)).execute()
'''
    process=subprocess.run([sys.executable,'-c',script,str(root/'interrupted')],capture_output=True,timeout=15)
    check(process.returncode==19,'Backend não foi interrompido no ponto esperado')
    recovered=RunReader(root/'interrupted',strict=False)
    check(recovered.run.execution_status=='interrupted_recovered','Recuperação incorreta')
    check(recovered.confirmed['observed/wire.bin']['size_bytes']==106,'Prefixo confirmado incorreto')
    golden=Path('tests/fixtures/golden_frame.bin').read_bytes()
    check(encode(decode(golden))==golden and len(golden)==53,'Golden legado alterado')
    summary=dict(schema_version=2,passed=True,tests=legacy['unit_integration_tests'],legacy_packets=1_000_000,
        normal_frames=m['frames_accepted'],normal_wall_s=normal_wall,replay_wall_s=replay_wall,
        elapsed_wall_s=time.perf_counter()-started,normal_bytes=(root/'normal/observed/wire.bin').stat().st_size,
        normal_total_disk_bytes=sum(p.stat().st_size for p in (root/'normal').rglob('*') if p.is_file()),
        normal_code_identity=normal.code_identity.to_dict(),normal_metrics={k:m[k] for k in ('frames_accepted','packets_lost','checksum_errors','framing_errors')},
        slow_pipeline=slow.health,overload_status=over.execution_status,recovered_prefix_bytes=106,
        not_validated=['Windows','8 horas reais','RSS prolongado','Hardware','Desempenho sustentado sem barreiras'])
    atomic_json(root/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
