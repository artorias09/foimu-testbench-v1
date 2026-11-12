import ast
from importlib.util import resolve_name
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from foimu_testbench.evidence import dumps, loads
from foimu_testbench.observed_analysis import PATHS, canonical_metrics, canonical_record, reanalyze_observed
from foimu_testbench.observed_input import open_observed, project_run, ObservedProjection
from foimu_testbench.processing import Processing

from foimu_testbench.backend import RunController
from foimu_testbench.replay import replay_run
from foimu_testbench.scenarios import import_v1


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.live = self.root / 'live'
        self.scenario = import_v1({'packets': 32, 'faults': {'checksum_every': 5}})
        RunController(self.scenario, self.live).execute()

    def variant(self, mode):
        copy = self.root / mode
        shutil.copytree(self.live, copy)
        if mode == 'removed':
            shutil.rmtree(copy / 'truth')
        else:
            summary = copy / 'truth/summary.jsonl'
            row = json.loads(summary.read_bytes())
            row['opportunities'] = 999
            summary.write_text(json.dumps(row) + '\n', encoding='utf8')
        return copy

    def test_full_replay_requires_original_truth(self):
        for mode in ('removed', 'poisoned'):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'truth/'):
                replay_run(self.variant(mode), self.root / 'out')

    def live_result(self, source):
        result = {}
        for path, group in PATHS.items():
            file = source / path
            rows = file.read_bytes().splitlines() if file.exists() else []
            result[group + '.jsonl'] = b''.join(dumps(canonical_record(group, loads(row))) + b'\n'
                                               for row in rows)
        metrics = loads((source / 'diagnostics/metrics.json').read_bytes())['metrics']
        result['metrics.json'] = dumps(canonical_metrics(metrics)) + b'\n'
        return result

    def file_result(self, directory, spec):
        with open_observed(directory, spec) as view, reanalyze_observed(view) as output:
            self.assertEqual(output.observed_integrity, 'complete')
            return {p.name: p.read_bytes() for p in output.directory.iterdir()}

    def test_file_source_uses_only_two_files_and_projection(self):
        spec = project_run(self.live)
        src = self.root / 'isolated'
        src.mkdir()
        for name in ('wire.bin', 'chunks.jsonl'):
            shutil.copy(self.live / 'observed' / name, src / name)
        self.assertEqual(self.live_result(self.live), self.file_result(src, ObservedProjection.from_json(spec.to_json())))
        self.assertEqual(set(spec.to_dict()), {'schema_version', 'protocol_profile', 'rate_hz',
                                               'timeout_ns', 'wire', 'chunks'})

    def test_without_truth_or_scenario(self):
        spec = project_run(self.live)
        copy = self.variant('removed')
        (copy / 'scenario.resolved.json').unlink()
        self.assertEqual(self.live_result(self.live), self.file_result(copy / 'observed', spec))

    def test_poisoned_truth(self):
        copy = self.variant('poisoned')
        self.assertEqual(self.live_result(self.live), self.file_result(copy / 'observed', project_run(copy)))

    def test_modified_inputs_rejected(self):
        for name in ('wire.bin', 'chunks.jsonl'):
            directory = self.root / name
            shutil.copytree(self.live / 'observed', directory)
            file = directory / name
            if name == 'wire.bin':
                file.write_bytes(bytes([file.read_bytes()[0] ^ 1]) + file.read_bytes()[1:])
            else:
                file.write_bytes(file.read_bytes().replace(b'"value":0', b'"value":1', 1))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.file_result(directory, project_run(self.live))

    def test_counter_episode_file_source(self):
        from foimu_testbench.emission import IterableSource, ReadResult
        from foimu_testbench.protocol import encode
        from foimu_testbench.simulator import synthetic_packet

        src = self.root / 'counter'
        packet = synthetic_packet(0, 100)
        reads = [ReadResult(encode(packet._replace(counter=c)), i*10_000_000)
                 for i, c in enumerate([*range(10), *range(200, 240)])]
        RunController(self.scenario, src, source_factory=lambda *_: IterableSource(reads)).execute()
        canonical = self.file_result(src / 'observed', project_run(src))
        self.assertEqual(canonical, self.live_result(src))
        events = list(map(loads, canonical['diagnostic_events.jsonl'].splitlines()))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['payload']['interpretation'], 'ambiguous_jump')
        raw = loads((src / 'diagnostics/events.jsonl').read_bytes())
        self.assertEqual(raw['payload']['cause_status'], 'inconclusive')
        self.assertIsNone(raw['payload']['candidate_missing'])
        metrics = loads((src / 'diagnostics/metrics.json').read_bytes())['metrics']
        self.assertEqual((metrics['counter_ambiguous_jumps'], metrics['counter_reacquisitions'],
                          metrics['packets_lost']), (1, 1, 0))

    def test_zero_byte_complete_stream(self):
        src = self.root / 'empty'
        RunController(import_v1({'packets': 0}), src).execute()
        self.assertEqual(self.live_result(src), self.file_result(src / 'observed', project_run(src)))

    def test_time_and_epoch_differential(self):
        from foimu_testbench.emission import IterableSource, ReadResult
        from foimu_testbench.protocol import encode
        from foimu_testbench.simulator import synthetic_packet

        src = self.root / 'timed'
        frame = encode(synthetic_packet(0, 100))
        reads = [ReadResult(frame, 1), ReadResult(frame[:10], 5),
                 ReadResult(b'', 300_000_000, 'epoch', '1'),
                 ReadResult(frame, 700_000_000, epoch='1')]
        RunController(self.scenario, src, source_factory=lambda *_: IterableSource(reads)).execute()
        result = self.file_result(src / 'observed', project_run(src))
        self.assertEqual(result, self.live_result(src))
        metrics = loads(result['metrics.json'])['metrics']
        self.assertEqual(metrics['reconnections'], 1)
        self.assertGreater(metrics['valid_frame_silence_episodes'], 0)
        self.assertGreater(metrics['jitter_max_s'], .6)

    def test_partial_reference_refused(self):
        file = self.live / 'run.json'
        run = loads(file.read_bytes())
        next(a for a in run['artifacts'] if a['path'] == 'observed/chunks.jsonl')['integrity'] = 'partial'
        file.write_bytes(dumps(run))
        with self.assertRaisesRegex(ValueError, 'parcial'):
            project_run(self.live)

    def test_live_truth_mutant_killed_by_file_source(self):
        src = self.root / 'mutant'
        original = Processing.metrics

        def contaminated(processing):
            result = original(processing)
            truth = loads((src / 'truth/summary.jsonl').read_bytes())
            result['checksum_errors'] += truth['opportunities']
            return result

        with patch.object(Processing, 'metrics', contaminated):
            RunController(self.scenario, src).execute()
        live = self.live_result(src)
        file = self.file_result(src / 'observed', project_run(src))
        self.assertEqual(loads(live['metrics.json'])['metrics']['checksum_errors'] -
                         loads(file['metrics.json'])['metrics']['checksum_errors'], 32)
        with self.assertRaises(AssertionError):
            self.assertEqual(live, file)


