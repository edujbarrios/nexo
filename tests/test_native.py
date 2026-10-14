"""Optional Rust binding parity. Skipped until the extension is built."""
import unittest

from nexo import decode, encode, encode_binary
from nexo import native


@unittest.skipUnless(native.available(), "optional nexo-native extension not installed")
class NativeParity(unittest.TestCase):
    def test_golden(self):
        values = [
            {"status": "ok", "task": 42, "type": "result"},
            {"type": "request", "files": ["a.py", "b.py"], "changed": False},
            {"name": "ñ🙂", "data": [1, -1, None, 3.5]},
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(native.encode(value), encode(value))
                self.assertEqual(native.encode_binary(value), encode_binary(value))
                self.assertEqual(native.decode(encode_binary(value)), decode(encode_binary(value)))
