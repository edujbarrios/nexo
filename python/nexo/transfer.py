"""Chunked, integrity-checked media frames for agent-to-agent transports.

NXI/1 is a separate application-layer attachment stream, not a change to the
NEXO/1 JSON-compatible value grammar. Callers send packets over an already
authenticated binary channel (or base64 text channel). No network socket,
cipher, or image decoder is provided by this module.
"""
import base64
import binascii
from dataclasses import dataclass
import hashlib
import struct

from .attachments import make_manifest, verify_bytes, verify_manifest
from .codec import CodecError, decode, encode_binary

MAGIC = b"NXI\x01"
TEXT_PREFIX = "NXI1:"
DEFAULT_CHUNK = 256 * 1024
MAX_CHUNK = 1024 * 1024
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
MAX_METADATA = 4096
_CHUNK_HEADER = len(MAGIC) + 1 + 32 + 4 + 4


@dataclass(frozen=True)
class ReceivedAttachment:
    """A verified blob and its content-addressed metadata."""
    manifest: dict
    data: bytes


def _require_mime(mime):
    if not isinstance(mime, str) or not mime or len(mime) > 127:
        raise CodecError("invalid MIME type")
    try:
        mime.encode("ascii")
    except UnicodeError as exc:
        raise CodecError("MIME type must be ASCII") from exc
    if any(ord(char) < 33 or ord(char) > 126 for char in mime) or "/" not in mime:
        raise CodecError("invalid MIME type")
    return mime


def _packet_as_bytes(packet):
    if isinstance(packet, str):
        if not packet.startswith(TEXT_PREFIX):
            raise CodecError("expected NXI1: text attachment frame")
        body = packet[len(TEXT_PREFIX):]
        # Bound base64 size before allocating decoded bytes.
        if len(body) > ((MAX_CHUNK + _CHUNK_HEADER + MAX_METADATA + 2) // 3) * 4 + 4:
            raise CodecError("attachment frame too large")
        try:
            packet = base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError, UnicodeError) as exc:
            raise CodecError("invalid attachment base64") from exc
    if not isinstance(packet, bytes):
        raise CodecError("expected bytes or NXI1: text frame")
    if len(packet) > MAX_CHUNK + _CHUNK_HEADER + MAX_METADATA:
        raise CodecError("attachment frame too large")
    if not packet.startswith(MAGIC):
        raise CodecError("unknown attachment frame version")
    return packet


def _as_transport(packet, text):
    if text:
        return TEXT_PREFIX + base64.b64encode(packet).decode("ascii")
    return packet


class AttachmentSender:
    """Generate bounded metadata and data frames for one image or other blob."""

    def __init__(
        self, data, *, mime="application/octet-stream",
        chunk_size=DEFAULT_CHUNK, max_bytes=DEFAULT_MAX_BYTES,
    ):
        if not isinstance(data, bytes):
            raise TypeError("attachment data must be bytes")
        if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK:
            raise ValueError("invalid chunk_size")
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be nonnegative")
        if len(data) > max_bytes:
            raise CodecError("attachment exceeds configured limit")
        self._data = data
        self.manifest = make_manifest(data, _require_mime(mime))
        self.chunk_size = chunk_size

    def frames(self, *, text=False):
        """Yield packets in order; transport and peer authentication are external."""
        if type(text) is not bool:
            raise TypeError("text must be bool")
        size = len(self._data)
        count = (size + self.chunk_size - 1) // self.chunk_size
        metadata = encode_binary({
            "manifest": self.manifest,
            "chunk_size": self.chunk_size,
            "chunk_count": count,
        })
        if len(metadata) > MAX_METADATA:
            raise CodecError("attachment metadata exceeds limit")
        yield _as_transport(MAGIC + b"M" + struct.pack(">I", len(metadata)) + metadata, text)
        digest = bytes.fromhex(self.manifest["sha256"])
        for index in range(count):
            part = self._data[index * self.chunk_size:(index + 1) * self.chunk_size]
            packet = (
                MAGIC + b"D" + digest
                + struct.pack(">II", index, len(part)) + part
            )
            yield _as_transport(packet, text)


