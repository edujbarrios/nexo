"""Optional Rust binding parity. Skipped if the extension is absent."""
import json
from pathlib import Path
import unittest

from nexo import decode, encode, encode_binary, native

VECTORS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "conformance.json").read_text(
        encoding="utf-8",
    )
)


@unittest.skipUnless(native.available(), "optional nexo-native extension not installed")
class NativeParity(unittest.TestCase):
    def test_frozen_shared_wire_vectors(self):
        for item in VECTORS:
            with self.subTest(item=item["label"]):
                value = item["value"]
                expected_binary = bytes.fromhex(item["binary_hex"])
                self.assertEqual(native.encode(value), item["text"])
                self.assertIsInstance(native.encode_binary(value), bytes)
                self.assertEqual(native.encode_binary(value), expected_binary)
                self.assertEqual(native.decode(item["text"]), value)
                self.assertEqual(native.decode(expected_binary), value)

    def test_nested_payload(self):
        value = {"type": "request", "files": ["a.py", "b.py"],
                 "changed": False, "data": {"name": "ñ🙂", "task": -99}}
        self.assertEqual(native.encode(value), encode(value))
        self.assertEqual(native.encode_binary(value), encode_binary(value))
        self.assertEqual(native.decode(encode_binary(value)), decode(encode_binary(value)))
