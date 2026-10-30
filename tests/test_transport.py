import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from foimu_testbench.config import validate_config
from foimu_testbench.runners import acquire, replay
from foimu_testbench.simulator import synthetic_packet
from foimu_testbench.protocol import encode

ROOT = Path(__file__).resolve().parents[1]


class TransportTests(unittest.TestCase):
    def test_two_processes_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = subprocess.Popen([sys.executable, "-u", "-m", "foimu_testbench", "simulate",
                "--port", "0", "--packets", "80", "--disconnect-at", "40"],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ready = queue.Queue()
            reader = threading.Thread(target=lambda: ready.put(server.stdout.readline()), daemon=True)
            reader.start()
            try:
                line = ready.get(timeout=10)
                self.assertTrue(line.startswith("READY "), line)
                port = int(line.split()[1].split(":")[-1])
                report = acquire(validate_config({}), Path(tmp) / "capture", "127.0.0.1", port, 3, 80)
                server.communicate(timeout=10)
                self.assertEqual(server.returncode, 0)
                metrics = report["metrics"]
                self.assertEqual(metrics["packets_received"], 80)
                self.assertEqual(metrics["reconnections"], 1)
                self.assertEqual(metrics["checksum_errors"], 0)
                self.assertEqual(metrics["packets_lost"], 0)
                replayed = replay(validate_config({}), Path(tmp) / "replay",
                                  Path(tmp) / "capture/wire.bin", Path(tmp) / "capture/chunks.jsonl")
                self.assertEqual(metrics, replayed["metrics"])
            finally:
                if server.poll() is None:
                    server.terminate()
                server.communicate(timeout=10)

    def test_silence_timeout_then_data_recovers_without_disconnect(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        errors = []

        def device():
            try:
                listener.settimeout(5)
                with listener.accept()[0] as connection:
                    connection.sendall(encode(synthetic_packet(0, 100)))
                    time.sleep(0.12)
                    connection.sendall(encode(synthetic_packet(1, 100)))
            except BaseException as exc:
                errors.append(exc)
            finally:
                listener.close()

        port = listener.getsockname()[1]
        thread = threading.Thread(target=device, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory() as tmp:
            report = acquire(validate_config({"stream_timeout_s": 0.03}), Path(tmp) / "capture", "127.0.0.1", port, 2, 2)
            thread.join(timeout=5)
            self.assertFalse(errors, errors)
            self.assertEqual(report["metrics"]["packets_received"], 2)
            self.assertEqual(report["metrics"]["stream_timeouts"], 1)
            self.assertEqual(report["metrics"]["reconnections"], 0)
            self.assertGreaterEqual(report["metrics"]["largest_gap_without_valid_data_s"], 0.1)


if __name__ == "__main__":
    unittest.main()
