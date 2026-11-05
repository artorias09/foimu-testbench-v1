import hashlib
import json
from pathlib import Path
import unittest

from foimu_testbench.observed_analysis import reanalyze_observed
from foimu_testbench.observed_input import open_observed, ObservedProjection


class CorpusTests(unittest.TestCase):
    def test_observed_goldens(self):
        root = Path(__file__).parent / 'corpus'
        for name in ('normal', 'counter', 'checksum', 'epoch', 'truncated'):
            with self.subTest(case=name):
                case = root / name
                meta = json.loads((case / 'metadata.json').read_bytes())
                self.assertEqual((meta['id'], meta['version']), (name, 1))
                outputs = {'frames.jsonl', 'diagnostic_events.jsonl', 'observed_events.jsonl', 'metrics.json'}
                self.assertEqual(set(meta['sha256']), outputs | {'wire.bin', 'chunks.jsonl'})
                for key, expected in meta['sha256'].items():
                    self.assertEqual(hashlib.sha256((case / key).read_bytes()).hexdigest(), expected)
                spec = ObservedProjection.from_dict(meta['profile'])
                with open_observed(case, spec) as view, reanalyze_observed(view) as result:
                    for key in outputs:
                        self.assertEqual((result.directory / key).read_bytes(), (case / key).read_bytes())