class AttachmentReceiver:
    """One-transfer reassembler enforcing length, order, SHA-256 and size bounds.

    A missing or duplicated packet raises on receive or prevents completion.
    For concurrent transfers, use a separate receiver instance per transfer.
    """

    def __init__(self, *, max_bytes=DEFAULT_MAX_BYTES):
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be nonnegative")
        self.max_bytes = max_bytes
        self._manifest = None
        self._chunk_size = None
        self._chunks = None
        self._received = 0
        self._blob = bytearray()
        self.complete = False

    def accept(self, frame):
        """Consume one packet; return True when the complete blob is verified."""
        if self.complete:
            raise CodecError("attachment already complete")
        packet = _packet_as_bytes(frame)
        if len(packet) < 5:
            raise CodecError("truncated attachment packet")
        tag = packet[4:5]
        if tag == b"M":
            if self._manifest is not None:
                raise CodecError("duplicate attachment metadata")
            if len(packet) < 9:
                raise CodecError("truncated attachment metadata")
            length = struct.unpack(">I", packet[5:9])[0]
            if length > MAX_METADATA or len(packet) != 9 + length:
                raise CodecError("invalid attachment metadata length")
            meta = decode(packet[9:])
            if not isinstance(meta, dict) or set(meta) != {
                "manifest", "chunk_size", "chunk_count"
            }:
                raise CodecError("invalid attachment metadata")
            manifest = meta["manifest"]
            verify_manifest(manifest)
            if set(manifest) != {"ref", "sha256", "size", "mime"}:
                raise CodecError("invalid manifest fields")
            _require_mime(manifest["mime"])
            chunk_size, chunks = meta["chunk_size"], meta["chunk_count"]
            if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK:
                raise CodecError("invalid attachment chunk size")
            if type(chunks) is not int:
                raise CodecError("invalid attachment chunk count")
            expected = (manifest["size"] + chunk_size - 1) // chunk_size
            if manifest["size"] > self.max_bytes or chunks != expected:
                raise CodecError("invalid attachment size or chunk count")
            self._manifest, self._chunk_size, self._chunks = (
                manifest, chunk_size, chunks
            )
            if chunks == 0:
                verify_bytes(manifest, b"")
                self.complete = True
            return self.complete

        if tag != b"D":
            raise CodecError("unknown attachment packet type")
        if self._manifest is None:
            raise CodecError("attachment data before metadata")
        if len(packet) < _CHUNK_HEADER:
            raise CodecError("truncated attachment chunk")
        digest = packet[5:37]
        index, length = struct.unpack(">II", packet[37:45])
        if digest != bytes.fromhex(self._manifest["sha256"]):
            raise CodecError("attachment digest mismatch")
        if index != self._received or index >= self._chunks:
            raise CodecError("out-of-order or duplicate attachment chunk")
        remaining = self._manifest["size"] - len(self._blob)
        expected = min(self._chunk_size, remaining)
        if length != expected or len(packet) != _CHUNK_HEADER + length:
            raise CodecError("invalid attachment chunk length")
        self._blob.extend(packet[_CHUNK_HEADER:])
        self._received += 1
        if self._received == self._chunks:
            verify_bytes(self._manifest, self._blob)
            self.complete = True
        return self.complete

    def result(self):
        """Return verified bytes and manifest; fail if any packet is missing."""
        if not self.complete:
            raise CodecError("incomplete attachment transfer")
        return ReceivedAttachment(dict(self._manifest), bytes(self._blob))


def send_attachment(data, *, mime="application/octet-stream",
                    chunk_size=DEFAULT_CHUNK, text=False):
    """Return an iterator of NXI/1 frames. Send each through your transport."""
    return AttachmentSender(data, mime=mime, chunk_size=chunk_size).frames(text=text)


def receive_attachment(frames, *, max_bytes=DEFAULT_MAX_BYTES, store=None):
    """Consume frames and verify the complete blob; optionally store it locally."""
    receiver = AttachmentReceiver(max_bytes=max_bytes)
    for packet in frames:
        receiver.accept(packet)
    result = receiver.result()
    if store is not None:
        persisted = store.add(result.data, mime=result.manifest["mime"])
        if persisted != result.manifest:
            raise CodecError("attachment store manifest mismatch")
    return result


def send_image(data, *, mime="image/png", chunk_size=DEFAULT_CHUNK, text=False):
    """Transfer actual image bytes; the receiver must decode/render the image."""
    _require_mime(mime)
    if not mime.lower().startswith("image/"):
        raise CodecError("expected image MIME type")
    return send_attachment(data, mime=mime, chunk_size=chunk_size, text=text)


def receive_image(frames, *, max_bytes=DEFAULT_MAX_BYTES, store=None):
    """Return a verified ReceivedAttachment with raw image data."""
    # Reject non-image transfers before any optional persistence side effect.
    result = receive_attachment(frames, max_bytes=max_bytes)
    if not result.manifest["mime"].lower().startswith("image/"):
        raise CodecError("received attachment is not an image")
    if store is not None:
        persisted = store.add(result.data, mime=result.manifest["mime"])
        if persisted != result.manifest:
            raise CodecError("attachment store manifest mismatch")
    return result
