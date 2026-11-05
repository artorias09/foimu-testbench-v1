from dataclasses import replace
import json
import os
import random
import unittest
from unittest.mock import patch

from foimu_testbench.core import ByteSpan
from foimu_testbench.evidence_tree import (
    Check, CheckResult, EvidenceRef, Manifest, Node, MANIFEST_V1, aggregate,
)
from foimu_testbench.observability import REGISTRY

RANK = ('ok', 'not_evaluated', 'unknown', 'warning', 'inconclusive', 'failed')
FRAME = next(s for s in REGISTRY if s.claim.condition == 'valid_frame')


def manifest(names):
    leaves = tuple(Node(n, checks=(Check(n, FRAME),)) for n in names)
    return Manifest('root', (Node('root', required=tuple(names)), *leaves))


def sample(key, status='ok'):
    ref = EvidenceRef(check_id=key, check_version='1', artifact='wire', sample_count=1,
                      coverage=ByteSpan(start=0, end=53), integrity='complete')
    return CheckResult(result=status, reason='test predicate', premises_met=True,
                       violation='constraint breached' if status == 'failed' else None,
                       evidence=[] if status == 'not_evaluated' else [ref])


def rows(m, inputs):
    return {n['node_id']: n for n in json.loads(aggregate(m, inputs))['nodes']}


