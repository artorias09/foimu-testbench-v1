import json
import math
from pathlib import Path
from .protocol import PROFILE

DEFAULT = {
    "schema_version": 1, "protocol": PROFILE, "seed": 20261028,
    "rate_hz": 100.0, "packets": 1000,
    "chunk_sizes": [1, 7, 19, 53], "stream_timeout_s": 0.25,
    "faults": {"drop_every": 0, "checksum_every": 0, "byte_every": 0,
               "header_every": 0, "truncate_every": 0, "jitter_s": 0.0}
}


def load_config(path=None):
    supplied = {} if path is None else json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_config(supplied)


def validate_config(supplied):
    if not isinstance(supplied, dict):
        raise ValueError("Configuration must be an object")
    unknown = set(supplied) - set(DEFAULT)
    if unknown:
        raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
    config = dict(DEFAULT, **supplied)
    faults = supplied.get("faults", {})
    if not isinstance(faults, dict) or set(faults) - set(DEFAULT["faults"]):
        raise ValueError("Unknown fault keys or invalid faults object")
    config["faults"] = dict(DEFAULT["faults"], **faults)
    if config["schema_version"] != 1 or config["protocol"] != PROFILE:
        raise ValueError("Unsupported schema or protocol")
    for key in ("seed", "packets"):
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    for key in ("rate_hz", "stream_timeout_s"):
        value = config[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be positive and finite")
    chunks = config["chunk_sizes"]
    if not isinstance(chunks, list) or not chunks or any(type(x) is not int or x < 1 or x > 65536 for x in chunks):
        raise ValueError("chunk_sizes must contain integers in [1,65536]")
    for key, value in config["faults"].items():
        if key != "jitter_s" and (type(value) is not int or value < 0):
            raise ValueError(f"{key} must be a nonnegative integer")
    jitter = config["faults"]["jitter_s"]
    if type(jitter) not in (int, float) or not math.isfinite(jitter) or not 0 <= jitter < 0.5 / config["rate_hz"]:
        raise ValueError("jitter_s must be finite, nonnegative and less than half a period")
    return config
