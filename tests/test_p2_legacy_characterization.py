"""B01/B02 observations in the untouched v1 path, separate from v2 guarantees."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
from foimu_testbench.acquisition import Capture
from foimu_testbench.config import validate_config
from foimu_testbench.protocol import encode
from foimu_testbench.simulator import synthetic_packet


class LegacyP2Characterization(unittest.TestCase):
    def test_b01_ingest_writes_and_parses_in_calling_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Capture(Path(tmp)/'v1',validate_config({}),'test')
            order=[];tid=threading.get_ident();original_feed=c.parser.feed
            c.wire=Mock(write=lambda data:order.append(('wire',threading.get_ident())))
            c.chunks=Mock(write=lambda data:order.append(('chunks',threading.get_ident())))
            def feed(data):
                order.append(('parser',threading.get_ident()))
                yield from original_feed(data)
            c.parser.feed=feed
            c.ingest(encode(synthetic_packet(0,100)),.01)
            self.assertEqual(order,[('wire',tid),('chunks',tid),('parser',tid)])
            c.finish(.01)

    def test_b02_metadata_absent_until_legacy_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'v1';c=Capture(p,validate_config({}),'test')
            c.ingest(encode(synthetic_packet(0,100)),.01)
            self.assertFalse((p/'config.resolved.json').exists())
            self.assertFalse((p/'report.json').exists())
            c.finish(.01)
            self.assertTrue((p/'config.resolved.json').exists())
