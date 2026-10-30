import copy
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from foimu_testbench.core import (
    AcceptanceCriterion, ArtifactReference, ByteSpan, ClockDefinition, CodeIdentity,
    EvaluationResult, Event, Fidelity, Provenance, Reference, Run, TimePoint,
    elapsed_ns, evaluate,
)
from foimu_testbench.core.contracts import TRANSITIONS
from foimu_testbench.scenarios import Scenario, import_v1, load_v1, to_v1, ScheduledAction
from foimu_testbench.provenance import collect_identity, new_run
from foimu_testbench.config import load_config
from foimu_testbench.protocol import encode, decode, StreamParser
from foimu_testbench.simulator import FakeFOIMU

ROOT=Path(__file__).resolve().parents[1]
BASELINE='52531eaa16bb111cdb6ad862c8fd037d6ead0977'


def identity():
    return CodeIdentity(app_version='test',python='3.12',os='test',architecture='test',
        collected_at=TimePoint(clock_id='utc',meaning='catalog',value=0),
        git_status='unavailable',unavailable_reason='Teste sem Git')


def run():
    return Run(run_id='r',scenario_id='s',code_identity=identity(),
        clocks=[ClockDefinition(clock_id='utc',kind='utc_catalog')],
        fidelity=[Fidelity(component='output',level='L1')])


class SchemaTests(unittest.TestCase):
    def test_all_models_json_roundtrip(self):
        samples=[identity(),run(),import_v1({}),ClockDefinition(clock_id='x',kind='unknown'),
            TimePoint(clock_id='x',meaning='unknown',value=None),ByteSpan(start=0,end=1),
            Event(event_id='e',run_id='r',producer_id='p',producer_seq=0,domain='observed',epistemic_status='observed_fact',kind='received',component_path='FO-IMU/Host'),
            ArtifactReference(artifact_id='a',path='observed/wire.bin',domain='observed'),
            Reference(reference_id='ref',kind='code',title='Fonte'),
            Provenance(provenance_id='p',target_path='rate',origin_kind='synthetic'),
            AcceptanceCriterion(criterion_id='c',metric='frames',domain='observed',operator='ge',expected=1,unit='frames'),
            EvaluationResult(criterion_id='c',status='inconclusive',evidence_count=0,reason='Sem dados'),
            Fidelity(component='sensor',level='L0')]
        for m in samples:
            with self.subTest(model=type(m).__name__):
                self.assertEqual(type(m).from_json(m.to_json()),m)
                self.assertEqual(m.to_json(),type(m).from_dict(dict(reversed(list(m.to_dict().items())))).to_json())
                bad=m.to_dict();bad['surprise']=1
                with self.assertRaises(ValueError): type(m).from_dict(bad)
                bad=m.to_dict();bad['schema_version']=True
                with self.assertRaises(ValueError): type(m).from_dict(bad)
                bad=m.to_dict();del bad['schema_version']
                with self.assertRaises(ValueError): type(m).from_dict(bad)

    def test_invalid_nested_scenarios(self):
        data=import_v1({}).to_dict()
        mutations=[lambda d:d.update(seed=True),lambda d:d.update(seed=-1),
            lambda d:d.update(signals='physical'),lambda d:d['rate'].update(value='100'),
            lambda d:d['rate'].update(unit='seconds'),lambda d:d['rate'].update(value=float('inf')),
            lambda d:d['fragmentation'].update(chunk_sizes=[True]),lambda d:d['fragmentation'].update(chunk_sizes=[]),
            lambda d:d['fidelity'].update(level='L2'),lambda d:d['fidelity'].update(electrical='measured'),
            lambda d:d['stop_condition'].update(count=True),lambda d:d['transport'].update(kind='serial'),
            lambda d:d['fault_rules'][0].update(every=True),lambda d:d.update(clock_mode='unknown'),
            lambda d:d['resource_limits'].update(max_memory_bytes=-1),lambda d:d['diagnostic_policy'].update(unknown=1)]
        for mutate in mutations:
            bad=copy.deepcopy(data); mutate(bad)
            with self.subTest(data=bad),self.assertRaises(ValueError): Scenario.from_dict(bad)

    def test_json_nonfinite_duplicate_keys_and_python_payload_rejected(self):
        with self.assertRaises(ValueError): ByteSpan.from_json('{"schema_version":2,"start":0,"start":1,"end":2}')
        with self.assertRaises(ValueError): TimePoint.from_json('{"schema_version":2,"value":NaN}')
        for value in (b'bytes',object(),float('nan'),{1:'bad'}):
            with self.assertRaises(ValueError): Provenance(provenance_id='p',target_path='x',origin_kind='unknown',raw_value=value)

    def test_byte_spans(self):
        self.assertEqual(ByteSpan(start=0,end=53).end,53)
        for start,end in ((-1,53),(0,0),(53,0),(True,53),(0,False),(0,1.0)):
            with self.subTest(start=start,end=end),self.assertRaises(ValueError): ByteSpan(start=start,end=end)

    def test_event_truth_observed_independent(self):
        observed=Event(event_id='e',run_id='r',producer_id='p',producer_seq=0,domain='observed',epistemic_status='observed_fact',kind='chunk',component_path='FO-IMU/Host')
        truth=replace(observed,event_id='t',domain='truth',epistemic_status='simulator_truth',payload={'dropped':1})
        self.assertNotEqual(observed.to_json(),truth.to_json())
        with self.assertRaises(ValueError): replace(observed,epistemic_status='simulator_truth')
        with self.assertRaises(ValueError): replace(truth,epistemic_status='observed_fact')
        with self.assertRaises(ValueError): replace(observed,producer_seq=True)
        with self.assertRaises(ValueError): replace(observed,byte_span=ByteSpan(start=0,end=53))
        span=replace(observed,stream_id='wire',epoch_id='0',byte_span=ByteSpan(start=0,end=53))
        self.assertEqual(span.byte_span.start,0)
        self.assertIsNone(observed.time)

    def test_event_run_and_clock_registry(self):
        r=run()
        e=Event(event_id='e',run_id='r',producer_id='p',producer_seq=0,domain='observed',epistemic_status='observed_fact',kind='received',component_path='FO-IMU/Host')
        r.validate_event(e)
        with self.assertRaises(ValueError): r.validate_event(replace(e,run_id='other'))
        with self.assertRaises(ValueError): r.validate_event(replace(e,time=TimePoint(clock_id='missing',meaning='host_receive',value=0)))
        with self.assertRaises(ValueError): replace(r,clocks=[])

    def test_artifact_paths_and_hash(self):
        for path in ('../wire','/wire','C:\\wire','a/../../b'):
            with self.assertRaises(ValueError): ArtifactReference(artifact_id='a',path=path,domain='observed')
        with self.assertRaises(ValueError): Reference(reference_id='x',kind='code',title='x',sha256='bad')


