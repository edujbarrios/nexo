"""Plain-text and image-transfer conformance across host and CLI boundaries."""
import base64
import io
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import unittest

from nexo import (
    AgentChannel, AttachmentReceiver, AttachmentSender, CodecError,
    FileBlobStore, MemoryBlobStore, advertise_capabilities, decode,
    decode_text, encode, encode_text, receive_attachment, receive_image,
    send_attachment, send_image,
)


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)
ROOT = Path(__file__).resolve().parents[1]


class TestPlainText(unittest.TestCase):
    def test_original_codec_already_accepts_plain_strings(self):
        source = "Hello, agent! Here is a plain-text note. 🌍"
        self.assertEqual(decode(encode(source)), source)

    def test_explicit_text_modes(self):
        for source in ("", "Hello agents", "ñ🤖", "line 1\nline 2", "NXI1: and :;[]"):
            with self.subTest(source=source):
                for mode in ("text", "binary", "opaque"):
                    frame = encode_text(source, mode=mode)
                    self.assertEqual(decode_text(frame), source)
                    if mode == "opaque":
                        self.assertTrue(frame.startswith("NXO1:"))
                    elif mode == "binary":
                        self.assertIsInstance(frame, bytes)
                    else:
                        self.assertTrue(frame.startswith("NX1"))

    def test_opaque_is_not_plain_text_or_encryption(self):
        frame = encode_text("classified-looking but not secret", mode="opaque")
        self.assertNotIn("classified-looking", frame)
        self.assertEqual(decode_text(frame), "classified-looking but not secret")
        with self.assertRaises(CodecError):
            decode_text("NXO1:%%%")
        with self.assertRaises(CodecError):
            decode_text("NXO1:////")

    def test_type_validation(self):
        with self.assertRaises(TypeError):
            encode_text({"message": "test"})
        with self.assertRaises(ValueError):
            encode_text("hello", mode="zlib")
        with self.assertRaises(CodecError):
            decode_text(encode({"task": 42}))

    def test_agent_channel_supports_raw_text(self):
        channel = AgentChannel.from_peer_capabilities(advertise_capabilities())
        self.assertEqual(
            channel.receive_text(channel.send_text("simple note\nwith newline")),
            "simple note\nwith newline",
        )
        with self.assertRaises(CodecError):
            channel.receive_text(channel.send({"task": 42}))

    def test_cli_raw_stdin_roundtrip(self):
        source = "hello plain-text agent\nline two\n".encode("utf-8")
        for args in ([], ["--binary"], ["--opaque"]):
            with self.subTest(mode=args):
                encoded = subprocess.run(
                    [sys.executable, "-m", "nexo", "encode-text", *args],
                    input=source, capture_output=True, cwd=ROOT, check=True,
                ).stdout
                decoded = subprocess.run(
                    [sys.executable, "-m", "nexo", "decode-text",
                     *(["--binary"] if "--binary" in args else [])],
                    input=encoded, capture_output=True, cwd=ROOT, check=True,
                ).stdout
                self.assertEqual(decoded, source)


