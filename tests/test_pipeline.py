import json
import tempfile
import unittest
from pathlib import Path
from foimu_testbench.config import validate_config
from foimu_testbench.runners import demo, replay


class PipelineTests(unittest.TestCase):
    def test_normal_logging_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "original"
            config = validate_config({"packets": 1000})
            original = demo(config, out)
            repeated = replay(config, Path(tmp) / "replay", out / "wire.bin", out / "chunks.jsonl")
            self.assertEqual(original["wire_sha256"], repeated["wire_sha256"])
            for name in ("packets_received", "checksum_errors", "period_s", "sensors", "largest_gap_without_valid_data_s"):
                self.assertEqual(original["metrics"][name], repeated["metrics"][name])
            self.assertEqual((out / "wire.bin").stat().st_size, 53000)
            self.assertEqual(original["metrics"]["packets_received"], 1000)

    def test_faults_with_explicit_oracles(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("checksum_every", "byte_every", "header_every", "truncate_every"):
                config = validate_config({"packets": 1001, "faults": {name: 10}})
                report = demo(config, Path(tmp) / name, False)
                self.assertEqual(report["metrics"]["packets_received"], 901)
                # At counter=0xA0, A0 A0 A0 forms an overlapping candidate after damage.
                self.assertEqual(report["metrics"]["checksum_errors"], 1 if name == "header_every" else 101)
                self.assertEqual(report["metrics"]["framing_errors"], 100)
                self.assertEqual(report["metrics"]["resync_events"], 100)

    def test_drop_every10(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = validate_config({"packets": 1001, "faults": {"drop_every": 10}})
            report = demo(config, Path(tmp) / "run", False)
            self.assertEqual(report["simulator_truth"]["dropped"], 100)
            self.assertEqual(report["metrics"]["packets_lost"], 100)
            self.assertEqual(report["metrics"]["packets_received"], 901)
            self.assertEqual(report["metrics"]["checksum_errors"], 0)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                demo(validate_config({}), tmp)

    def test_seed_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = validate_config({"packets": 300, "faults": {"jitter_s": 0.001}})
            a = demo(config, Path(tmp) / "a")
            b = demo(config, Path(tmp) / "b")
            self.assertEqual(a["metrics"], b["metrics"])
            self.assertEqual((Path(tmp) / "a/chunks.jsonl").read_bytes(), (Path(tmp) / "b/chunks.jsonl").read_bytes())

    def test_invalid_configs_rejected(self):
        for config in ({"faults": {"cheksum_every": 10}}, {"unknown": 1}, {"rate_hz": 0},
                       {"rate_hz": float("nan")}, {"packets": -1}, {"chunk_sizes": []},
                       {"faults": {"jitter_s": 0.2}}):
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_broken_replay_timeline_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wire.bin").write_bytes(b"abc")
            (root / "chunks.jsonl").write_text(json.dumps(dict(event="chunk", received_s=0.01, offset=1, length=3))+"\n")
            with self.assertRaises(ValueError):
                replay(validate_config({}), root / "replay", root / "wire.bin", root / "chunks.jsonl")


if __name__ == "__main__":
    unittest.main()
