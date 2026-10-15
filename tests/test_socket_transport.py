"""Integration and hostile-input tests for bounded NXF/1 socket transport."""
import base64
from contextlib import closing
import os
import socket
import ssl
import struct
import threading
import unittest

from nexo import (
    AgentSocketSession, CodecError, SocketFramedTransport,
)
from nexo.transfer import send_image


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def _sessions():
    a, b = socket.socketpair()
    a.settimeout(4)
    b.settimeout(4)
    return (
        AgentSocketSession(SocketFramedTransport(a, allow_insecure=True)),
        AgentSocketSession(SocketFramedTransport(b, allow_insecure=True)),
    )


def _negotiate_pair(a, b, **kwargs):
    failures = []

    def start():
        try:
            a.negotiate(**kwargs)
        except Exception as exc:
            failures.append(exc)

    worker = threading.Thread(target=start, daemon=True)
    worker.start()
    b.negotiate()
    worker.join(timeout=4)
    if worker.is_alive():
        raise AssertionError("capability negotiation deadlocked")
    if failures:
        raise failures[0]


class TestSocketTransport(unittest.TestCase):
    def test_local_sockets_require_explicit_insecure_opt_in(self):
        a, b = socket.socketpair()
        with closing(a), closing(b):
            with self.assertRaises(ValueError):
                SocketFramedTransport(a)
            self.assertIs(SocketFramedTransport(a, allow_insecure=True).socket, a)

    def test_client_tls_rejects_disabled_hostname_verification(self):
        context = ssl.create_default_context()
        context.check_hostname = False
        with self.assertRaises(ValueError):
            SocketFramedTransport.connect_tls("example.com", 443, context=context)

    def test_client_tls_validates_host_and_port(self):
        with self.assertRaises(ValueError):
            SocketFramedTransport.connect_tls("", 443)
        with self.assertRaises(ValueError):
            SocketFramedTransport.connect_tls("example.com", 0)

    def test_text_message_and_image_same_socket(self):
        with _sessions()[0] as _:
            pass  # handled below with both handles in a single scope
        a, b = _sessions()
        with a, b:
            with self.assertRaises(CodecError):
                a.send("no capabilities")
            _negotiate_pair(a, b)
            self.assertTrue(a.channel.peer_supports_nexo)
            self.assertTrue(a.channel.peer_supports_attachments)
            a.send_text("hello agent, plain text ñ🤖")
            self.assertEqual(b.receive_text(), "hello agent, plain text ñ🤖")
            b.send({"type": "result", "task": 7})
            self.assertEqual(a.receive(), {"type": "result", "task": 7})
            a.send_image(PNG, chunk_size=19)
            attachment = b.receive_image()
            self.assertEqual(attachment.data, PNG)
            self.assertEqual(attachment.manifest["mime"], "image/png")
            b.send_text("image received")
            self.assertEqual(a.receive_text(), "image received")

    def test_large_image_across_partial_tcp_reads(self):
        image = PNG + os.urandom(170_000)
        a, b = _sessions()
        with a, b:
            _negotiate_pair(a, b)
            failures = []

            def transmit():
                try:
                    a.send_image(image, mime="image/png", chunk_size=4096)
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=transmit, daemon=True)
            worker.start()
            result = b.receive_image()
            worker.join(timeout=4)
            self.assertFalse(worker.is_alive(), "sender did not finish")
            self.assertFalse(failures)
            self.assertEqual(result.data, image)

    def test_reject_unannounced_attachment(self):
        a, b = _sessions()
        with a, b:
            _negotiate_pair(a, b, allow_attachments=False)
            self.assertFalse(b.channel.peer_supports_attachments)
            with self.assertRaises(CodecError):
                a.send_image(PNG)
            with self.assertRaises(CodecError):
                b.receive_image()

    def test_repeated_handshake_rejected(self):
        a, b = _sessions()
        with a, b:
            _negotiate_pair(a, b)
            with self.assertRaises(CodecError):
                a.negotiate()

    def test_reject_wrong_message_kind(self):
        a, b = socket.socketpair()
        with closing(a), closing(b):
            sender = SocketFramedTransport(a, allow_insecure=True)
            receiver = SocketFramedTransport(b, allow_insecure=True)
            sender.send_envelope({"format": "json", "payload": "null"})
            with self.assertRaises(CodecError):
                receiver.receive_media_packet()

    def test_reject_oversized_before_reading_payload(self):
        a, b = socket.socketpair()
        with closing(a), closing(b):
            receiver = SocketFramedTransport(b, allow_insecure=True)
            a.sendall(b"NXF\x01E" + struct.pack(">I", 0xFFFFFFFF))
            with self.assertRaises(CodecError):
                receiver.receive_envelope()

    def test_reject_truncated_payload(self):
        a, b = socket.socketpair()
        with closing(a), closing(b):
            receiver = SocketFramedTransport(b, allow_insecure=True)
            a.sendall(b"NXF\x01E" + struct.pack(">I", 8) + b"{}")
            a.shutdown(socket.SHUT_WR)
            with self.assertRaises(CodecError):
                receiver.receive_envelope()

    def test_reject_wrong_protocol_magic(self):
        a, b = socket.socketpair()
        with closing(a), closing(b):
            receiver = SocketFramedTransport(b, allow_insecure=True)
            a.sendall(b"NOPEE" + struct.pack(">I", 0))
            with self.assertRaises(CodecError):
                receiver.receive_envelope()

    def test_reject_malformed_json_and_constants(self):
        for wire in (b"not-json", b'{"value":NaN}', b'["not an object"]'):
            with self.subTest(wire=wire):
                a, b = socket.socketpair()
                with closing(a), closing(b):
                    receiver = SocketFramedTransport(b, allow_insecure=True)
                    a.sendall(b"NXF\x01C" + struct.pack(">I", len(wire)) + wire)
                    with self.assertRaises(CodecError):
                        receiver.receive_capabilities()

    def test_media_content_corruption_rejected(self):
        a, b = _sessions()
        with a, b:
            _negotiate_pair(a, b)
            parts = list(send_image(PNG, chunk_size=21))
            damaged = bytearray(parts[-1])
            damaged[-1] ^= 1
            for packet in [*parts[:-1], bytes(damaged)]:
                a.transport.send_media_packet(packet)
            with self.assertRaises(CodecError):
                b.receive_image()