class ImportBoundaryTests(unittest.TestCase):
    def test_static_observed_import_closure(self):
        pkg = 'foimu_testbench'
        root = Path(__file__).resolve().parents[1] / pkg
        modules = ('', 'observed_input', 'observed_analysis', 'evidence_tree', 'observability', 'evidence', 'processing',
                   'diagnostics', 'diagnostics.counter', 'protocol', 'protocol.gateway53', 'core', 'core.contracts', 'core.schema')
        allowed = {pkg + ('.' + name if name else '') for name in modules}
        for name in modules:
            path = root.joinpath(*name.split('.'))
            package = path.is_dir()
            source = path / '__init__.py' if package else path.with_suffix('.py')
            module = pkg + ('.' + name if name else '')
            for node in ast.walk(ast.parse(source.read_text(encoding='utf8'))):
                if isinstance(node, ast.ImportFrom):
                    parent = module if package else module.rpartition('.')[0]
                    target = resolve_name('.' * node.level + (node.module or ''), parent)
                    targets = [target]
                    for alias in node.names:
                        child = target + '.' + alias.name
                        candidate = root.parent.joinpath(*child.split('.'))
                        if candidate.is_dir() or candidate.with_suffix('.py').is_file():
                            targets.append(child)
                elif isinstance(node, ast.Import):
                    targets = [a.name for a in node.names]
                else:
                    continue
                for target in targets:
                    if target == pkg or target.startswith(pkg + '.'):
                        self.assertIn(target, allowed, msg=f'{module} importa {target}')
