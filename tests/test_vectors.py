import unittest
from nexo import decode, encode, encode_binary

VALUE = {"status": "ok", "task": 42, "type": "result"}
TEXT = "NX1{3:.2;!1;.1;#42;.0;!0;"
BINARY = bytes.fromhex("4e58010703000208010001035400000800")


class TestGoldenVector(unittest.TestCase):
    def test_text(self):
        self.assertEqual(encode(VALUE), TEXT)
        self.assertEqual(decode(TEXT), VALUE)

    def test_binary(self):
        self.assertEqual(encode_binary(VALUE), BINARY)
        self.assertEqual(decode(BINARY), VALUE)
