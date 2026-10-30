import math
import unittest
from foimu_testbench.diagnostics import Diagnostics
from foimu_testbench.simulator import synthetic_packet


class DiagnosticsTests(unittest.TestCase):
    def make(self, counters, times=None):
        d = Diagnostics(100)
        times = times or [(i + 1) * 0.01 for i in range(len(counters))]
        for counter, t in zip(counters, times):
            d.observe(synthetic_packet(0, 100)._replace(counter=counter), t)
        return d.report(times[-1])

    def test_remove_counter100_oracle(self):
        report = self.make([99, 101, 102])
        self.assertEqual(report["packets_received"], 3)
        self.assertEqual(report["packets_lost"], 1)
        self.assertEqual(report["counter_discontinuities"], 1)

    def test_rollover(self):
        report = self.make([254, 255, 0, 1])
        self.assertEqual(report["packets_lost"], 0)
        self.assertEqual(report["counter_discontinuities"], 0)

    def test_duplicate_not255_losses(self):
        report = self.make([5, 5, 6])
        self.assertEqual(report["duplicates"], 1)
        self.assertEqual(report["packets_lost"], 0)

    def test_out_of_order_does_not_rewind_anchor(self):
        report = self.make([10, 12, 11, 13])
        self.assertEqual(report["out_of_order_or_reset"], 1)
        self.assertEqual(report["packets_lost"], 1)
        self.assertEqual(report["counter_discontinuities"], 2)

    def test_counter_cannot_reveal256_lost(self):
        report = self.make([10, 11], [0.01, 2.58])
        self.assertEqual(report["packets_lost"], 0)
        self.assertAlmostEqual(report["largest_gap_without_valid_data_s"], 2.57)

    def test_known_jitter(self):
        report = self.make([1, 2, 3, 4, 5], [0.011, 0.019, 0.031, 0.039, 0.051])
        self.assertAlmostEqual(report["period_s"]["mean"], 0.01, places=12)
        self.assertAlmostEqual(report["period_s"]["std_population"], 0.002, places=12)
        self.assertAlmostEqual(report["jitter_max_s"], 0.002, places=12)

    def test_nonfinite_does_not_poison_stats(self):
        d = Diagnostics(100)
        for i, value in enumerate((1, float("nan"), float("inf"), 3)):
            d.observe(synthetic_packet(i, 100)._replace(ifog_x=value), (i + 1) / 100)
        stats = d.report(0.04)["sensors"]["ifog_x"]
        self.assertEqual((stats["n_finite"], stats["nan"], stats["inf"], stats["mean"]), (2, 1, 1, 2))

    def test_temperature_slot_and_unknown_timeouts(self):
        report = self.make(list(range(1, 9)))
        self.assertTrue(all(v["n_finite"] == 1 for v in report["temperature_slots"].values()))
        self.assertTrue(all(v is None for v in report["timeouts_by_sensor"].values()))
        self.assertIsNone(report["latency_mean_s"])

    def test_constant_not_declared_failure(self):
        report = self.make([1, 2, 3])
        self.assertEqual(report["sensors"]["ifog_y"]["max_identical_run"], 3)
        self.assertIsNone(report["timeouts_by_sensor"]["ifog_y"])

    def test_tail_gap(self):
        d = Diagnostics(100)
        d.observe(synthetic_packet(0, 100), 0.01)
        self.assertAlmostEqual(d.report(1.01)["largest_gap_without_valid_data_s"], 1)


if __name__ == "__main__":
    unittest.main()