class ClockTests(unittest.TestCase):
    def test_explicit_domains_and_intervals(self):
        for kind in ('virtual','monotonic_local','utc_catalog','unknown'):
            ClockDefinition(clock_id=kind,kind=kind)
        clock=ClockDefinition(clock_id='v',kind='virtual')
        a=TimePoint(clock_id='v',meaning='host_receive',value=10)
        b=replace(a,value=20)
        self.assertEqual(elapsed_ns(a,b,clock),10)
        for wrong in (replace(b,clock_id='another'),replace(b,meaning='physical_sample'),replace(b,value=None),replace(b,value=0)):
            with self.assertRaises(ValueError): elapsed_ns(a,wrong,clock)
        with self.assertRaises(ValueError): elapsed_ns(a,b,replace(clock,kind='unknown'))
        with self.assertRaises(ValueError): elapsed_ns(a,b,replace(clock,kind='utc_catalog'))
        with self.assertRaises(ValueError): replace(a,value=True)
        with self.assertRaises(ValueError): replace(a,uncertainty_ns=-1)
        self.assertIsNone(a.uncertainty_ns)


class LifecycleTests(unittest.TestCase):
    def test_normal_chain_does_not_approve(self):
        r=run()
        for status in ('validated','prepared','armed','running','stopping','finalizing','completed'):
            r=r.transition(status)
            self.assertEqual(r.evaluation_status,'not_evaluated')
            self.assertEqual(r.integrity_status,'unknown')
        with self.assertRaises(ValueError): replace(r,evaluation_status='passed',integrity_status='complete')

    def test_every_allowed_and_forbidden_edge(self):
        for source,allowed in TRANSITIONS.items():
            r=replace(run(),execution_status=source,stop_reason='Teste')
            for target in TRANSITIONS:
                with self.subTest(source=source,target=target):
                    if target in allowed:
                        self.assertEqual(r.transition(target,'Teste').execution_status,target)
                    else:
                        with self.assertRaises(ValueError): r.transition(target,'Teste')

    def test_cancel_requires_reason(self):
        with self.assertRaises(ValueError): run().transition('cancelled')

    def test_no_evidence_never_passes(self):
        c=AcceptanceCriterion(criterion_id='c',metric='checksum',domain='observed',operator='eq',expected=0,unit='candidates')
        self.assertEqual(evaluate(c,0,0).status,'inconclusive')
        self.assertEqual(evaluate(c,None,10).status,'inconclusive')
        with self.assertRaises(ValueError): EvaluationResult(criterion_id='c',status='passed',evidence_count=0,observed=0,reason='Erro')
        with self.assertRaises(ValueError): evaluate(c,0,True)

    def test_approval_checks_criterion_and_integrity(self):
        c=AcceptanceCriterion(criterion_id='c',metric='frames',domain='observed',operator='ge',expected=10,unit='frames')
        good=evaluate(c,10,10)
        r=replace(run(),execution_status='completed',integrity_status='complete',criteria=[c],results=[good],evaluation_status='passed')
        self.assertEqual(r.evaluation_status,'passed')
        for bad in (dict(execution_status='running'),dict(integrity_status='partial'),dict(results=[]),dict(results=[replace(good,observed=0)])):
            with self.assertRaises(ValueError): replace(r,**bad)


