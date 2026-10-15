"""NEXO64/1 binary-to-text interoperability without extra dependencies."""
import base64
from pathlib import Path
import random
import tempfile
import unittest

from nexo import (
    AgentChannel, CodecError, advertise_capabilities, decode_nexo64,
    encode_nexo64, receive_file_to_directory, receive_image, send_file, send_image,
)
from nexo.nexo64 import NEXO_ALPHABET, STANDARD_ALPHABET

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


class TestNexo64(unittest.TestCase):
    def test_alphabet_is_a_documented_permutation(self):
        self.assertEqual(len(NEXO_ALPHABET), 64)
        self.assertEqual(set(NEXO_ALPHABET), set(STANDARD_ALPHABET))
        self.assertNotEqual(NEXO_ALPHABET, STANDARD_ALPHABET)

    def test_reversible_arbitrary_image_bytes(self):
        rng = random.Random(20261015)
        for raw in [b"", b"\x00", b"\xff", bytes(range(256)), PNG,
                    bytes(rng.randrange(256) for _ in range(4096))]:
            with self.subTest(length=len(raw)):
                frame = encode_nexo64(raw)
                self.assertTrue(frame.startswith("NX64/1:"))
                self.assertEqual(decode_nexo64(frame), raw)

    def test_rejects_wrong_version_checksum_and_size(self):
        frame = encode_nexo64(PNG)
        bad = [frame.replace("NX64/1:", "NX64/2:", 1), frame[:-1] + ("0" if
               frame[-1] != "0" else "1"), frame + "!", "NX64/1:A:00000000"]
        for candidate in bad:
            with self.subTest(candidate=candidate), self.assertRaises(CodecError):
                decode_nexo64(candidate)
        with self.assertRaises(CodecError):
            decode_nexo64(frame, max_bytes=1)

    def test_nxi_binary_and_legacy_base64_remain_supported(self):
        self.assertTrue(next(send_image(PNG)).startswith(b"NXI\x01"))
        self.assertTrue(next(send_image(PNG, text=True)).startswith("NXI1:"))
        self.assertEqual(receive_image(send_image(PNG, text=True)).data, PNG)

    def test_image_packets_use_nexo64_text(self):
        raw = PNG * 70
        frames = list(send_image(raw, chunk_size=70, text="nexo64"))
        self.assertTrue(all(x.startswith("NX64/1:") for x in frames))
        self.assertEqual(receive_image(frames).data, raw)

    def test_agent_channel_and_disk_stream(self):
        channel = AgentChannel.from_peer_capabilities(advertise_capabilities())
        self.assertEqual(channel.receive_image(channel.send_image(
            PNG, text="nexo64",
        )).data, PNG)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "image.png"
            path.write_bytes(PNG * 200)
            stored = receive_file_to_directory(
                send_file(path, mime="image/png", text="nexo64", chunk_size=127),
                Path(root) / "received", image_only=True,
            )
            self.assertEqual(stored.path.read_bytes(), path.read_bytes())

    def test_invalid_presentation(self):
        with self.assertRaises(ValueError):
            list(send_image(PNG, text="unrecognized"))
