"""Compare real Rust and Python encoders across many generated JSON messages.

Set NEXO_RUST_INSPECT to the compiled binary's absolute/relative path.
Python-only CI skips this test; the dedicated Rust-parity job requires it.
"""
import json
import os
from pathlib import Path
import random
import subprocess
import unittest

from nexo import decode, encode, encode_binary


def _random_value(rng, depth=0):
    atoms = [None, True, False, 0, 42, -55, -2**63, 2**63-1,
             1.5, -0.0, 1e-20, "", "ñ🤖", "ok", ":;.[]{}"]
    if depth >= 3 or rng.random() < 0.45:
        return rng.choice(atoms)
    if rng.random() < 0.5:
        return [_random_value(rng, depth + 1)
                for _ in range(rng.randrange(5))]
    names = ("task", "type", "status", "zzñ", "content", "other")
    return {name: _random_value(rng, depth + 1)
            for name in rng.sample(names, rng.randrange(5))}


def _samples():
    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "conformance.json"
    for item in json.loads(fixtures.read_text(encoding="utf-8")):
        yield item["value"]
    rng = random.Random(20261015)
    for _ in range(150):
        yield _random_value(rng)


@unittest.skipUnless(
    os.environ.get("NEXO_RUST_INSPECT"),
    "Build nexo-inspect and set NEXO_RUST_INSPECT to run cross-language parity",
)
class TestRustPythonParity(unittest.TestCase):
    def test_randomized_codec_parity(self):
        tool = os.environ["NEXO_RUST_INSPECT"]
        for index, value in enumerate(_samples()):
            with self.subTest(index=index):
                process = subprocess.run(
                    [tool], input=json.dumps(value, ensure_ascii=False),
                    text=True, capture_output=True, check=True, timeout=10,
                )
                rust = json.loads(process.stdout)
                python_text = encode(value)
                python_binary = encode_binary(value)
                self.assertEqual(rust["text"], python_text)
                self.assertEqual(bytes.fromhex(rust["binary_hex"]), python_binary)
                self.assertTrue(rust["roundtrip_text"])
                self.assertTrue(rust["roundtrip_binary"])
                self.assertEqual(decode(python_text), value)
                self.assertEqual(decode(python_binary), value)
