"""Run once from repository root in a dedicated Python 3.12 environment."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
from foimu_testbench.scenarios import Scenario, import_v1
from foimu_testbench.provenance import collect_identity, new_run
from foimu_testbench.storage import RunWriter, atomic_json, digest_file
from .p3_harness import Backend, check, exercise


def main():
    import PySide6, pyqtgraph, numpy
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    parser.add_argument('--windows-gate',action='store_true')
    args = parser.parse_args()
    check(sys.version_info[:2]==(3,12),'Python 3.12 obrigatório')
    versions = [PySide6.__version__,pyqtgraph.__version__,numpy.__version__]
    check(versions==['6.8.3','0.13.7','2.3.5'],'Versões diferentes do ambiente fixado')
    if args.windows_gate:
        check(sys.platform=='win32' and sys.getwindowsversion().major==10 and sys.prefix!=sys.base_prefix,
              'Requer Windows 10/11 real e venv dedicado')
    root = Path(args.out).resolve()
    root.mkdir(parents=True)
    began = time.monotonic()
    result = dict(passed=False,released=False,windows=False,identity=collect_identity(Path.cwd()).to_dict(),
                  os=platform.platform(),python=platform.python_version(),gui_versions=versions)
    try:
        print('Regressão P2, suíte completa e milhão legado',flush=True)
        with (root/'p2.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-m','tools.acceptance_p2','--out',str(root/'p2')],stdout=log,stderr=subprocess.STDOUT,check=True)
        p2=json.loads((root/'p2/summary.json').read_bytes())
        count=unittest.defaultTestLoader.discover('tests',pattern='test_p3*.py').countTestCases()
        check(count>=15 and p2['tests']>=108+count and p2['passed'],'Regressão ou descoberta incompleta')
        result.update(tests=p2['tests'],p3_tests=count,legacy_packets=p2['legacy_packets'])
        normal=Scenario.from_json(Path('configs/v2/normal.json').read_bytes())
        backend=Backend(root)
        try:
            for mode,s in [('slow',normal),('checksum',import_v1({'packets':1001,'faults':{'checksum_every':10}})),
                           ('stop',import_v1({'packets':100000}))]:
                print('GUI '+mode,flush=True)
                d=exercise(backend,root/mode,s,mode)
                result[mode]=d
                check(d['live_seen'] and d['report_opened'] and d['shown_report'],'Fluxo visual incompleto')
                if mode=='slow':
                    check(d['metrics']==dict(frames_accepted=6000,packets_lost=0,checksum_errors=0,framing_errors=0)
                          and d['plotted_points']==6000 and d['perf']['replaced']>0 and d['slowed'],'Normal/lentidão')
                elif mode=='checksum':
                    check(d['metrics']==dict(frames_accepted=901,packets_lost=100,checksum_errors=101,framing_errors=100)
                          and d['visible_events']>0,'Oráculo checksum')
                else: check(d['stopped'] and 0<d['metrics']['frames_accepted']<100000,'Stop')
            original=root/'slow/run'
            def hashes(): return {str(p):digest_file(p) for p in original.rglob('*') if p.is_file()}
            before=hashes()
            result['open']=exercise(backend,root/'open',normal,'open',original)
            check(result['open']['plotted_points']==6000 and result['open']['report_opened'] and before==hashes(),'Reabertura')
            partial=root/'interrupted'
            RunWriter(partial,new_run(normal,Path.cwd(),run_id='partial'),normal).close()
            result['partial']=exercise(backend,root/'recovery',normal,'partial',partial)
        finally: backend.close()
        life=root/'lifecycle'
        life.mkdir()
        backend=Backend(life,guarded=True)
        try:
            for mode in ('close','kill'):
                result[mode]=exercise(backend,life/mode,import_v1({'packets':400,'chunk_sizes':[53]}),mode)
                check(result[mode]['metrics']['frames_accepted']==400,'Perda após saída da GUI')
        finally: backend.close()
        if args.windows_gate:
            check(result['slow']['qt_platform']=='windows','Qt nativo Windows obrigatório')
        result.update(passed=True,released=args.windows_gate,windows=args.windows_gate)
    except Exception as exc:
        result['error']=str(exc)
        raise
    finally:
        result['wall_s']=time.monotonic()-began
        atomic_json(root/'summary.json',result)
    print('Gate disponível aprovado',flush=True)


if __name__=='__main__': main()
