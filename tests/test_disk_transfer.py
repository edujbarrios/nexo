"""True streaming file-source/file-sink adapters: integrity and atomicity."""
import base64
import hashlib
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from nexo import (
    AgentSocketSession, CodecError, FileAttachmentReceiver,
    FileAttachmentSender, SocketFramedTransport, receive_file_to_directory,
    send_file,
)
from nexo.transfer import send_attachment


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


class TestDiskAttachments(unittest.TestCase):
    def test_file_stream_matches_original_binary_protocol(self):
        original = PNG + os.urandom(130_000)
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source.png"
            source.write_bytes(original)
            from_file = list(send_file(source, mime="image/png", chunk_size=8192))
            from_memory = list(send_attachment(
                original, mime="image/png", chunk_size=8192
            ))
            self.assertEqual(from_file, from_memory)
            result = receive_file_to_directory(from_file, Path(root) / "received",
                                               image_only=True)
            self.assertEqual(result.path.read_bytes(), original)
            self.assertEqual(result.path.name, hashlib.sha256(original).hexdigest())
            self.assertEqual(result.manifest["mime"], "image/png")

    def test_text_frames_and_empty_file(self):
        with tempfile.TemporaryDirectory() as root:
            original = Path(root) / "empty.bin"
            original.write_bytes(b"")
            packets = list(send_file(original, text=True))
            self.assertEqual(len(packets), 1)
            record = receive_file_to_directory(packets, Path(root) / "out")
            self.assertEqual(record.path.read_bytes(), b"")
            self.assertFalse(list((Path(root) / "out").glob(".nexo-upload-*")))

    def test_incomplete_transfer_leaves_no_file_or_temporary(self):
        with tempfile.TemporaryDirectory() as root:
            image = PNG * 30
            src = Path(root) / "a.png"
            src.write_bytes(image)
            destination = Path(root) / "received"
            frames = list(send_file(src, mime="image/png", chunk_size=32))
            with self.assertRaises(CodecError):
                receive_file_to_directory(frames[:-1], destination)
            self.assertEqual(list(destination.iterdir()), [])

    def test_corrupted_transfer_leaves_no_file_or_temporary(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "a.png"
            source.write_bytes(PNG * 100)
            frames = list(send_file(source, mime="image/png", chunk_size=64))
            changed = bytearray(frames[-1])
            changed[-1] ^= 1
            frames[-1] = bytes(changed)
            dst = Path(root) / "out"
            with self.assertRaises(CodecError):
                receive_file_to_directory(frames, dst, image_only=True)
            self.assertEqual(list(dst.iterdir()), [])

    def test_source_mutation_detected_and_not_published(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "source.bin"
            src.write_bytes(b"a" * 80)
            sender = FileAttachmentSender(src, chunk_size=11)
            src.write_bytes(b"b" * 80)
            with self.assertRaises(CodecError):
                list(sender.frames())

    def test_no_overwrite_same_hash_output(self):
        with tempfile.TemporaryDirectory() as root:
            original = PNG
            source = Path(root) / "source.png"
            source.write_bytes(original)
            destination = Path(root) / "uploads"
            record = receive_file_to_directory(
                send_file(source, mime="image/png"), destination
            )
            with self.assertRaises(FileExistsError):
                receive_file_to_directory(
                    send_file(source, mime="image/png"), destination
                )
            self.assertEqual(record.path.read_bytes(), original)
            self.assertEqual(list(destination.iterdir()), [record.path])

    def test_reject_mime_prior_to_publishing(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "data"
            src.write_bytes(b"not an image")
            dst = Path(root) / "received"
            with self.assertRaises(CodecError):
                receive_file_to_directory(
                    send_file(src, mime="text/plain"), dst, image_only=True
                )
            self.assertEqual(list(dst.iterdir()), [])

    def test_send_size_guard_without_loading_full_file(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "huge"
            src.write_bytes(b"z" * 500)
            with self.assertRaises(CodecError):
                FileAttachmentSender(src, max_bytes=499)

    def test_commit_requires_complete_transfer(self):
        with tempfile.TemporaryDirectory() as root:
            with FileAttachmentReceiver(root) as receiver:
                with self.assertRaises(CodecError):
                    receiver.commit()
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_real_socket_session_streams_into_disk_file(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "image.png"
            original = PNG + os.urandom(165_000)
            source.write_bytes(original)
            left, right = socket.socketpair()
            left.settimeout(5)
            right.settimeout(5)
            with AgentSocketSession(
                SocketFramedTransport(left, allow_insecure=True)
            ) as sender, AgentSocketSession(
                SocketFramedTransport(right, allow_insecure=True)
            ) as receiver:
                errors = []

                def sender_negotiate():
                    try:
                        sender.negotiate()
                    except Exception as exc:
                        errors.append(exc)

                thread = threading.Thread(target=sender_negotiate, daemon=True)
                thread.start()
                receiver.negotiate()
                thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors)

                def send_image():
                    try:
                        sender.send_image_file(source, mime="image/png",
                                               chunk_size=8192)
                    except Exception as exc:
                        errors.append(exc)

                thread = threading.Thread(target=send_image, daemon=True)
                thread.start()
                record = receiver.receive_image_to_directory(Path(root) / "out")
                thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors)
                self.assertEqual(record.path.read_bytes(), original)
                self.assertEqual(record.manifest["size"], len(original))
