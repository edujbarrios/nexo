"""Session-scoped NXE64 replay rejection; cryptographic tests need crypto extra."""
import importlib.util
from pathlib import Path
import secrets
import tempfile
import unittest

from nexo import (
    CodecError, ReplayGuard, open_nexo64, seal_nexo64,
    receive_file_to_directory, receive_image, send_file, send_image,
)

HAVE_CRYPTO = importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(HAVE_CRYPTO, "install nexo[crypto] to test replay guards")
class TestReplayGuard(unittest.TestCase):
    def test_standalone_replay_is_rejected(self):
        key = secrets.token_bytes(32)
        cache = ReplayGuard()
        frame = seal_nexo64(b"same contents", key)
        self.assertEqual(open_nexo64(frame, key, replay_guard=cache), b"same contents")
        self.assertEqual(cache.count, 1)
        with self.assertRaisesRegex(CodecError, "replayed"):
            open_nexo64(frame, key, replay_guard=cache)
        self.assertEqual(cache.count, 1)

    def test_authentication_failure_cannot_fill_cache(self):
        key = secrets.token_bytes(32)
        frame = seal_nexo64(b"message", key)
        cache = ReplayGuard(max_entries=1)
        with self.assertRaises(CodecError):
            open_nexo64(frame, secrets.token_bytes(32), replay_guard=cache)
        self.assertEqual(cache.count, 0)
        self.assertEqual(open_nexo64(frame, key, replay_guard=cache), b"message")
        self.assertEqual(cache.count, 1)

    def test_distinct_nonce_for_same_plaintext_accepted_until_capacity(self):
        key = secrets.token_bytes(32)
        cache = ReplayGuard(max_entries=2)
        for _ in range(2):
            frame = seal_nexo64(b"same message", key)
            self.assertEqual(open_nexo64(frame, key, replay_guard=cache), b"same message")
        self.assertEqual(cache.count, 2)
        with self.assertRaisesRegex(CodecError, "exhausted"):
            open_nexo64(seal_nexo64(b"new", key), key, replay_guard=cache)

    def test_image_packet_replay_between_transfers(self):
        key = secrets.token_bytes(32)
        guard = ReplayGuard(max_entries=16)
        original = b"not rendered image bytes" * 8
        packets = list(send_image(original, text="encrypted", key=key, chunk_size=100))
        self.assertEqual(
            receive_image(packets, key=key, replay_guard=guard).data, original
        )
        with self.assertRaisesRegex(CodecError, "replayed"):
            receive_image(packets, key=key, replay_guard=guard)
        self.assertGreaterEqual(guard.count, 2)

    def test_separate_guards_have_separate_scope(self):
        key = secrets.token_bytes(32)
        payload = seal_nexo64(b"message", key)
        self.assertEqual(
            open_nexo64(payload, key, replay_guard=ReplayGuard()), b"message"
        )
        self.assertEqual(
            open_nexo64(payload, key, replay_guard=ReplayGuard()), b"message"
        )

    def test_disk_sink_rejects_replay_without_publishing(self):
        key = secrets.token_bytes(32)
        guard = ReplayGuard()
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "image.png"
            source.write_bytes(b"image data" * 50)
            packets = list(send_file(source, mime="image/png", chunk_size=100,
                                     text="encrypted", key=key))
            first = receive_file_to_directory(
                packets, Path(root) / "first", key=key,
                replay_guard=guard, image_only=True,
            )
            self.assertEqual(first.path.read_bytes(), source.read_bytes())
            with self.assertRaisesRegex(CodecError, "replayed"):
                receive_file_to_directory(
                    packets, Path(root) / "second", key=key,
                    replay_guard=guard, image_only=True,
                )
            self.assertEqual(list((Path(root) / "second").iterdir()), [])

    def test_replay_guard_requires_encryption_and_valid_capacity(self):
        with self.assertRaises(ValueError):
            ReplayGuard(max_entries=0)
        with self.assertRaises(ValueError):
            receive_image([b"NXI\x01"], replay_guard=ReplayGuard())
