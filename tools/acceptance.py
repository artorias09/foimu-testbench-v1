"""Run from project root: python -m tools.acceptance --out logs/acceptance."""
import argparse
import json
import time
import unittest
from pathlib import Path
from foimu_testbench.config import validate_config
from foimu_testbench.runners import demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--packets", type=int, default=1000000)
    args = parser.parse_args()
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    with (root / "unittest.txt").open("w", encoding="utf-8") as stream:
        suite = unittest.defaultTestLoader.discover("tests")
        results = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not results.wasSuccessful():
        raise SystemExit("Unit/integration tests failed; see unittest.txt")
    config = validate_config({"packets": args.packets, "chunk_sizes": [53]})
    report = demo(config, root / "normal", record=False)
    m = report["metrics"]
    assert m["packets_received"] == args.packets
    for key in ("packets_lost", "checksum_errors", "framing_errors", "counter_discontinuities", "duplicates", "truncated_tails"):
        assert m[key] == 0, (key, m[key])
    cases = {}
    for name, faults in (("checksum", {"checksum_every": 10}), ("loss", {"drop_every": 10}),
                         ("truncate", {"truncate_every": 10}), ("header", {"header_every": 10}),
                         ("byte", {"byte_every": 10}), ("jitter", {"jitter_s": 0.001})):
        case = demo(validate_config({"packets": 1001, "faults": faults}), root / name)
        cases[name] = {key: case["metrics"][key] for key in ("packets_received", "packets_lost", "checksum_errors", "framing_errors", "resync_events", "jitter_max_s")}
    summary = {"passed": True, "unit_integration_tests": results.testsRun,
               "normal_packets": args.packets, "normal_metrics": {key:m[key] for key in ("packets_received", "packets_lost", "checksum_errors", "framing_errors", "buffer_peak_bytes")},
               "elapsed_wall_s": time.perf_counter()-start, "scenarios": cases,
               "source_sha256": report["source_sha256"], "python": report["python"],
               "platform": report["platform"], "not_validated": ["Windows USB/COM", "real 8-hour soak", "STM32 timing", "sensor-level HIL", "installed IEAv revision"]}
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
