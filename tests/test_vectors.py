"""Shared golden vectors consumed by Rust and the Python reference codec."""
import json
from pathlib import Path
import unittest

from nexo import decode, encode, encode_binary


FIXTURES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "conformance.json").read_text(
        encoding="utf-8",
    )
)


class GoldenVectors(unittest.TestCase):
    def test_text_binary_reference_codec(self):
        for item in FIXTURES:
            with self.subTest(item=item["label"]):
                value = item["value"]
                text = item["text"]
                binary = bytes.fromhex(item["binary_hex"])
                self.assertEqual(encode(value), text)
                self.assertEqual(encode_binary(value), binary)
                self.assertEqual(decode(text), value)
                self.assertEqual(decode(binary), value)
