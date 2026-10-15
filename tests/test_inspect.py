"""CLI-level inspection keeps binary and text outputs explainable."""
import json
import unittest

from nexo.__main__ import _inspection


class InspectTests(unittest.TestCase):
    def test_known_wire_vector(self):
        result = _inspection({"status": "ok", "task": 42, "type": "result"})
        self.assertEqual(
            result["nexo_binary_hex"], "4e58010703000208010001035400000800",
        )
        self.assertEqual(result["nexo_binary_bytes"], 17)
        self.assertEqual(result["nexo_text"], "NX1{3:.2;!1;.1;#42;.0;!0;")
        self.assertTrue(result["decoded_equal"])

    def test_utf8_byte_length_not_character_count(self):
        result = _inspection("ñ🤖")
        self.assertEqual(result["nexo_text"], "NX1:6:ñ🤖")
        self.assertEqual(result["nexo_binary_bytes"], 3 + 1 + 1 + 6)
