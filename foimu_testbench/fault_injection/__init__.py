"""Deterministic byte faults; sensor-response faults require a later gateway model."""
import random


class Injector:
    def __init__(self, config, seed):
        self.config = config
        self.random = random.Random(seed)
        self.counts = {name: 0 for name in ("dropped", "checksum", "byte", "header", "truncated")}

    def apply(self, index, frame, due_s):
        n = index + 1
        hit = lambda name: self.config[name] > 0 and n % self.config[name] == 0
        jitter = self.config["jitter_s"]
        delivery_s = due_s + (self.random.uniform(-jitter, jitter) if jitter else 0)
        if hit("drop_every"):
            self.counts["dropped"] += 1
            return b"", delivery_s
        data = bytearray(frame)
        if hit("checksum_every"):
            data[51] ^= 1
            self.counts["checksum"] += 1
        if hit("byte_every"):
            data[7] ^= 1
            self.counts["byte"] += 1
        if hit("header_every"):
            data[0] ^= 1
            self.counts["header"] += 1
        if hit("truncate_every"):
            del data[20:]
            self.counts["truncated"] += 1
        return bytes(data), delivery_s