class EvidenceTests(unittest.TestCase):
    def test_order_and_missing(self):
        m = manifest(('a', 'b'))
        for a in RANK:
            for b in RANK:
                self.assertEqual(rows(m, {'a': sample('a', a), 'b': sample('b', b)})['root']['result'],
                                 max((a, b), key=RANK.index))
        absent = rows(m, {})
        self.assertEqual(set(absent), {'a', 'b', 'root'})
        self.assertTrue(all(n['result'] == 'not_evaluated' for n in absent.values()))
        self.assertEqual(rows(m, {'a': sample('a')})['root']['result'], 'not_evaluated')

    def test_concrete_ref_required(self):
        for state in ('ok', 'warning', 'failed', 'inconclusive'):
            with self.assertRaises(ValueError):
                replace(sample('a', state), evidence=[])

    def test_coverage_and_integrity(self):
        m, good = manifest(('a',)), sample('a')
        ref = good.evidence[0]
        for changed, state in [
            (replace(ref, coverage=None), 'unknown'), (replace(ref, sample_count=0), 'unknown'),
            (replace(ref, integrity='invalid'), 'unknown'), (replace(ref, integrity='partial'), 'unknown'),
            (replace(ref, integrity='partial', confirmed_prefix_end=52), 'unknown'),
            (replace(ref, integrity='partial', confirmed_prefix_end=53), 'ok')]:
            row = rows(m, {'a': replace(good, evidence=[changed])})['root']
            self.assertEqual(row['result'], state)
            if changed.integrity == 'partial':
                self.assertEqual(row['partial_checks'], ['a'])
                self.assertEqual(row['evidence'][0]['coverage'], [0, 53])
        self.assertEqual(rows(m, {'a': replace(good, premises_met=False)})['root']['result'], 'unknown')
        timing = next(s for s in REGISTRY if s.claim.condition == 'byte_silence')
        m = Manifest('a', (Node('a', checks=(Check('a', timing),)),))
        r = replace(ref, artifact='chunks', integrity='partial', confirmed_prefix_end=53)
        self.assertEqual(rows(m, {'a': replace(good, evidence=[r])})['a']['result'], 'unknown')

    def test_limits_and_optional(self):
        m = Manifest('root', (Node('root', ('a',), ('b',), limitations=('first',)),
                              Node('a', checks=(Check('a', FRAME),)), Node('b', limitations=('second',))))
        root = rows(m, {'a': sample('a')})['root']
        self.assertEqual((root['result'], root['limitations'], root['undetected_conditions']),
                         ('ok', ['first', 'second'], 2))
        self.assertIn('loss_multiple_of_256', rows(MANIFEST_V1, {})['FO-IMU']['limitations'])

    def test_truth_independence(self):
        m, inputs = manifest(('a',)), {'a': sample('a')}
        with patch.dict(os.environ, {}, clear=True):
            original = aggregate(m, inputs)
            os.environ['SIMULATOR_TRUTH'] = 'false'
            self.assertEqual(aggregate(m, inputs), original)
        with self.assertRaises(ValueError):
            aggregate(m, dict(inputs, truth='false'))

    def test_heuristic_and_violation(self):
        indicator = next(s for s in REGISTRY if s.claim.condition == 'long_gap')
        with self.assertRaises(ValueError):
            aggregate(Manifest('a', (Node('a', checks=(Check('a', indicator),)),)), {'a': sample('a', 'failed')})
        with self.assertRaises(ValueError):
            replace(sample('a', 'failed'), violation=None)

    def test_generated_trees(self):
        for seed in range(40):
            rng = random.Random(seed)
            for _ in range(50):
                count = rng.randint(2, 9)
                children = [[] for _ in range(count)]
                for i in range(1, count):
                    children[rng.randrange(i)].append(str(i))
                nodes, values = [], {}
                for i, child_list in enumerate(children):
                    key = str(i)
                    nodes.append(Node(key, tuple(child_list), checks=(Check(key, FRAME),)))
                    if rng.random() < .8:
                        values[key] = sample(key, rng.choice(RANK))
                m = Manifest('0', tuple(nodes))
                result = rows(m, values)
                for n in nodes:
                    local = values[n.node_id].result if n.node_id in values else 'not_evaluated'
                    expected = max([local] + [result[k]['result'] for k in n.required], key=RANK.index)
                    self.assertEqual(result[n.node_id]['result'], expected)
                key = str(count - 1)
                self.assertEqual(rows(m, dict(values, **{key: sample(key, 'failed')}))['0']['result'], 'failed')
                removed = dict(values)
                removed.pop(key, None)
                self.assertEqual(rows(m, removed)[key]['result'], 'not_evaluated')
                reversed_nodes = tuple(replace(n, required=n.required[::-1]) for n in reversed(nodes))
                doubled = {k: replace(v, evidence=v.evidence * 2) for k, v in values.items()}
                self.assertEqual(aggregate(m, values), aggregate(Manifest('0', reversed_nodes), doubled))

    def test_structural_conditions_are_detector_relative(self):
        from dataclasses import replace
        blind = next(s for s in REGISTRY if s.claim.condition == 'loss_multiple_of_256')
        # A fictitious formal detector is confined to the aggregation test.
        other = replace(FRAME, claim=replace(FRAME.claim, condition=blind.claim.condition))
        one = Node('first', checks=(Check('blind', blind),))
        two = Node('second', checks=(Check('other', other),))
        m = Manifest('root', (Node('root', ('first', 'second')), one, two))
        result = rows(m, {})
        self.assertEqual(result['first']['undetected_conditions'], 1)
        self.assertEqual(result['root']['undetected_conditions'], 0)
        self.assertIn(blind.claim.condition, result['root']['limitations'])

    def test_minimum_coverage_and_duplicate_reference(self):
        m = Manifest('a', (Node('a', checks=(Check('a', FRAME, 2),)),))
        ok = sample('a')
        self.assertEqual(rows(m, {'a': replace(ok, evidence=ok.evidence*2)})['a']['result'], 'unknown')
        for seed in range(100):
            base = manifest(('a','b'))
            prev = tuple(f'condition-{i}' for i in range(seed % 8))
            def with_limits(limits):
                return replace(base, nodes=(replace(base.nodes[0], limitations=limits), *base.nodes[1:]))
            before = rows(with_limits(prev), {})['root']['limitations']
            after = rows(with_limits(prev + ('additional',)), {})['root']['limitations']
            self.assertEqual(set(after), set(before) | {'additional'})
