import math
import struct
import unittest
from pathlib import Path
from foimu_testbench.protocol import Packet, encode, decode, fletcher16, StreamParser

GOLDEN = (Path(__file__).parent / "fixtures" / "golden_frame.bin").read_bytes()
EXPECTED = Packet(90, 1.0, -2.0, 0.5, 0x1234, 0x5678, 0x9ABC, 0xDEF0,
                  25.25, 0.25, -0.125, 16.0, 1.5, -9.81, 27.125)


class ProtocolTests(unittest.TestCase):
    def test_independent_c_reference(self):
        self.assertEqual(len(GOLDEN), 53)
        self.assertEqual(GOLDEN[-2:].hex(), "545f")
        self.assertEqual(encode(EXPECTED), GOLDEN)
        decoded = decode(GOLDEN)
        for a, b in zip(decoded, EXPECTED):
            self.assertAlmostEqual(a, b, places=5)

    def test_offsets_independent_literal_bytes(self):
        self.assertEqual(GOLDEN[:3], bytes.fromhex("a0a05a"))
        self.assertEqual(GOLDEN[3:7], bytes.fromhex("0000803f"))
        self.assertEqual(GOLDEN[15:23], bytes.fromhex("34127856bc9af0de"))
        self.assertEqual(GOLDEN[23:27], bytes.fromhex("0000ca41"))

    def test_every_single_bit_change_rejected(self):
        for position in range(53):
            for bit in range(8):
                candidate = bytearray(GOLDEN)
                candidate[position] ^= 1 << bit
                with self.assertRaises(ValueError, msg=f"byte={position}, bit={bit}"):
                    decode(candidate)

    def test_checksum_known_collision_is_not_hidden(self):
        altered = bytearray(GOLDEN)
        self.assertEqual(altered[3], 0)
        altered[3] = 255
        self.assertEqual(fletcher16(altered[2:51]), fletcher16(GOLDEN[2:51]))
        self.assertNotEqual(decode(altered).ifog_x, decode(GOLDEN).ifog_x)

    def test_all_split_positions(self):
        for cut in range(1, 53):
            parser = StreamParser()
            self.assertEqual(list(parser.feed(GOLDEN[:cut])), [])
            self.assertEqual(list(parser.feed(GOLDEN[cut:])), [decode(GOLDEN)])
            self.assertEqual(len(parser.buffer), 0)

    def test_byte_at_a_time(self):
        parser = StreamParser()
        packets = []
        for value in GOLDEN:
            packets.extend(parser.feed(bytes([value])))
        self.assertEqual(packets, [decode(GOLDEN)])

    def test_burst_and_large_noise_bounded(self):
        parser = StreamParser()
        self.assertEqual(len(list(parser.feed(b"\x66" * 100000 + GOLDEN * 500))), 500)
        self.assertLessEqual(parser.stats["buffer_peak_bytes"], 4096 + 52)
        self.assertEqual(parser.stats["resync_events"], 1)
        self.assertEqual(parser.stats["discarded_bytes"], 100000)

    def test_header_inside_payload(self):
        value = struct.unpack("<f", bytes.fromhex("a0a0403f"))[0]
        packet = EXPECTED._replace(ifog_y=value)
        parser = StreamParser()
        self.assertEqual(list(parser.feed(encode(packet))), [decode(encode(packet))])

    def test_corrupt_then_valid(self):
        damaged = bytearray(GOLDEN)
        damaged[51] ^= 1
        parser = StreamParser()
        self.assertEqual(list(parser.feed(damaged + GOLDEN)), [decode(GOLDEN)])
        self.assertEqual(parser.stats["checksum_errors"], 1)
        self.assertEqual(parser.stats["resync_events"], 1)

    def test_truncated_then_valid(self):
        parser = StreamParser()
        self.assertEqual(list(parser.feed(GOLDEN[:20] + GOLDEN)), [decode(GOLDEN)])
        self.assertEqual(parser.stats["checksum_errors"], 1)
        self.assertEqual(parser.stats["discarded_bytes"], 20)

    def test_wrong_header_is_framing_not_checksum(self):
        parser = StreamParser()
        self.assertEqual(list(parser.feed(b"\x00" + GOLDEN[1:] + GOLDEN)), [decode(GOLDEN)])
        self.assertEqual(parser.stats["checksum_errors"], 0)
        self.assertEqual(parser.stats["framing_errors"], 1)

    def test_partial_final_frame(self):
        parser = StreamParser()
        self.assertEqual(list(parser.feed(GOLDEN[:12])), [])
        parser.finish()
        self.assertEqual(parser.stats["truncated_tails"], 1)
        self.assertEqual(parser.stats["discarded_bytes"], 12)

    def test_float_nonfinite_supported_by_wire(self):
        packet = decode(encode(EXPECTED._replace(ifog_x=float("nan"), ifog_z=float("inf"))))
        self.assertTrue(math.isnan(packet.ifog_x))
        self.assertTrue(math.isinf(packet.ifog_z))

    def test_uint16_not_signed_or_float(self):
        self.assertEqual(decode(GOLDEN).acc_z, 39612)
        with self.assertRaises(struct.error):
            encode(EXPECTED._replace(acc_x=-1))


if __name__ == "__main__":
    unittest.main()
