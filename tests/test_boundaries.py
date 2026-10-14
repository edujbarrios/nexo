"""Defensive decoding and supported JSON value conformance."""
import random
import unittest

from nexo import CodecError, decode, encode, encode_binary
from nexo.codec import MAX_FRAME


def build_value(rng, depth=0):
    if depth > 3:
        return rng.choice([None, True, False, 0, -1, "ñ🙂", "text:;[]"])
    choice = rng.randrange(6)
    if choice == 0:
        return rng.randint(-(2**63), 2**63 - 1)
    if choice == 1:
        return rng.choice([0.0, -0.0, 1.5, -2.4, 1e-20])
    if choice == 2:
        return rng.choice(["", "A", "ñ🙂", "status", "type", ":;#"])
    if choice == 3:
        return [build_value(rng, depth + 1) for _ in range(rng.randrange(4))]
    if choice == 4:
        return {"k" + str(i): build_value(rng, depth + 1)
                for i in range(rng.randrange(4))}
    return rng.choice([None, True, False])


class BoundariesTest(unittest.TestCase):
    def test_randomized_roundtrip(self):
        rng = random.Random(20261015)
        for _ in range(250):
            message = build_value(rng)
            self.assertEqual(decode(encode(message)), message)
            self.assertEqual(decode(encode_binary(message)), message)

    def test_no_trailing_data(self):
        for frame in [encode({"type": "ok"}), encode_binary({"type": "ok"})]:
            with self.assertRaises(CodecError):
                decode(frame + ("garbage" if isinstance(frame, str) else b"garbage"))

    def test_depth_limit(self):
        value = None
        for _ in range(66):
            value = [value]
        with self.assertRaises(CodecError):
            encode(value)

    def test_duplicate_keys(self):
        for frame in ["NX1{2::1:a#1;:1:a#2;",
                      bytes.fromhex("4e5801070201016103020101610304")]:
            with self.assertRaises(CodecError):
                decode(frame)

    def test_frame_limit(self):
        too_long = b"NX1:" + b"0" * (MAX_FRAME + 1)
        with self.assertRaises(CodecError):
            decode(too_long)

    def test_bad_input_types(self):
        for item in [bytearray(b"NX1_"), 123, object()]:
            with self.assertRaises(CodecError):
                decode(item)
