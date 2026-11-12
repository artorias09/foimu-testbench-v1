from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import json
from foimu_testbench.scenarios import import_v1


class CLITests(unittest.TestCase):
    def invoke(self,*args):
        return subprocess.run([sys.executable,'-m','foimu_testbench',*args],capture_output=True,text=True,timeout=15)

    def test_v2_cli_import_run_inspect_replay_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'v1.json').write_text('{"packets":3}', encoding='utf-8')
            r=self.invoke('run-v2','--config-v1',str(p/'v1.json'),'--out',str(p/'r'))
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['evaluation_status'],'not_evaluated')
            r=self.invoke('inspect-v2','--run',str(p/'r'));self.assertEqual(r.returncode,0,r.stderr)
            r=self.invoke('replay-v2','--run',str(p/'r'),'--out',str(p/'replay'));self.assertEqual(r.returncode,0,r.stderr)
            r=self.invoke('run-v2','--config-v1',str(p/'v1.json'),'--out',str(p/'r'));self.assertEqual(r.returncode,2)

    def test_strict_schema_rejected_and_scenario_cli(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);s=import_v1({'packets':2});(p/'s.json').write_text(s.to_json(), encoding='utf-8')
            r=self.invoke('run-v2','--scenario',str(p/'s.json'),'--out',str(p/'r'));self.assertEqual(r.returncode,0,r.stderr)
            d=s.to_dict();d['seed']=True;(p/'s.json').write_text(json.dumps(d), encoding='utf-8')
            r=self.invoke('run-v2','--scenario',str(p/'s.json'),'--out',str(p/'bad'));self.assertEqual(r.returncode,2)
            self.assertFalse((p/'bad').exists())
