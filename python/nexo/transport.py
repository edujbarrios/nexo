"""Length-framed agent messaging and image transfer over connected sockets.

NXF/1 is a *transport adapter*, not a new NEXO wire format. It multiplexes
NEXO/1 agent envelopes and NXI/1 attachment packets over a byte stream.
Use TLS with certificate and hostname verification for remote connections.
Raw sockets require an explicit unsafe opt-in (for local tests only).
"""
import json
import socket
import ssl
import struct

from .agent import AgentChannel
from .codec import CodecError, MAX_FRAME
from .negotiation import advertise_capabilities
from .transfer import (
    AttachmentReceiver, DEFAULT_CHUNK, DEFAULT_MAX_BYTES,
    MAX_CHUNK, MAX_METADATA, AttachmentSender, _CHUNK_HEADER,
)

MAGIC = b"NXF\x01"
_HEADER_SIZE = 9
MAX_MEDIA_FRAME = MAX_CHUNK + _CHUNK_HEADER + MAX_METADATA


def _strict_json(value):
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CodecError("invalid transport JSON") from exc


def _invalid_constant(_):
    raise CodecError("non-finite transport JSON constant")


class SocketFramedTransport:
    """Framing for an already-connected TLS socket (or opted-in local socket).

    NXF/1 frames: 4-byte magic, 1-byte kind, 4-byte BE length, payload.
    Frame kinds: C = JSON capabilities, E = JSON message envelope,
    I = raw NXI/1 image/file packet. An OS socket is a byte *stream*, not
    a message bus; receive_exact handles arbitrary partial socket reads.
    """

    def __init__(self, sock, *, allow_insecure=False):
        if not isinstance(sock, socket.socket):
            raise TypeError("expected connected socket")
        if not isinstance(sock, ssl.SSLSocket) and not allow_insecure:
            raise ValueError(
                "remote NEXO transport requires TLS; "
                "allow_insecure=True is only for trusted local tests"
            )
        self.socket = sock

    @classmethod
    def connect_tls(cls, host, port, *, timeout=10, context=None):
        """Connect with certificate/hostname-verified TLS, not custom crypto.

        The server certificate authenticates the hostname. Application-level
        peer authorization and ACLs are still the caller's responsibility.
        """
        if not isinstance(host, str) or not host:
            raise ValueError("host must be a non-empty hostname")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("port must be an integer in 1..65535")
        if context is None:
            context = ssl.create_default_context()
        if not isinstance(context, ssl.SSLContext):
            raise TypeError("context must be an SSLContext")
        if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("TLS requires hostname and certificate verification")
        raw = socket.create_connection((host, port), timeout=timeout)
        try:
            secured = context.wrap_socket(raw, server_hostname=host)
        except BaseException:
            raw.close()
            raise
        return cls(secured)

    def close(self):
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def _read_exact(self, length):
        data = bytearray()
        while len(data) < length:
            try:
                block = self.socket.recv(length - len(data))
            except (OSError, TimeoutError) as exc:
                raise CodecError("transport read failed") from exc
            if not block:
                raise CodecError("connection closed before frame completed")
            data.extend(block)
        return bytes(data)

    def _write(self, kind, payload):
        if kind not in (b"C", b"E", b"I"):
            raise CodecError("unknown transport frame kind")
        limit = MAX_MEDIA_FRAME if kind == b"I" else MAX_FRAME
        if len(payload) > limit:
            raise CodecError("transport frame exceeds limit")
        packet = MAGIC + kind + struct.pack(">I", len(payload)) + payload
        try:
            self.socket.sendall(packet)
        except (OSError, TimeoutError) as exc:
            raise CodecError("transport write failed") from exc

    def _read(self, expected):
        header = self._read_exact(_HEADER_SIZE)
        if header[:4] != MAGIC:
            raise CodecError("invalid NXF/1 transport version")
        kind = header[4:5]
        if kind not in (b"C", b"E", b"I") or kind != expected:
            raise CodecError("unexpected transport frame kind")
        length = struct.unpack(">I", header[5:])[0]
        limit = MAX_MEDIA_FRAME if kind == b"I" else MAX_FRAME
        if length > limit:
            raise CodecError("transport frame exceeds limit")
        return self._read_exact(length)

    def _send_json(self, kind, value):
        self._write(kind, _strict_json(value))

    def _recv_json(self, kind):
        raw = self._read(kind)
        try:
            value = json.loads(raw.decode("utf-8"), parse_constant=_invalid_constant)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise CodecError("invalid transport JSON frame") from exc
        if not isinstance(value, dict):
            raise CodecError("expected transport JSON object")
        return value

    def send_capabilities(self, capabilities):
        self._send_json(b"C", capabilities)

    def receive_capabilities(self):
        return self._recv_json(b"C")

    def send_envelope(self, envelope):
        self._send_json(b"E", envelope)

    def receive_envelope(self):
        return self._recv_json(b"E")

    def send_media_packet(self, packet):
        if not isinstance(packet, bytes):
            raise CodecError("socket media packets must be binary bytes")
        self._write(b"I", packet)

    def receive_media_packet(self):
        return self._read(b"I")


