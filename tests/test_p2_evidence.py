import hashlib
import json
import random
import unittest
from pathlib import Path
from foimu_testbench.protocol import StreamParser, encode
from foimu_testbench.evidence import ObservedChunk, loads
from foimu_testbench.processing import LocatedParser, Processing, SilenceWatchdogs
from foimu_testbench.emission import VirtualSource
from foimu_testbench.scenarios import import_v1, to_v1
from foimu_testbench.simulator import FakeFOIMU

GOLDEN=(Path(__file__).parent/'fixtures/golden_frame.bin').read_bytes()


class EvidenceTests(unittest.TestCase):
    def test_located_parser_exact_legacy_equivalence(self):
        rng=random.Random(42)
        bad=bytearray(GOLDEN);bad[51]^=1
        wire=b'\xa0'+GOLDEN+bytes(bad)+b'noise'*900+GOLDEN*100+GOLDEN[:20]
        for size in [*range(1,54),4096,65536]:
            events=[]; a=LocatedParser(lambda *e:events.append(e)); b=StreamParser()
            pa=[];pb=[]
            for i in range(0,len(wire),size):
                chunk=wire[i:i+size]
                pa.extend(encode(x[0]) for x in a.feed(chunk));pb.extend(encode(x) for x in b.feed(chunk))
            a.finish();b.finish()
            self.assertEqual(pa,pb)
            self.assertEqual(a.stats,b.stats)
            self.assertEqual(a.cursor,len(wire))
            self.assertTrue(all(0<=start<end<=len(wire) for _,start,end in events))

    def test_frame_spans_and_refs(self):
        p=Processing('r',100,250_000_000)
        p.consume(ObservedChunk.make(b'',ns=0,offset=0,seq=0,kind='epoch'))
        p.consume(ObservedChunk.make(GOLDEN[:10],ns=1,offset=0,seq=1))
        batch=p.consume(ObservedChunk.make(GOLDEN[10:],ns=2,offset=10,seq=2))
        f=loads(next(x.body for x in batch.items if x.path=='observed/frames.jsonl'))
        self.assertEqual(f['byte_span'],{'schema_version':2,'start':0,'end':53})
        self.assertEqual(f['chunk_refs'],[1,2])
        self.assertEqual(f['time']['value'],2)

    def test_epoch_discard_retains_byte_origin_and_detection_time(self):
        p=Processing('r',100,250_000_000)
        p.consume(ObservedChunk.make(b'',ns=0,offset=0,seq=0,kind='epoch'))
        p.consume(ObservedChunk.make(GOLDEN[:10],ns=10,offset=0,seq=1))
        batch=p.consume(ObservedChunk.make(b'',ns=20,offset=10,seq=2,kind='epoch',epoch='1'))
        event=loads(next(x.body for x in batch.items if x.path=='observed/events.jsonl'))
        self.assertEqual(event['kind'],'discard')
        self.assertEqual(event['epoch_id'],'0')
        self.assertEqual(event['byte_span'],{'schema_version':2,'start':0,'end':10})
        self.assertEqual(event['observation_refs'],['chunk:1'])
        self.assertEqual(event['time']['value'],20)
        batch=p.consume(ObservedChunk.make(GOLDEN,ns=30,offset=10,seq=3,epoch='1'))
        frame=loads(next(x.body for x in batch.items if x.path=='observed/frames.jsonl'))
        self.assertEqual(frame['epoch_id'],'1')
        self.assertEqual(frame['byte_span']['start'],10)
        self.assertEqual(frame['chunk_refs'],[3])

    def test_watchdogs_garbage_and_total_silence(self):
        events=[]; w=SilenceWatchdogs(10,lambda *e:events.append(e))
        for ns in range(1,31):
            w.poll(ns);w.arrival('byte_silence',ns)
        self.assertEqual([x[0] for x in events],['valid_frame_silence'])
        w.poll(42)
        self.assertEqual(events[-1][0],'byte_silence')
        self.assertEqual(events[-1][1]['detection_delay_ns'],2)
        events=[];w=SilenceWatchdogs(10,lambda *e:events.append(e));w.poll(12);w.poll(20)
        self.assertEqual(len(events),2)

    def test_ledger_does_not_change_legacy_rng_or_composition(self):
        s=import_v1({'packets':301,'faults':{'jitter_s':.001,'drop_every':10,'checksum_every':10,'byte_every':7,'truncate_every':11}})
        ledger=[];src=VirtualSource(s.to_json(),'r',ledger.append)
        actual=[]
        while (r:=src.read()) is not None:
            if r.data: actual.append(r.data)
        expected=b''.join(x.data for x in FakeFOIMU(to_v1(s)).events())
        self.assertEqual(b''.join(actual),expected)
        faults=[loads(i.body) for b in ledger for i in b.items if i.path=='truth/faults.jsonl']
        self.assertTrue(any(x['payload'].get('result')=='suppressed' for x in faults))
        self.assertTrue(any(x['payload'].get('result')=='applied' for x in faults))

    def test_worker_envelope_rejects_mutable_bytes(self):
        c=ObservedChunk.make(GOLDEN,ns=0,offset=0,seq=0)
        with self.assertRaises(ValueError): ObservedChunk(c.metadata,bytearray(GOLDEN))
        with self.assertRaises(ValueError): ObservedChunk(c.metadata,b'broken')
