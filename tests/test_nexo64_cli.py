"""Smoke tests for NEXO64 CLI pipelines and encrypted image files."""
import base64
import importlib.util
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def _nexo(args, data):
    return subprocess.run(
        [sys.executable, "-m", "nexo", *args], input=data,
        capture_output=True, cwd=ROOT,
    )


class TestNexo64Cli(unittest.TestCase):
    def test_binary_to_nexo64_and_back(self):
        frame = _nexo(["encode64"], PNG)
        self.assertEqual(frame.returncode, 0, frame.stderr)
        self.assertTrue(frame.stdout.startswith(b"NX64/1:"))
        restored = _nexo(["decode64"], frame.stdout)
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(restored.stdout, PNG)

    def test_nexo64_image_frames_piped_between_processes(self):
        frame = _nexo(["send-image", "--encoding", "nexo64",
                       "--chunk-size", "16"], PNG * 3)
        self.assertEqual(frame.returncode, 0, frame.stderr)
        self.assertIn(b"NX64/1:", frame.stdout)
        received = _nexo(["receive-image"], frame.stdout)
        self.assertEqual(received.returncode, 0, received.stderr)
        self.assertEqual(received.stdout, PNG * 3)

    @unittest.skipUnless(HAVE_CRYPTO, "install optional nexo[crypto]")
    def test_aes_cli_encrypt_and_decrypt_without_key_in_args(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder) / "private-key"
            key.write_bytes(secrets.token_bytes(32))
            sealed = _nexo(["seal64", "--key-file", str(key)], PNG)
            self.assertEqual(sealed.returncode, 0, sealed.stderr)
            self.assertTrue(sealed.stdout.startswith(b"NXE64/1:"))
            opened = _nexo(["open64", "--key-file", str(key)], sealed.stdout)
            self.assertEqual(opened.returncode, 0, opened.stderr)
            self.assertEqual(opened.stdout, PNG)

            another_key = Path(folder) / "wrong"
            another_key.write_bytes(secrets.token_bytes(32))
            denied = _nexo(["open64", "--key-file", str(another_key)], sealed.stdout)
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(denied.stdout, b"")

    @unittest.skipUnless(HAVE_CRYPTO, "install optional nexo[crypto]")
    def test_encrypted_image_text_packets_via_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder) / "key"
            key.write_bytes(secrets.token_bytes(32))
            sent = _nexo(
                ["send-image", "--encoding", "encrypted",
                 "--key-file", str(key), "--chunk-size", "19"], PNG * 2
            )
            self.assertEqual(sent.returncode, 0, sent.stderr)
            self.assertTrue(all(p.startswith(b"NXE64/1:")
                                for p in sent.stdout.splitlines()))
            received = _nexo(["receive-image", "--key-file", str(key)], sent.stdout)
            self.assertEqual(received.returncode, 0, received.stderr)
            self.assertEqual(received.stdout, PNG * 2)
            downgraded = _nexo(["receive-image", "--key-file", str(key)],
                               _nexo(["send-image"], PNG).stdout)
            self.assertNotEqual(downgraded.returncode, 0)