class ImportIdentityCompatibilityTests(unittest.TestCase):
    def test_every_config_roundtrip_and_deterministic_bytes(self):
        for path in sorted((ROOT/'configs').glob('*.json')):
            original=path.read_bytes()
            scenario=load_v1(path)
            cfg=load_config(path)
            self.assertEqual(to_v1(scenario),cfg)
            self.assertEqual(path.read_bytes(),original)
            self.assertTrue(scenario.imported_from.normalizations)
            # Limit count without changing the formulas, fault ordering or RNG.
            a=dict(cfg,packets=300);b=dict(to_v1(scenario),packets=300)
            self.assertEqual(list(FakeFOIMU(a).events()),list(FakeFOIMU(b).events()))
            self.assertEqual(Scenario.from_json(scenario.to_json()),scenario)

    def test_import_does_not_accept_bool_version_or_mutate_input(self):
        with self.assertRaises(ValueError): import_v1({'schema_version':True})
        cfg={'chunk_sizes':[1,2]}; s=import_v1(cfg)
        cfg['chunk_sizes'].append(3)
        self.assertEqual(s.fragmentation.chunk_sizes,[1,2])
        self.assertEqual(import_v1({}).to_json(),import_v1({}).to_json())

    def test_actions_are_contracts_not_silently_projected(self):
        s=import_v1({})
        action=ScheduledAction(action_id='a',at_opportunity=10,rule_id='drop_every',enabled=True,sequence_id=0)
        s=replace(s,scheduled_actions=[action])
        with self.assertRaises(ValueError): to_v1(s)
        with self.assertRaises(ValueError): replace(s,scheduled_actions=[replace(action,rule_id='absent')])

    def test_identity_without_git_and_draft_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp,patch('foimu_testbench.provenance.subprocess.run',side_effect=FileNotFoundError):
            r=new_run(import_v1({}),tmp,run_id='r')
            self.assertEqual(r.code_identity.git_status,'unavailable')
            self.assertIsNone(r.code_identity.commit)
            self.assertTrue(r.code_identity.unavailable_reason)
            self.assertEqual(r.execution_status,'draft')
            self.assertEqual(list(Path(tmp).iterdir()),[])
            self.assertEqual(r.transition('validated').code_identity,r.code_identity)

    def test_git_identity_dirty_and_hash_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'foimu_testbench').mkdir();(p/'foimu_testbench/x.py').write_text('x=1')
            def git(*args): return subprocess.run(['git','-C',tmp,*args],check=True,capture_output=True,text=True)
            try: git('init')
            except FileNotFoundError: self.skipTest('Git indisponível')
            git('add','.');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
            a=collect_identity(p);self.assertFalse(a.dirty)
            (p/'foimu_testbench/x.py').write_text('x=2')
            b=collect_identity(p);self.assertTrue(b.dirty)
            self.assertEqual(a.commit,b.commit);self.assertNotEqual(a.hashes,b.hashes)

    def test_golden_all_splits_resync_after_contract_imports(self):
        golden=(ROOT/'tests/fixtures/golden_frame.bin').read_bytes()
        self.assertEqual(encode(decode(golden)),golden)
        damaged=bytearray(golden);damaged[51]^=1
        for split in range(1,53):
            p=StreamParser();packets=list(p.feed(damaged+golden[:split]))+list(p.feed(golden[split:]))
            self.assertEqual([encode(x) for x in packets],[golden])
            self.assertEqual(p.stats['checksum_errors'],1)
            self.assertEqual(p.stats['resync_events'],1)

    def test_legacy_sources_are_exact_frozen_blobs(self):
        # Optional Git check complements portable golden tests in archive distributions.
        try:
            subprocess.run(['git','cat-file','-e',BASELINE],cwd=ROOT,check=True,capture_output=True)
        except (FileNotFoundError,subprocess.CalledProcessError): self.skipTest('Snapshot Git ausente')
        for path in ('foimu_testbench/protocol/gateway53.py','foimu_testbench/runners.py','foimu_testbench/config.py','foimu_testbench/simulator/__init__.py','foimu_testbench/diagnostics/__init__.py','tools/acceptance.py'):
            old=subprocess.check_output(['git','show',f'{BASELINE}:{path}'],cwd=ROOT)
            self.assertEqual((ROOT/path).read_bytes().replace(b'\r\n', b'\n'),old.replace(b'\r\n', b'\n'),path)
