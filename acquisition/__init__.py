"""Capture is transport independent. No simulator ground truth enters this pipeline."""
import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from .. import __version__
from ..protocol import PROFILE, Packet, StreamParser
from ..diagnostics import Diagnostics


def source_digest():
    base = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(base.rglob("*.py")):
        digest.update(path.relative_to(base).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class Capture:
    def __init__(self, out, config, mode, expected=None, record=True, start_s=0.0):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.config = config
        self.mode = mode
        self.parser = StreamParser()
        self.diagnostics = Diagnostics(config["rate_hz"], start_s, expected)
        self.offset = 0
        self.closed = False
        self.record = record
        self.files = []
        self.started = datetime.now(timezone.utc).isoformat()
        self.hash = hashlib.sha256()
        self.wire = self.chunks = self.samples = self.writer = None
        if record:
            self.wire = (self.out / "wire.bin").open("wb")
            self.chunks = (self.out / "chunks.jsonl").open("w", encoding="utf-8")
            self.samples = (self.out / "samples.csv").open("w", newline="", encoding="utf-8")
            self.files = [self.wire, self.chunks, self.samples]
            self.writer = csv.writer(self.samples)
            self.writer.writerow(["received_s", "temperature_slot", *Packet._fields])

    def ingest(self, data, received_s):
        if self.closed:
            raise RuntimeError("Capture already finished")
        if not data:
            return
        self.hash.update(data)
        if self.record:
            self.wire.write(data)
            self.chunks.write(json.dumps({"event": "chunk", "offset": self.offset,
                                          "length": len(data), "received_s": received_s}) + "\n")
        self.offset += len(data)
        for packet in self.parser.feed(data):
            self.diagnostics.observe(packet, received_s)
            if self.record:
                self.writer.writerow([received_s, (packet.counter - 1) % 8, *packet])

    def new_epoch(self, received_s, reconnect=False):
        self.parser.new_epoch()
        self.diagnostics.new_epoch()
        if reconnect:
            self.diagnostics.reconnections += 1
        self.event("connection", received_s, reconnect=reconnect)

    def event(self, kind, received_s, **extra):
        if self.record:
            self.chunks.write(json.dumps(dict(event=kind, received_s=received_s, **extra)) + "\n")

    def timeout(self, received_s):
        self.diagnostics.stream_timeouts += 1
        self.event("stream_timeout", received_s)

    def finish(self, end_s, truth=None, extra=None):
        if self.closed:
            raise RuntimeError("Capture already finished")
        self.closed = True
        self.parser.finish()
        self.event("end", end_s)
        for handle in self.files:
            handle.close()
        report = {
            "simulator_version": __version__, "protocol": PROFILE,
            "source_sha256": source_digest(), "started_utc": self.started,
            "python": platform.python_version(), "platform": platform.platform(),
            "mode": self.mode, "config": self.config, "end_s": end_s,
            "raw_bytes": self.offset, "wire_sha256": self.hash.hexdigest(),
            "raw_recorded": self.record, "metrics": dict(self.diagnostics.report(end_s), **self.parser.stats),
            "simulator_truth": truth, "execution": extra or {},
            "limitations": ["No physical sample timestamps", "Counter8 is ambiguous across wraps, reset and reordering",
                            "Synthetic signals are not an optical physics model", "No firmware execution on MCU"]
        }
        (self.out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        (self.out / "config.resolved.json").write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        m = report["metrics"]
        lines = ["# Resultado FO-IMU testbench", "", f"Modo: {self.mode}; versão {__version__}; contrato {PROFILE}.", "",
                 "| Métrica | Valor |", "|---|---:|"]
        for key in ("packets_expected", "packets_received", "packets_lost", "checksum_errors", "framing_errors",
                    "counter_discontinuities", "duplicates", "resync_events", "reconnections", "stream_timeouts",
                    "jitter_max_s", "largest_gap_without_valid_data_s", "buffer_peak_bytes"):
            lines.append(f"| {key} | {m[key]} |")
        lines += ["", "Perdas são lacunas candidatas do contador; timeouts por sensor e latência física não são observáveis.",
                  "Tempo virtual/acelerado não comprova duração real, ausência de memory leak ou timing do hardware.",
                  "JSON contém estatísticas por canal, temperaturas por slot, configuração, hashes e oráculo separado."]
        (self.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report
