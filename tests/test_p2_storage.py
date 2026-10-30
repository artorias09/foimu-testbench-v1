from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from foimu_testbench.backend import RunController
from foimu_testbench.scenarios import import_v1
from foimu_testbench.storage import RunReader, RunWriter, digest_file, atomic_json
from foimu_testbench.provenance import new_run
from foimu_testbench.evidence import ObservedChunk, WriteBatch, WriteItem, dumps


class StorageTests(unittest.TestCase):
    def test_checkpoint_preserves_tail_and_never_recovers_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run';s=import_v1({});r=new_run(s,tmp,run_id='r')
            writer=RunWriter(p,r,s)
            writer.append(WriteBatch((WriteItem('observed/wire.bin',b'abc'),)))
            writer.checkpoint()
            writer.append(WriteBatch((WriteItem('observed/wire.bin',b'partial'),)))
            writer.close(checkpoint=False)
            before={f.relative_to(p):f.read_bytes() for f in p.rglob('*') if f.is_file()}
            reader=RunReader(p,strict=False)
            self.assertEqual(reader.run.execution_status,'interrupted_recovered')
            self.assertEqual(reader.confirmed['observed/wire.bin']['size_bytes'],3)
            self.assertEqual(reader.tails['observed/wire.bin']['present_bytes'],10)
            self.assertEqual(before,{f.relative_to(p):f.read_bytes() for f in p.rglob('*') if f.is_file()})
            with self.assertRaises(ValueError): RunReader(p)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError): RunController(import_v1({}),tmp).execute()

    def test_manifest_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'r';RunController(import_v1({'packets':2}),p).execute()
            with (p/'observed/wire.bin').open('ab') as f:f.write(b'corrupt')
            with self.assertRaises(ValueError):RunReader(p)
            self.assertEqual(RunReader(p,strict=False).run.integrity_status,'corrupt')

    def test_timeline_validated_even_without_manifest_trust(self):
        mutations=[lambda rows:rows[2]['time'].update(value=-1),
                   lambda rows:rows[2].update(global_offset=99),
                   lambda rows:rows[2].update(epoch_id='unknown'),
                   lambda rows:rows[2].update(read_seq=0),
                   lambda rows:rows[2].update(size=65537),
                   lambda rows:rows[2].update(schema_version=True),
                   lambda rows:rows.append(rows[-2]),lambda rows:rows.pop()]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'r';RunController(import_v1({'packets':2}),p).execute()
            reader=RunReader(p)
            target=p/'observed/chunks.jsonl';original=target.read_bytes()
            for mutation in mutations:
                rows=[json.loads(x) for x in original.splitlines()];mutation(rows)
                target.write_bytes(b''.join(dumps(x)+b'\n' for x in rows))
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):reader.validate_timeline()
            target.write_bytes(original)

    def test_backend_process_death_mid_write_and_recovery(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run'
            script='''
import os,sys
from foimu_testbench.storage import RunWriter
from foimu_testbench.scenarios import import_v1
from foimu_testbench.provenance import new_run
from foimu_testbench.evidence import WriteBatch,WriteItem
s=import_v1({});w=RunWriter(sys.argv[1],new_run(s,sys.argv[2],run_id='crash'),s)
w.append(WriteBatch((WriteItem('observed/wire.bin',b'abc'),)))
w.checkpoint()
w.append(WriteBatch((WriteItem('observed/wire.bin',b'xyz'),)))
os._exit(17)
'''
            r=subprocess.run([sys.executable,'-c',script,str(p),tmp],timeout=10,capture_output=True)
            self.assertEqual(r.returncode,17,r.stderr)
            a=RunReader(p,strict=False)
            self.assertEqual(a.run.execution_status,'interrupted_recovered')
            self.assertEqual(a.confirmed['observed/wire.bin']['size_bytes'],3)
            self.assertEqual((p/'observed/wire.bin').read_bytes(),b'abcxyz')

    def test_full_controller_killed_inside_writer(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'run'
            script='''
import os,sys
from foimu_testbench.backend import RunController,BackendOptions
from foimu_testbench.scenarios import import_v1
count=0
def kill(path,body):
    global count
    if path=='observed/wire.bin':
        count+=1
        if count==3:os._exit(19)
RunController(import_v1({'packets':100,'chunk_sizes':[53]}),sys.argv[1],writer_hook=kill,
    options=BackendOptions(checkpoint_every=1)).execute()
'''
            r=subprocess.run([sys.executable,'-c',script,str(p)],timeout=10,capture_output=True)
            self.assertEqual(r.returncode,19,r.stderr)
            before={f.relative_to(p):f.read_bytes() for f in p.rglob('*') if f.is_file()}
            a=RunReader(p,strict=False)
            self.assertEqual(a.run.execution_status,'interrupted_recovered')
            self.assertEqual(a.confirmed['observed/wire.bin']['size_bytes'],106)
            self.assertEqual(before,{f.relative_to(p):f.read_bytes() for f in p.rglob('*') if f.is_file()})

    def test_partial_checkpoint_keeps_previous_confirmed_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'r';s=import_v1({});w=RunWriter(p,new_run(s,tmp,run_id='r'),s)
            w.append(WriteBatch((WriteItem('observed/wire.bin',b'abc'),)))
            w.close()
            with (p/'storage/checkpoints.jsonl').open('ab') as f:f.write(b'{"schema_ver')
            reader=RunReader(p,strict=False)
            self.assertEqual(reader.confirmed['observed/wire.bin']['size_bytes'],3)
            self.assertTrue(any('parcial' in x for x in reader.issues))
