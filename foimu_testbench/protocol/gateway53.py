"""Wire contract from gateway main.c:60-80, 996-1005, 1035-1040.

This is a checksum, not a cryptographic integrity guarantee or a physical model.
"""
import struct
from typing import NamedTuple

PROFILE = "gateway53-fletcher16-le-v1"
HEADER = b"\xa0\xa0"
PAYLOAD = struct.Struct("<B3f4H7f")
CHECKSUM = struct.Struct("<H")
SIZE = 53


class Packet(NamedTuple):
    counter: int
    ifog_x: float
    ifog_y: float
    ifog_z: float
    acc_x: int
    acc_y: int
    acc_z: int
    acc_tap: int
    temperature: float
    mems_gyro_x: float
    mems_gyro_y: float
    mems_gyro_z: float
    mems_acc_x: float
    mems_acc_y: float
    mems_acc_z: float


def fletcher16(data):
    a = b = 0
    for value in data:
        a = (a + value) % 255
        b = (b + a) % 255
    return (b << 8) | a


def encode(packet):
    payload = PAYLOAD.pack(*packet)
    return HEADER + payload + CHECKSUM.pack(fletcher16(payload))


def decode(frame):
    if len(frame) != SIZE:
        raise ValueError("Expected exactly 53 bytes")
    if frame[:2] != HEADER:
        raise ValueError("Invalid header")
    if CHECKSUM.unpack_from(frame, 51)[0] != fletcher16(frame[2:51]):
        raise ValueError("Invalid Fletcher-16")
    return Packet(*PAYLOAD.unpack_from(frame, 2))


class StreamParser:
    """Incremental parser. feed() must be consumed; input is processed in bounded slices.

    An invalid candidate advances by one byte, preserving overlapping headers.
    framing_errors counts desynchronization episodes, not malformed packets.
    """
    def __init__(self):
        self.buffer = bytearray()
        self.recovering = False
        self.stats = dict(checksum_errors=0, framing_errors=0, resync_events=0,
                          discarded_bytes=0, truncated_tails=0, buffer_peak_bytes=0)

    def _discard(self, count):
        if not count:
            return
        if not self.recovering:
            self.stats["framing_errors"] += 1
            self.recovering = True
        self.stats["discarded_bytes"] += count
        del self.buffer[:count]

    def feed(self, data):
        for start in range(0, len(data), 4096):
            self.buffer.extend(data[start:start + 4096])
            self.stats["buffer_peak_bytes"] = max(self.stats["buffer_peak_bytes"], len(self.buffer))
            while self.buffer:
                position = self.buffer.find(HEADER)
                if position < 0:
                    keep = 1 if self.buffer[-1:] == HEADER[:1] else 0
                    self._discard(len(self.buffer) - keep)
                    break
                if position:
                    self._discard(position)
                if len(self.buffer) < SIZE:
                    break
                frame = bytes(self.buffer[:SIZE])
                if CHECKSUM.unpack_from(frame, 51)[0] != fletcher16(frame[2:51]):
                    self.stats["checksum_errors"] += 1
                    self._discard(1)
                    continue
                del self.buffer[:SIZE]
                if self.recovering:
                    self.stats["resync_events"] += 1
                    self.recovering = False
                yield Packet(*PAYLOAD.unpack_from(frame, 2))

    def finish(self):
        if self.buffer:
            self.stats["truncated_tails"] += 1
            self._discard(len(self.buffer))

    def new_epoch(self):
        self.finish()
        self.recovering = False
