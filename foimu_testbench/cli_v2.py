"""Additive headless CLI; v1 commands keep their original runners."""
import argparse
import json
from pathlib import Path
import sys
from .backend import RunController, BackendOptions
from .scenarios import Scenario, load_v1
from .storage import RunReader
from .replay import replay_run


def main(argv):
    parser=argparse.ArgumentParser(description='FO-IMU P2: backend sem interface gráfica')
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run-v2')
    src=run.add_mutually_exclusive_group(required=True)
    src.add_argument('--scenario'); src.add_argument('--config-v1')
    run.add_argument('--out',required=True);run.add_argument('--options')
    inspect=sub.add_parser('inspect-v2')
    inspect.add_argument('--run',required=True);inspect.add_argument('--recover',action='store_true')
    replay=sub.add_parser('replay-v2')
    replay.add_argument('--run',required=True);replay.add_argument('--out',required=True)
    replay.add_argument('--rate-hz',type=float);replay.add_argument('--options')
    args=parser.parse_args(argv)
    try:
        if args.command=='inspect-v2':
            reader=RunReader(args.run,strict=not args.recover)
            print(json.dumps(dict(run=reader.run.to_dict(),issues=reader.issues,
                                  confirmed=reader.confirmed,tails=reader.tails),ensure_ascii=False,indent=2))
            return 0 if not reader.issues else 3
        options=BackendOptions.from_json(Path(args.options).read_bytes()) if args.options else BackendOptions()
        if args.command=='run-v2':
            scenario=load_v1(args.config_v1) if args.config_v1 else Scenario.from_json(Path(args.scenario).read_bytes())
            result=RunController(scenario,args.out,options=options).execute()
        else:
            result=replay_run(args.run,args.out,rate_hz=args.rate_hz,options=options)
        print(json.dumps(dict(run_id=result.run_id,execution_status=result.execution_status,
            evaluation_status=result.evaluation_status,integrity_status=result.integrity_status,
            stop_reason=result.stop_reason,out=str(Path(args.out).resolve())),ensure_ascii=False,indent=2))
        if result.execution_status=='cancelled': return 130
        if result.execution_status!='completed' or result.integrity_status!='complete': return 3
        return 4 if result.evaluation_status in ('failed','inconclusive') else 0
    except (ValueError,OSError) as exc:
        print(f'Erro: {exc}',file=sys.stderr)
        return 2