class AgentSocketSession:
    """One negotiated agent-to-agent session on a connected socket.

    Both peers call negotiate() at session start. It sends a small JSON
    capability frame *before* reading, so simultaneous negotiation works.
    This does not provide an identity or authorization system.
    """

    def __init__(self, transport):
        if not isinstance(transport, SocketFramedTransport):
            raise TypeError("transport must be a SocketFramedTransport")
        self.transport = transport
        self.channel = None

    @classmethod
    def connect_tls(cls, host, port, *, timeout=10, context=None):
        return cls(SocketFramedTransport.connect_tls(
            host, port, timeout=timeout, context=context,
        ))

    def negotiate(self, *, allow_nexo=True, allow_attachments=True,
                  max_attachment_bytes=DEFAULT_MAX_BYTES, tokenizer=None,
                  nexo_setup_tokens=0):
        if self.channel is not None:
            raise CodecError("session already negotiated")
        self.transport.send_capabilities(advertise_capabilities(
            allow_nexo=allow_nexo, allow_attachments=allow_attachments,
            max_attachment_bytes=max_attachment_bytes,
        ))
        offer = self.transport.receive_capabilities()
        self.channel = AgentChannel.from_peer_capabilities(
            offer, tokenizer=tokenizer, nexo_setup_tokens=nexo_setup_tokens,
        )
        return offer

    def _channel(self):
        if self.channel is None:
            raise CodecError("negotiate peer capabilities before sending messages")
        return self.channel

    def send(self, message):
        self.transport.send_envelope(self._channel().send(message))

    def receive(self):
        return self._channel().receive(self.transport.receive_envelope())

    def send_text(self, text):
        self.transport.send_envelope(self._channel().send_text(text))

    def receive_text(self):
        return self._channel().receive_text(self.transport.receive_envelope())

    def send_image(self, data, *, mime="image/png", chunk_size=DEFAULT_CHUNK):
        """Stream image packets directly; never build a full packets list."""
        packets = self._channel().send_image(
            data, mime=mime, chunk_size=chunk_size, text=False,
        )
        for packet in packets:
            self.transport.send_media_packet(packet)

    def receive_image(self, *, store=None):
        """Read packets until a complete SHA-256-verified image is available."""
        channel = self._channel()
        if not channel.peer_supports_attachments:
            raise CodecError("peer did not negotiate NXI/1 attachment support")
        receiver = AttachmentReceiver(max_bytes=channel.max_attachment_bytes)
        while not receiver.complete:
            receiver.accept(self.transport.receive_media_packet())
        result = receiver.result()
        if not result.manifest["mime"].lower().startswith("image/"):
            raise CodecError("received attachment is not an image")
        if store is not None:
            persisted = store.add(result.data, mime=result.manifest["mime"])
            if persisted != result.manifest:
                raise CodecError("attachment store manifest mismatch")
        return result

    def close(self):
        self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
