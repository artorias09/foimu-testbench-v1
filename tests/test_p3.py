import json
import math
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from foimu_testbench.ipc import envelope, send, receive, validate, LIMIT
from foimu_testbench.gui.client import Latest, Client
from foimu_testbench.presentation import View, series, filtered, UNITS, FIELDS
from foimu_testbench.service import Service
from foimu_testbench.scenarios import import_v1
from foimu_testbench.storage import RunReader, RunWriter
from foimu_testbench.provenance import new_run


class ProtocolTests(unittest.TestCase):
    def test_roundtrip(self):
        a,b=socket.socketpair()
        with a,b:
            msg=envelope('hello',{})
            send(a,msg)
            self.assertEqual(receive(b),msg)

    def test_bad_envelope(self):
        for key,v in [('schema_version',True),('catalog_ns',False),('message_type',[]),('id',''),('payload',[])]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate(dict(envelope('hello',{}),**{key:v}))

    def test_bad_length_duplicate_truncation(self):
        for data in (struct.pack('!I',LIMIT+1),struct.pack('!I',13)+b'{"a":1,"a":2}',struct.pack('!I',4)+b'{'):
            a,b=socket.socketpair()
            with a,b:
                a.sendall(data)
                a.shutdown(socket.SHUT_WR)
                with self.assertRaises((ValueError,ConnectionError)):receive(b)

    def test_slow_consumer_keeps_latest(self):
        slot=Latest()
        for i in range(2000):slot.put(str(i).encode())
        self.assertEqual(slot.replaced,1999)
        self.assertEqual(slot.take(),b'1999')
        self.assertIsNone(slot.take())

    def test_disconnect_does_not_start_run(self):
        c=Client(1)
        def dead(port,kind):
            self.assertEqual(kind,'snapshot_request')
            c.closed.set()
            raise ConnectionError('Teste')
        with patch('foimu_testbench.gui.client.request',side_effect=dead):
            c.run()
        self.assertFalse(json.loads(c.latest.take())['connected'])
        self.assertTrue(c.commands.empty())


