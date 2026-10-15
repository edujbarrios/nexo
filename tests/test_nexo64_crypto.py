"""Optional AES-256-GCM authenticated NEXO64 and image encryption tests."""
import base64
import importlib.util
from pathlib import Path
import secrets
import tempfile
import unittest

from nexo import (
    AgentChannel, CodecError, advertise_capabilities,
    receive_image, send_image, send_file, receive_file_to_directory,
    seal_nexo64, open_nexo64,
)

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


@unittest.skipUnless(HAVE_CRYPTO, "install nexo[crypto] for AEAD tests")
class TestEncryptedNexo64(unittest.TestCase):
    def test_random_nonce_and_exact_roundtrip(self):
        key = secrets.token_bytes(32)
        data = PNG + b"\xff\x00" * 256
        one = seal_nexo64(data, key)
        two = seal_nexo64(data, key)
        self.assertTrue(one.startswith("NXE64/1:"))
        self.assertNotEqual(one, two)
        self.assertEqual(open_nexo64(one, key), data)
        self.assertEqual(open_nexo64(two, key), data)

    def test_wrong_key_aad_and_tampering(self):
        key = secrets.token_bytes(32)
        envelope = seal_nexo64(PNG, key, aad=b"image")
        with self.assertRaises(CodecError):
            open_nexo64(envelope, secrets.token_bytes(32), aad=b"image")
        with self.assertRaises(CodecError):
            open_nexo64(envelope, key, aad=b"other")
        bad = envelope[:-1] + ("0" if envelope[-1] != "0" else "1")
        with self.assertRaises(CodecError):
            open_nexo64(bad, key, aad=b"image")

    def test_invalid_key_is_rejected(self):
        with self.assertRaises(ValueError):
            seal_nexo64(PNG, b"not a 32-byte AES key")
        with self.assertRaises(TypeError):
            seal_nexo64(PNG, secrets.token_bytes(32), aad="not bytes")

    def test_encrypted_chunked_image(self):
        key = secrets.token_bytes(32)
        data = PNG * 35
        packets = list(send_image(data, text="encrypted", key=key, chunk_size=91))
        self.assertTrue(all(p.startswith("NXE64/1:") for p in packets))
        self.assertEqual(receive_image(packets, key=key).data, data)
        with self.assertRaises(CodecError):
            receive_image(packets, key=secrets.token_bytes(32))
        with self.assertRaises(CodecError):
            receive_image(packets)
        with self.assertRaises(CodecError):
            receive_image(list(send_image(data, text=True)), key=key)

    def test_mode_validation(self):
        key = secrets.token_bytes(32)
        with self.assertRaises(ValueError):
            list(send_image(PNG, text="encrypted"))
        with self.assertRaises(ValueError):
            list(send_image(PNG, text="nexo64", key=key))

    def test_agent_and_streamed_file_encryption(self):
        key = secrets.token_bytes(32)
        agent = AgentChannel.from_peer_capabilities(advertise_capabilities())
        self.assertEqual(agent.receive_image(
            agent.send_image(PNG, text="encrypted", key=key), key=key,
        ).data, PNG)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "photo.png"
            path.write_bytes(PNG * 90)
            output = Path(root) / "received"
            stored = receive_file_to_directory(
                send_file(path, mime="image/png", chunk_size=101,
                          text="encrypted", key=key),
                output, image_only=True, key=key,
            )
            self.assertEqual(stored.path.read_bytes(), path.read_bytes())
            bad_output = Path(root) / "wrong"
            with self.assertRaises(CodecError):
                receive_file_to_directory(
                    send_file(path, mime="image/png", text="encrypted", key=key),
                    bad_output, key=secrets.token_bytes(32),
                )
            self.assertEqual(list(bad_output.iterdir()), [])
