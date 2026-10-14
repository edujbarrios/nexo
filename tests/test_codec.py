"""Reference-format tests, including untrusted inputs and edge cases."""
import unittest

from nexo import (
    Codec, CodecError, MemoryBlobStore, TOOL_SCHEMAS, benchmark,
    decode, decode_message, encode, encode_binary, encode_message,
)

EXAMPLES = [
    None, False, True, 0, -2**63, 2**63-1, 1.5, -0.0, 1e-20,
    "", "a:b;[x]", "ñ🙂", "ok", [],
    {"type": "result", "task": 42, "status": "ok",
     "files": [{"name": "a.py", "changed": True}, {"name": "b.py", "changed": False}]},
    {"custom": {"nested": [1, None, "🌍"]}},
]


class NexoTest(unittest.TestCase):
    def test_roundtrips(self):
        for obj in EXAMPLES:
            with self.subTest(obj=obj):
                self.assertEqual(decode(encode(obj)), obj)
                self.assertEqual(decode(encode_binary(obj)), obj)

    def test_deterministic(self):
        self.assertEqual(encode({"b": 2, "a": 1}), encode({"a": 1, "b": 2}))

    def test_errors(self):
        for wire in ["", "NX1", "NX1:9:ab", "NX1!999;", "NX1[100001:",
                     "NX1{1:.0;_", "NX1#1", "NX1{2::1:x_:1:x_"]:
            with self.subTest(wire=wire), self.assertRaises(CodecError):
                decode(wire)
        for wire in [b"NX\x01\xff", b"NX\x01\x06\x80", b"NX\x01\x08\x7f"]:
            with self.assertRaises(CodecError):
                decode(wire)
        for obj in [{1: 2}, 2**64, float("nan"), set([1])]:
            with self.assertRaises(CodecError):
                encode(obj)

    def test_facade(self):
        obj = {"task": 42}
        self.assertIsInstance(Codec().encode(obj), str)
        self.assertIsInstance(Codec("binary").encode(obj), bytes)
        self.assertEqual(Codec("binary").decode(Codec("binary").encode(obj)), obj)

    def test_benchmark(self):
        obj = {"task": 42}
        self.assertIsNone(benchmark(obj)["nexo_tokens"])
        b = benchmark(obj, tokenizer=lambda s: s.encode())
        self.assertEqual(b["nexo_tokens"], len(encode(obj).encode()))

    def test_tools(self):
        value = {"type": "result", "status": "ok"}
        self.assertEqual(decode_message(encode_message(value)), value)
        self.assertEqual(len(TOOL_SCHEMAS), 2)

    def test_attachments(self):
        store = MemoryBlobStore()
        manifest = store.add(b"\x89PNG", "image/png")
        self.assertEqual(store.resolve(manifest), b"\x89PNG")
        with self.assertRaises(KeyError):
            MemoryBlobStore().resolve(manifest)
        with self.assertRaises(CodecError):
            store.resolve({**manifest, "size": 123})


if __name__ == "__main__":
    unittest.main()