class PlotTests(unittest.TestCase):
    def row(self,i,value=1):
        return [i*10_000_000,'0',i*53,(i+1)%256,[value]*len(FIELDS)]

    def test_nonfinite_and_missing(self):
        rows=[self.row(i,v) for i,v in enumerate((1,None,float('nan'),float('inf')))]
        self.assertTrue(all(math.isnan(y) for y in series(rows,'ifog_x',100)[1][1:]))

    def test_counter_gap_epoch_offset_and_time(self):
        for index,value in [(0,3_000_000_000),(1,'another'),(2,106),(3,8)]:
            b=self.row(1)
            b[index]=value
            self.assertTrue(math.isnan(series([self.row(0),b],'ifog_x',100)[1][1]))

    def test_thermal_slot_units(self):
        self.assertEqual(series([self.row(i) for i in range(16)],'temp_0',100)[0],[0,.08])
        self.assertNotEqual(UNITS['acc_z'],UNITS['mems_acc_z'])
        self.assertNotEqual(UNITS['ifog_x'],UNITS['mems_gyro_x'])

    def test_event_filters(self):
        event=dict(domain='observed',component_path='FO-IMU/Host',severity='warning',byte_span={'start':0,'end':53})
        self.assertEqual(filtered([event],'observed','host','warning'),[event])
        self.assertEqual(filtered([event],'truth'),[])


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'run'
        self.s=Service()
        self.recipe=import_v1({'packets':101,'chunk_sizes':[53],'faults':{'checksum_every':10}})

    def tearDown(self):
        if self.s.worker:self.s.worker.join(10)
        self.temp.cleanup()

    def cmd(self,kind,**p):
        return self.s.command(envelope(kind,p))['payload']

    def start(self):
        return self.cmd('start_run',command_id='one',scenario=self.recipe.to_dict(),out=str(self.root))

    def finish(self):
        self.s.worker.join(10)
        self.assertFalse(self.s.worker.is_alive())

    def test_duplicate_start_and_payload_collision(self):
        a=self.start()
        self.finish()
        b=self.start()
        self.assertEqual(a['run_id'],b['run_id'])
        self.assertTrue(b['duplicate'])
        with self.assertRaises(ValueError):self.cmd('open_run',command_id='one',path=str(self.root))

    def test_completed_without_client_and_states(self):
        self.start();self.finish()
        r=RunReader(self.root).run
        self.assertEqual((r.execution_status,r.evaluation_status,r.integrity_status),('completed','not_evaluated','complete'))
        self.assertTrue((self.root/'report.md').exists())

    def test_stop_idempotent_drain(self):
        from foimu_testbench.backend import RunController
        from foimu_testbench.emission import IterableSource,ReadResult
        entered,release=threading.Event(),threading.Event()
        def factory(*args):
            def reads():
                entered.set()
                if not release.wait(4):raise TimeoutError()
                yield ReadResult(b'x',1)
            return IterableSource(reads())
        with patch('foimu_testbench.service.RunController',side_effect=lambda s,p:RunController(s,p,source_factory=factory)):
            ack=self.start()
        try:
            self.assertTrue(entered.wait(3))
            p=dict(command_id='stop',reason='Stop de teste',run_id=ack['run_id'])
            self.assertTrue(self.cmd('stop_run',**p)['accepted'])
            self.assertTrue(self.cmd('stop_run',**p)['duplicate'])
        finally:release.set()
        self.finish()
        self.assertEqual(self.s.state()['execution_status'],'cancelled')
        self.assertEqual(self.s.state()['integrity_status'],'complete')

    def test_projection_matches_final_and_never_reads_truth(self):
        self.start();self.finish()
        v=View(self.root,100)
        for f in (self.root/'truth').iterdir():f.unlink()
        v.advance()
        final=json.loads((self.root/'diagnostics/metrics.json').read_bytes())['metrics']
        for k,value in v.metrics.items():self.assertAlmostEqual(value,final[k],places=12)
        self.assertEqual(len(v.frames),91)
        self.assertTrue(any(e['kind']=='checksum_candidate_rejected' and e['byte_span'] for e in v.events))
        before=v.positions.copy()
        v.advance()
        self.assertEqual(v.positions,before)
        self.assertEqual(v.metrics['frames_accepted'],91)

    def test_blocked_presentation_does_not_block_writer(self):
        entered,release=threading.Event(),threading.Event()
        def wait(view):
            entered.set();release.wait(5)
        self.start()
        with patch.object(View,'advance',wait):
            thread=threading.Thread(target=self.s.snapshot)
            thread.start()
            try:
                self.assertTrue(entered.wait(3))
                self.finish()
                self.assertEqual(RunReader(self.root).run.integrity_status,'complete')
            finally:release.set();thread.join(5)

    def test_reopen_and_report_readonly(self):
        self.start();self.finish()
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.cmd('open_run',command_id='open',path=str(self.root))
        sections={m['message_type']:m['payload'] for m in self.s.snapshot()['messages']}
        self.assertEqual(sections['run_finished']['report'],(self.root/'report.md').read_text(encoding='utf-8'))
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_open_partial_ignores_unconfirmed_tail(self):
        from foimu_testbench.evidence import WriteBatch,WriteItem
        w=RunWriter(self.root,new_run(self.recipe,self.root.parent,run_id='partial'),self.recipe)
        w.append(WriteBatch((WriteItem('observed/frames.jsonl',b'invalid tail\n'),)))
        w.close(checkpoint=False)
        self.cmd('open_run',command_id='open',path=str(self.root))
        self.assertEqual(self.s.state()['execution_status'],'interrupted_recovered')
        self.assertEqual(self.s.state()['integrity_status'],'partial')
        self.s.view.advance()
        self.assertEqual(len(self.s.view.frames),0)

    def test_snapshot_rate_and_bounds(self):
        self.start();self.finish()
        with patch('foimu_testbench.service.time.monotonic',return_value=3):
            a=self.s.snapshot()
            self.assertEqual(self.s.snapshot()['sequence'],a['sequence'])
        self.assertEqual(self.s.view.frames.maxlen,6000);self.assertEqual(self.s.view.events.maxlen,500)

    def test_display_window_max_60_seconds(self):
        self.start();self.finish()
        p=self.root/'observed/frames.jsonl'
        rows=[json.loads(x) for x in p.read_bytes().splitlines()]
        for i,r in enumerate(rows):r['time']['value']=i*2_000_000_000
        p.write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in rows))
        self.s.view.advance()
        frames=self.s.view.frames
        self.assertLessEqual(frames[-1][0]-frames[0][0],60_000_000_000)
        self.assertLess(len(frames),len(rows))
