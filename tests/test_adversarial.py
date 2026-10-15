"""Malformed NEXO frames are rejected; corrupted frames never crash the parser."""
import json
from pathlib import Path
import random
import unittest

from nexo import CodecError, decode, encode, encode_binary

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "invalid_frames.json").read_text(
        encoding="utf-8",
    )
)


class RejectionContract(unittest.TestCase):
    def test_shared_invalid_vectors(self):
        for item in FIXTURES:
            raw = bytes.fromhex(item["binary_hex"]) if "binary_hex" in item else item["text"]
            with self.subTest(case=item["name"]), self.assertRaises(CodecError):
                decode(raw)

    def test_generated_nested_depth_exhaustion(self):
        for profile in ("text", "binary"):
            # Nesting depth 65 exceeds NEXO/1's maximum of 64.
            frame = (
                "NX1" + "[1:" * 65 + "_"
                if profile == "text" else b"NX\x01" + b"\x06\x01" * 65 + b"\x00"
            )
            with self.subTest(profile=profile), self.assertRaises(CodecError):
                decode(frame)

    def test_deterministic_mutations_do_not_raise_unexpected_errors(self):
        rng = random.Random(20261015)
        bases = [
            encode_binary({"status": "ok", "task": 42}),
            encode_binary({"data": [1, 2, {"name": "ñ🤖"}]}),
            encode_binary([True, None, -2**63, 2**63-1, 1e-20]),
        ]
        for index in range(350):
            original = bytearray(rng.choice(bases))
            mode = rng.randrange(3)
            if mode == 0:
                original[rng.randrange(len(original))] ^= 1 << rng.randrange(8)
            elif mode == 1:
                original = original[:rng.randrange(len(original))]
            else:
                original.extend(bytes([rng.randrange(256)]))
            with self.subTest(index=index):
                try:
                    value = decode(bytes(original))
                except CodecError:
                    continue
                # A bit flip may legitimately create another valid message.
                # If it does, its decoded structure must remain reversible.
                self.assertEqual(decode(encode(value)), value)
                self.assertEqual(decode(encode_binary(value)), value)
