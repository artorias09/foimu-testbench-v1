"""Legacy observations, not desired v2 behavior. No hardware or wall-clock waits."""
import ast
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from foimu_testbench import runners
from foimu_testbench.acquisition import Capture
from foimu_testbench.config import validate_config
from foimu_testbench.fault_injection import Injector
from foimu_testbench.protocol import StreamParser, encode
from foimu_testbench.simulator import synthetic_packet
from tools import acceptance


class LegacyCharacterization(unittest.TestCase):
    def test_b03_replay_accepts_after_end_and_clock_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            frame = encode(synthetic_packet(0, 100))
            (p/'wire').write_bytes(frame*2)
            events = [dict(event='chunk', offset=0, length=53, received_s=.02),
                      dict(event='end', received_s=.005),
                      dict(event='chunk', offset=53, length=53, received_s=.01)]
            (p/'time').write_text(''.join(json.dumps(x)+'\n' for x in events))
            r = runners.replay(validate_config({}), p/'out', p/'wire', p/'time')
            self.assertEqual(r['execution']['status'], 'completed')
            self.assertEqual(r['metrics']['clock_regressions'], 1)
            self.assertEqual(r['metrics']['packets_received'], 2)

    def test_b04_replay_uses_caller_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            a = runners.demo(validate_config({'rate_hz':50, 'packets':3}), p/'a')
            b = runners.replay(validate_config({}), p/'b', p/'a/wire.bin', p/'a/chunks.jsonl')
            self.assertEqual(a['wire_sha256'], b['wire_sha256'])
            self.assertAlmostEqual(a['metrics']['jitter_max_s'], 0)
            self.assertAlmostEqual(b['metrics']['jitter_max_s'], .01)

    def test_b05_completed_without_receiving(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runners.time, 'monotonic', side_effect=[0, 2, 2]):
            r = runners.acquire(validate_config({}), Path(tmp)/'run', 'localhost', 1, 1)
            self.assertEqual(r['execution']['status'], 'completed')
            self.assertEqual(r['metrics']['packets_received'], 0)

    def test_b06_legacy_acceptance_has_optimization_sensitive_asserts(self):
        source = inspect.getsource(acceptance)
        self.assertTrue(any(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(source))))
        self.assertFalse(any(isinstance(n, ast.Assert) for n in ast.walk(ast.parse('pass'))))
        self.assertTrue(unittest.TestResult().wasSuccessful())  # zero tests is not a gate
        self.assertIn('"passed": True', source)

    def test_b07_parser_returns_packets_without_byte_spans(self):
        parser = StreamParser()
        frame = encode(synthetic_packet(0,100))
        packets = list(parser.feed(b'bad'+frame))
        self.assertEqual(len(packets), 1)
        self.assertFalse(hasattr(packets[0], 'byte_span'))
        self.assertEqual(parser.stats['discarded_bytes'],3)

    def test_b08_drop_suppresses_other_faults(self):
        cfg=validate_config({'faults':{'drop_every':1, 'checksum_every':1}})
        inj=Injector(cfg['faults'], cfg['seed'])
        data, _ = inj.apply(0, encode(synthetic_packet(0,100)), .01)
        self.assertEqual(data,b'')
        self.assertEqual(inj.counts['dropped'],1)
        self.assertEqual(inj.counts['checksum'],0)

    def test_b09_planned_count_is_not_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=runners.demo(validate_config({'packets':3,'faults':{'drop_every':1}}),Path(tmp)/'run')
            self.assertEqual(r['metrics']['packets_expected'],3)
            self.assertEqual(r['metrics']['packets_received'],0)
            self.assertEqual(r['simulator_truth']['dropped'],3)

    def test_b10_identity_collected_at_finish(self):
        with tempfile.TemporaryDirectory() as tmp, patch('foimu_testbench.acquisition.source_digest', return_value='end') as digest:
            c=Capture(Path(tmp)/'run',validate_config({}),'test')
            digest.assert_not_called()
            r=c.finish(0)
            digest.assert_called_once()
            self.assertEqual(r['source_sha256'],'end')

    def test_b12_garbage_keeps_byte_watchdog_alive(self):
        connection=Mock()
        connection.recv.return_value=b'garbage'
        # start, loop, now, connected, recv, next loop, finish
        with tempfile.TemporaryDirectory() as tmp, patch.object(runners.time,'monotonic',side_effect=[0,0,0,0,.1,2,2]), patch.object(runners.socket,'create_connection',return_value=connection):
            r=runners.acquire(validate_config({}),Path(tmp)/'run','localhost',1,1)
            self.assertEqual(r['metrics']['packets_received'],0)
            self.assertEqual(r['metrics']['stream_timeouts'],0)
            self.assertEqual(r['raw_bytes'],7)

    def test_b14_legacy_bool_version_is_accepted(self):
        self.assertIs(validate_config({'schema_version':True})['schema_version'],True)
