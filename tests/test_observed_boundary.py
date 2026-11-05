import json
from pathlib import Path
import shutil
import tempfile
import unittest

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
