from dataclasses import replace
from pathlib import Path
import json
import tempfile
import threading
import unittest
from foimu_testbench.backend import RunController, BackendOptions, BoundedChannel, Overload
from foimu_testbench.core import AcceptanceCriterion
from foimu_testbench.evidence import WriteItem, WriteBatch
from foimu_testbench.emission import IterableSource, ReadResult, VirtualSource
from foimu_testbench.scenarios import import_v1
from foimu_testbench.protocol import encode
from foimu_testbench.simulator import synthetic_packet
from foimu_testbench.storage import RunReader
from foimu_testbench.replay import replay_run


def criterion(n):
    return AcceptanceCriterion(criterion_id='received',metric='frames_accepted',domain='observed',operator='eq',expected=n,unit='frames')


def metrics(path):
    return json.loads((Path(path)/'diagnostics/metrics.json').read_text())['metrics']


class BackendTests(unittest.TestCase):
    def test_normal_reopens_hashes_and_drains_without_deadlock(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'r';s=replace(import_v1({'packets':100}),acceptance_criteria=[criterion(100)])
            c=RunController(s,p);r=c.execute();a=RunReader(p)
            self.assertEqual((r.execution_status,r.evaluation_status,r.integrity_status),('completed','passed','complete'))
            self.assertEqual(metrics(p)['frames_accepted'],100)
            self.assertEqual(metrics(p)['checksum_errors'],0)
            self.assertEqual(c.health['workers_alive'],[])
            self.assertEqual(c.health['rx']['pending'],0)
            self.assertEqual(c.health['writer']['pending'],0)
            self.assertTrue((p/'report.md').exists())
            self.assertEqual(a.run,r)
            self.assertTrue(any(x.path.startswith('truth/') for x in r.artifacts))
            self.assertTrue(all(x.sha256 and x.size_bytes>0 for x in r.artifacts))

    def test_snapshot_detaches_mutable_scenario(self):
        with tempfile.TemporaryDirectory() as t:
            s=import_v1({'packets':2});c=RunController(s,Path(t)/'r')
            s.fragmentation.chunk_sizes.clear();s.fault_rules.clear()
            r=c.execute()
            self.assertEqual(r.execution_status,'completed')
            self.assertEqual(metrics(c.out)['frames_accepted'],2)

    def test_truth_removed_same_observed(self):
        with tempfile.TemporaryDirectory() as t:
            s=import_v1({'packets':101,'faults':{'drop_every':10,'checksum_every':11,'jitter_s':.001}})
            a=Path(t)/'a';b=Path(t)/'b'
            RunController(s,a).execute()
            RunController(s,b,source_factory=lambda cfg,rid,sink:VirtualSource(cfg,rid,lambda batch:None)).execute()
            self.assertEqual(metrics(a),metrics(b))
            for name in ('wire.bin','frames.jsonl','chunks.jsonl'):
                self.assertEqual((a/'observed'/name).read_bytes(),(b/'observed'/name).read_bytes())
            self.assertFalse((b/'truth').exists())

    def test_zero_data_never_implicit_pass(self):
        with tempfile.TemporaryDirectory() as t:
            a=RunController(import_v1({'packets':0}),Path(t)/'a').execute()
            b=RunController(replace(import_v1({'packets':0}),acceptance_criteria=[criterion(1)]),Path(t)/'b').execute()
            self.assertEqual(a.evaluation_status,'not_evaluated')
            self.assertEqual(b.evaluation_status,'failed')
            self.assertEqual(b.results[0].observed,0)
            RunReader(Path(t)/'a')
            self.assertFalse((Path(t)/'a/observed/wire.bin').exists())

    def test_corruption_and_unobservable_final_drop(self):
        with tempfile.TemporaryDirectory() as t:
            a=Path(t)/'a';b=Path(t)/'b'
            RunController(import_v1({'packets':101,'faults':{'checksum_every':10}}),a).execute()
            RunController(import_v1({'packets':10,'faults':{'drop_every':10}}),b).execute()
            self.assertEqual(metrics(a)['frames_accepted'],91)
            self.assertEqual(metrics(a)['checksum_errors'],10)
            self.assertEqual(metrics(b)['packets_lost'],0)
            self.assertEqual(metrics(b)['frames_accepted'],9)
            truth=json.loads((b/'truth/summary.jsonl').read_text())
            self.assertEqual(truth['dropped'],1)

    def test_garbage_and_silence_have_distinct_watchdogs(self):
        with tempfile.TemporaryDirectory() as t:
            for name,data,expected in [('noise',b'garbage',0),('silent',b'',1)]:
                p=Path(t)/name
                reads=[ReadResult(data,i*10_000_000,'chunk' if data else 'tick') for i in range(1,101)]
                c=RunController(import_v1({'stream_timeout_s':.025}),p,
                    source_factory=lambda cfg,rid,sink:IterableSource(reads))
                r=c.execute();self.assertEqual(r.execution_status,'completed')
                self.assertEqual(metrics(p)['byte_silence_episodes'],expected)
                self.assertEqual(metrics(p)['valid_frame_silence_episodes'],1)

    def test_writer_slow_does_not_directly_block_rx(self):
        entered=threading.Event();release=threading.Event();rx_advanced=threading.Event()
        def source(cfg,rid,sink):
            def reads():
                for i in range(100):
                    if i==80:rx_advanced.set()
                    yield ReadResult(encode(synthetic_packet(i,100)),(i+1)*10_000_000)
            return IterableSource(reads())
        once=[]
        def hook(path,body):
            if path=='observed/wire.bin' and not once:
                once.append(True);entered.set()
                if not release.wait(3):raise TimeoutError('Teste não liberou writer')
        with tempfile.TemporaryDirectory() as t:
            c=RunController(import_v1({}),Path(t)/'r',source_factory=source,writer_hook=hook)
            result=[];thread=threading.Thread(target=lambda:result.append(c.execute()))
            thread.start()
            try:
                self.assertTrue(entered.wait(3));self.assertTrue(rx_advanced.wait(3))
            finally: release.set();thread.join(8)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result[0].execution_status,'completed')
            self.assertGreater(c.health['writer']['peak_items'],1)

    def test_bounded_queue_exact_limit_rejection_no_eviction(self):
        q=BoundedChannel('test',10,2)
        item=WriteBatch((WriteItem('x',b'12345'),))
        q.put(item);q.put(item)
        with self.assertRaises(Overload):q.put(item)
        self.assertEqual(q.snapshot()['bytes'],10)
        self.assertEqual(q.snapshot()['enqueued_items'],2)
        self.assertIs(q.get(),item);q.done()
        self.assertIs(q.get(),item);q.done()
        self.assertEqual(q.snapshot()['pending'],0)

    def test_writer_queue_full_explicit_partial_and_no_deadlock(self):
        with tempfile.TemporaryDirectory() as t:
            c=RunController(import_v1({'packets':1000}),Path(t)/'r',
                options=BackendOptions(writer_bytes=1000,scheduling='unpaced_stress'))
            r=c.execute()
            self.assertEqual(r.execution_status,'failed')
            self.assertEqual(r.integrity_status,'partial')
            self.assertTrue(any(x['error_type']=='Overload' for x in c.health['failures']))
            self.assertLessEqual(c.health['writer']['peak_bytes'],1000)
            self.assertTrue((c.out/'storage/terminal.jsonl').exists())

    def test_rx_queue_full_explicit_partial(self):
        with tempfile.TemporaryDirectory() as t:
            c=RunController(import_v1({'packets':3}),Path(t)/'r',options=BackendOptions(rx_bytes=1))
            r=c.execute()
            self.assertEqual(r.integrity_status,'partial')
            self.assertEqual(c.health['failures'][0]['details']['queue'],'rx')

    def test_writer_dead_and_disk_full(self):
        for exception in (SystemExit('writer morto'),OSError(28,'Disco cheio simulado')):
            with self.subTest(error=exception),tempfile.TemporaryDirectory() as t:
                def hook(path,body):
                    if path=='observed/wire.bin':raise exception
                c=RunController(import_v1({'packets':20}),Path(t)/'r',writer_hook=hook)
                r=c.execute()
                self.assertEqual(r.execution_status,'failed')
                self.assertEqual(r.integrity_status,'partial')
                self.assertTrue(any(x['worker']=='writer' for x in c.health['failures']))
                self.assertEqual(c.health['workers_alive'],[])
                self.assertNotEqual(RunReader(c.out,strict=False).run.integrity_status,'complete')

    def test_stop_idempotent_and_drained(self):
        with tempfile.TemporaryDirectory() as t:
            acks=[]
            def source(cfg,rid,sink):
                def reads():
                    for i in range(20):
                        if i==5:
                            acks.append(c.request_stop('stop-1','Parada de teste'))
                            acks.append(c.request_stop('stop-1','Parada de teste'))
                        yield ReadResult(encode(synthetic_packet(i,100)),(i+1)*10_000_000)
                return IterableSource(reads())
            c=RunController(import_v1({}),Path(t)/'r',source_factory=source)
            r=c.execute()
            self.assertEqual(r.execution_status,'cancelled')
            self.assertEqual(r.stop_reason,'Parada de teste')
            self.assertEqual(r.integrity_status,'complete')
            self.assertEqual(metrics(c.out)['frames_accepted'],6)
            self.assertTrue(acks[0]['accepted']);self.assertTrue(acks[1]['duplicate'])
            self.assertEqual(acks[0]['requested_ns'],acks[1]['requested_ns'])
            RunReader(c.out)
            actions=[json.loads(x)['kind'] for x in (c.out/'control/actions.jsonl').read_text().splitlines()]
            self.assertEqual(actions.count('stop_ack'),1)
            self.assertEqual(c.health['writer']['pending'],0)

    def test_initial_identity_preserved_and_source_change_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'foimu_testbench').mkdir();f=root/'foimu_testbench/source.py';f.write_text('before')
            def factory(cfg,rid,sink):
                f.write_text('after')
                return IterableSource([])
            c=RunController(import_v1({}),root/'r',source_root=root,source_factory=factory)
            r=c.execute()
            self.assertTrue(r.sources_changed)
            self.assertNotEqual(r.code_identity.hashes,r.final_code_identity.hashes)
            self.assertTrue(r.limitations)

    def test_replay_source_config_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as t:
            a,b,c=[Path(t)/x for x in 'abc']
            r=RunController(import_v1({'packets':40,'rate_hz':50}),a).execute()
            repeated=replay_run(a,b)
            changed=replay_run(a,c,rate_hz=100)
            self.assertEqual(metrics(a),metrics(b))
            self.assertEqual(repeated.parent_run_id,r.run_id)
            self.assertAlmostEqual(metrics(c)['jitter_max_s'],.01)
            diff=json.loads((c/'derivation.json').read_text())['overrides']
            self.assertEqual(diff['rate']['original']['value'],50)
            self.assertEqual(diff['rate']['analysis']['value'],100)
            self.assertEqual((a/'observed/wire.bin').read_bytes(),(c/'observed/wire.bin').read_bytes())
            self.assertEqual(RunReader(a).run,r)

    def test_replay_preserves_epoch_boundaries_and_partial_discard(self):
        frame=encode(synthetic_packet(0,100))
        reads=[ReadResult(frame[:10],10),ReadResult(b'',20,'epoch','1'),
               ReadResult(frame,30,epoch='1')]
        with tempfile.TemporaryDirectory() as t:
            a,b=[Path(t)/x for x in 'ab']
            r=RunController(import_v1({}),a,source_factory=lambda *args:IterableSource(reads)).execute()
            repeated=replay_run(a,b)
            self.assertEqual(r.execution_status,'completed')
            self.assertEqual(repeated.execution_status,'completed')
            self.assertEqual(metrics(a),metrics(b))
            self.assertEqual(metrics(a)['reconnections'],1)
            for name in ('wire.bin','chunks.jsonl','frames.jsonl'):
                self.assertEqual((a/'observed'/name).read_bytes(),(b/'observed'/name).read_bytes())
            events=[json.loads(x) for x in (b/'observed/events.jsonl').read_text().splitlines()]
            discarded=next(x for x in events if x['kind']=='discard')
            self.assertEqual(discarded['epoch_id'],'0')
            self.assertEqual(discarded['byte_span']['end'],10)
            RunReader(b)

    def test_unit_mismatch_and_missing_truth_inconclusive(self):
        with tempfile.TemporaryDirectory() as t:
            criteria=[replace(criterion(3),unit='wrong'),AcceptanceCriterion(criterion_id='truth',domain='truth',metric='dropped',operator='eq',expected=0,unit='frames')]
            s=replace(import_v1({'packets':3}),acceptance_criteria=criteria)
            a=Path(t)/'a';b=Path(t)/'b';RunController(s,a).execute();r=replay_run(a,b)
            self.assertEqual(r.evaluation_status,'inconclusive')
            self.assertTrue(all(x.status=='inconclusive' for x in r.results))

    def test_worker_progress_detection_delay_with_mock_clock(self):
        from unittest.mock import Mock,patch
        c=RunController(import_v1({}),'unused')
        c.options=BackendOptions(worker_timeout_ns=10)
        c.progress={'writer':5};c.threads={'writer':Mock(is_alive=lambda:True)}
        with patch('foimu_testbench.backend.time.monotonic_ns',return_value=20):c._monitor()
        self.assertTrue(c.stop.is_set())
        self.assertEqual(c.failure_by_worker['writer']['details']['detection_delay_ns'],5)

    def test_nan_inf_preserved_in_wire_and_explicit_in_json(self):
        with tempfile.TemporaryDirectory() as t:
            frame=encode(synthetic_packet(0,100)._replace(ifog_x=float('nan'),ifog_y=float('inf')))
            c=RunController(import_v1({}),Path(t)/'r',source_factory=lambda *args:IterableSource([ReadResult(frame,1)]))
            r=c.execute()
            self.assertEqual(r.execution_status,'completed')
            result=json.loads((c.out/'observed/frames.jsonl').read_text())
            self.assertIsNone(result['fields']['ifog_x'])
            self.assertEqual(result['numeric_status']['ifog_x'],'nan')
            self.assertEqual(result['numeric_status']['ifog_y'],'pos_inf')
            self.assertEqual((c.out/'observed/wire.bin').read_bytes(),frame)

    def test_scheduled_action_order_and_not_reached(self):
        from foimu_testbench.scenarios import ScheduledAction, FaultRule
        with tempfile.TemporaryDirectory() as t:
            s=import_v1({'packets':10})
            rules=[replace(x,every=1,enabled=False) if x.kind=='drop_every' else x for x in s.fault_rules]
            actions=[ScheduledAction(action_id='on',rule_id='drop_every',enabled=True,at_opportunity=3,sequence_id=0),
                     ScheduledAction(action_id='off',rule_id='drop_every',enabled=False,at_opportunity=5,sequence_id=1),
                     ScheduledAction(action_id='future',rule_id='drop_every',enabled=True,at_opportunity=100,sequence_id=2)]
            c=RunController(replace(s,fault_rules=rules,scheduled_actions=actions),Path(t)/'r');r=c.execute()
            self.assertEqual(r.execution_status,'completed')
            self.assertEqual(metrics(c.out)['frames_accepted'],8)
            rows=[json.loads(x) for x in (c.out/'truth/faults.jsonl').read_text().splitlines()]
            self.assertTrue(any(x['kind']=='scheduled_action_not_reached' for x in rows))

    def test_invalid_capacity_rejected_before_resources(self):
        with self.assertRaises(ValueError):BackendOptions(rx_bytes=True)
        with self.assertRaises(ValueError):BackendOptions(checkpoint_every=0)

    def test_disk_budget_cannot_report_complete(self):
        from foimu_testbench.scenarios import ResourceLimits
        with tempfile.TemporaryDirectory() as t:
            s=replace(import_v1({'packets':200}),resource_limits=ResourceLimits(max_disk_bytes=50000))
            c=RunController(s,Path(t)/'r',source_root=t);r=c.execute()
            self.assertNotEqual(r.execution_status,'completed')
            self.assertEqual(r.integrity_status,'partial')

    def test_failure_in_finalization_cannot_publish_completed_or_stale_report(self):
        from unittest.mock import patch
        from foimu_testbench.storage import RunWriter
        checked=[];original=RunWriter.check_disk_budget
        with tempfile.TemporaryDirectory() as t:
            s=replace(import_v1({'packets':2}),acceptance_criteria=[criterion(2)])
            c=RunController(s,Path(t)/'r')
            def fail(writer,replacement_run=None):
                if replacement_run is not None:
                    checked.append(c.run.execution_status)
                    raise OSError(28,'Falha ao confirmar finalização')
                return original(writer)
            with patch.object(RunWriter,'check_disk_budget',fail):r=c.execute()
            self.assertEqual(checked,['finalizing'])
            self.assertEqual(r.execution_status,'failed')
            self.assertEqual(r.evaluation_status,'inconclusive')
            self.assertIn('**failed**',(c.out/'report.md').read_text())
            self.assertNotIn('**passed**',(c.out/'report.md').read_text())
            self.assertEqual(json.loads((c.out/'validation/results.json').read_text())['evaluation_status'],'inconclusive')
