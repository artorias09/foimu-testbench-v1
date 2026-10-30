import math
from dataclasses import dataclass
from ..protocol import Packet, encode
from ..fault_injection import Injector


def synthetic_packet(index, rate_hz):
    t = index / rate_hz
    x, y, z = 100 * math.sin(2 * math.pi * 0.2 * t), 25.0, 10 * (t % 20)
    counter = (index + 1) % 256
    slot = (counter - 1) % 8
    return Packet(counter, x, y, z, 0, 0, 2048, 1024, 25 + slot * 0.5 + 0.001 * t,
                  x / 3600, y / 3600, z / 3600, 0.0, 0.0, 9.81)


@dataclass(frozen=True, slots=True)
class Emission:
    index: int
    model_s: float
    delivery_s: float
    data: bytes


class FakeFOIMU:
    def __init__(self, config):
        self.config = config
        self.injector = Injector(config["faults"], config["seed"])

    def events(self):
        rate = self.config["rate_hz"]
        for index in range(self.config["packets"]):
            frame = encode(synthetic_packet(index, rate))
            data, due = self.injector.apply(index, frame, (index + 1) / rate)
            yield Emission(index, index / rate, due, data)


class Fragmenter:
    def __init__(self, sizes):
        self.sizes = sizes
        self.index = 0

    def split(self, data):
        offset = 0
        while offset < len(data):
            count = self.sizes[self.index % len(self.sizes)]
            self.index += 1
            yield data[offset:offset + count]
            offset += count
