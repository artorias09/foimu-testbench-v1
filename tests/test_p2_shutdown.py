"""Controlled worker lifecycle: no wall-clock waits or background threads."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from foimu_testbench.backend import RunController, BackendOptions
from foimu_testbench.processing import Processing
from foimu_testbench.scenarios import import_v1


class ShutdownBudgetTests(unittest.TestCase):
    def exercise(self):
        now = [0]
        budgets = {}
        with tempfile.TemporaryDirectory() as tmp:
            c = RunController(import_v1({'packets': 0}), Path(tmp)/'run',
                              options=BackendOptions(shutdown_timeout_ns=1_000_000_000))
            class Worker:
                def __init__(self, target, name, daemon):
                    self.name = name.removeprefix('foimu-')
                    self.alive = True
                    self.interrupt = self.name == 'rx'
                def start(self):
                    if self.name == 'processing':
                        c.processing = Processing(c.run_id, 100, 250_000_000)
                        c.processing.ended = True
                def is_alive(self):
                    if self.interrupt:
                        self.interrupt = False
                        raise KeyboardInterrupt
                    return self.alive
                def join(self, timeout):
                    budgets[self.name] = timeout
                    required = .5 if self.name == 'writer' else .9
                    now[0] += round(min(timeout, required)*1e9)
                    self.alive = timeout < required
                    if self.name == 'writer' and not self.alive:
                        c.writer.close()
            with patch('foimu_testbench.backend.Thread', Worker), patch(
                    'foimu_testbench.backend.time.monotonic_ns', side_effect=lambda: now[0]):
                result = c.execute()
            return budgets, result

    def test_independent_budgets_allow_healthy_writer_to_drain(self):
        budgets, run = self.exercise()
        self.assertAlmostEqual(budgets['rx'], 1)
        self.assertAlmostEqual(budgets['processing'], 1)
        self.assertEqual(budgets['writer'], 1)
        self.assertEqual((run.execution_status, run.integrity_status), ('cancelled', 'complete'))
