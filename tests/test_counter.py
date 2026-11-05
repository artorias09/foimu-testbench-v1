import unittest

from foimu_testbench.diagnostics import Diagnostics
from foimu_testbench.simulator import synthetic_packet


class CounterTests(unittest.TestCase):
    def observe(self, values):
        diag = Diagnostics(100)
        packet = synthetic_packet(0, 100)
        for i, value in enumerate(values):
            diag.observe(packet._replace(counter=value), i / 100)
        return diag

    def test_pairs(self):
        # before, current, delta, candidate, duplicate, ambiguity, after
        rows = [(0, 1, 1, 0, 0, 0, 1), (255, 0, 1, 0, 0, 0, 0),
                (10, 10, 0, 0, 1, 0, 10), (10, 11, 1, 0, 0, 0, 11),
                (10, 12, 2, 1, 0, 0, 12), (10, 137, 127, 126, 0, 0, 137),
                (10, 138, 128, 0, 0, 1, None), (10, 139, 129, 0, 0, 1, None)]
        for before, current, delta, lost, duplicate, ambiguity, after in rows:
            with self.subTest(current=current):
                self.assertEqual(self.observe([before]).counter, before)
                self.assertEqual((current - before) % 256, delta)
                d = self.observe([before, current])
                self.assertEqual((d.lost, d.duplicates, d.order_or_reset, d.counter),
                                 (lost, duplicate, ambiguity, after))

    def test_stale_sequence(self):
        d = self.observe([*range(10), *range(200, 240)])
        self.assertEqual((d.received, d.discontinuities, d.order_or_reset, d.counter, d.lost),
                         (50, 1, 1, 239, 0))