class TestAttachmentTransfer(unittest.TestCase):
    def test_binary_frames_carry_actual_image_bytes(self):
        data = PNG + os.urandom(32 * 1024)
        frames = list(send_image(data, chunk_size=700))
        self.assertIsInstance(frames[0], bytes)
        self.assertGreater(len(frames), 3)
        self.assertEqual(frames[0][:5], b"NXI\x01M")
        self.assertEqual(frames[1][:5], b"NXI\x01D")
        result = receive_image(frames)
        self.assertEqual(result.data, data)
        self.assertEqual(result.manifest["mime"], "image/png")
        self.assertEqual(result.manifest["size"], len(data))
        self.assertTrue(result.manifest["ref"].startswith("sha256:"))

    def test_text_only_transport(self):
        frames = list(send_image(PNG, mime="image/png", text=True, chunk_size=13))
        self.assertTrue(all(isinstance(frame, str) and frame.startswith("NXI1:")
                            for frame in frames))
        self.assertEqual(receive_image(frames).data, PNG)

    def test_empty_generic_attachment(self):
        frames = list(send_attachment(b"", text=False))
        self.assertEqual(len(frames), 1)
        result = receive_attachment(frames)
        self.assertEqual(result.data, b"")
        self.assertEqual(result.manifest["size"], 0)

    def test_persist_received_bytes_into_different_stores(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = FileBlobStore(folder)
            result = receive_image(send_image(PNG, text=True), store=storage)
            self.assertEqual(storage.resolve(result.manifest), PNG)
        local = MemoryBlobStore()
        result = receive_attachment(send_attachment(PNG), store=local)
        self.assertEqual(local.resolve(result.manifest), PNG)

    def test_agent_capability_negotiation_controls_images(self):
        cap = advertise_capabilities(max_attachment_bytes=1024)
        channel = AgentChannel.from_peer_capabilities(cap)
        received = channel.receive_image(channel.send_image(PNG, text=True))
        self.assertEqual(received.data, PNG)
        with self.assertRaises(CodecError):
            list(channel.send_image(b"z" * 1025))
        unsupported = AgentChannel.from_peer_capabilities(
            advertise_capabilities(allow_attachments=False)
        )
        with self.assertRaises(CodecError):
            unsupported.send_image(PNG)
        old_peer = AgentChannel.from_peer_capabilities({
            "protocol": "nexo-capabilities/1",
            "formats": ["json", "nexo/1"],
            "max_frame_bytes": 8 * 1024 * 1024,
        })
        with self.assertRaises(CodecError):
            old_peer.send_image(PNG)

    def test_missing_or_duplicate_packets(self):
        packets = list(send_image(PNG * 50, chunk_size=64))
        with self.assertRaises(CodecError):
            receive_image(packets[:-1])
        with self.assertRaises(CodecError):
            receive_image([packets[0], packets[1], packets[1]] + packets[2:])
        with self.assertRaises(CodecError):
            receive_image([packets[1], packets[0], *packets[2:]])
        with self.assertRaises(CodecError):
            receive_image(packets + [packets[-1]])

    def test_bad_digest_and_corrupted_payload(self):
        packets = list(send_image(PNG * 20, chunk_size=50))
        changed = bytearray(packets[1])
        changed[8] ^= 1
        with self.assertRaises(CodecError):
            receive_image([packets[0], bytes(changed), *packets[2:]])
        changed = bytearray(packets[-1])
        changed[-1] ^= 1
        with self.assertRaises(CodecError):
            receive_image([*packets[:-1], bytes(changed)])

    def test_reject_over_limits_and_wrong_mime(self):
        with self.assertRaises(CodecError):
            AttachmentSender(PNG, max_bytes=1)
        with self.assertRaises(ValueError):
            AttachmentSender(PNG, chunk_size=0)
        with self.assertRaises(CodecError):
            receive_attachment(send_image(PNG), max_bytes=1)
        with self.assertRaises(CodecError):
            receive_image(send_attachment(b"hello", mime="text/plain"))
        with self.assertRaises(CodecError):
            list(send_image(PNG, mime="text/plain"))
        with self.assertRaises(CodecError):
            AttachmentSender(PNG, mime="image/png\r\nX-Header: forged")
        with self.assertRaises(CodecError):
            receive_image(["NXI1:%%%"])
        with self.assertRaises(CodecError):
            receive_image([b"WRONG"]) 

    def test_receivers_require_end_to_end_completion(self):
        rx = AttachmentReceiver()
        with self.assertRaises(CodecError):
            rx.result()
        packets = list(send_image(PNG, chunk_size=12))
        self.assertFalse(rx.accept(packets[0]))
        for packet in packets[1:-1]:
            self.assertFalse(rx.accept(packet))
        self.assertTrue(rx.accept(packets[-1]))
        self.assertEqual(rx.result().data, PNG)
        with self.assertRaises(CodecError):
            rx.accept(packets[-1])

    def test_image_cli_stream_roundtrip(self):
        sender = subprocess.run(
            [sys.executable, "-m", "nexo", "send-image",
             "--mime", "image/png", "--chunk-size", "17"],
            input=PNG, capture_output=True, cwd=ROOT, check=True,
        )
        self.assertIn(b"NXI1:", sender.stdout)
        receiver = subprocess.run(
            [sys.executable, "-m", "nexo", "receive-image"],
            input=sender.stdout, capture_output=True, cwd=ROOT, check=True,
        )
        self.assertEqual(receiver.stdout, PNG)
