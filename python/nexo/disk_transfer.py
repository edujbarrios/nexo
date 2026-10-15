"""Constant-memory file attachment sender and disk-backed NXI/1 receiver.

These host-side adapters use the unmodified NXI/1 wire format. Files are
hashed incrementally and published only when the full SHA-256 is verified.
The destination directory is assumed trusted and is never derived from a
remote filename. The resulting filename is always the verified hex digest.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import struct
import tempfile

from .codec import CodecError, encode_binary
from .transfer import (
    AttachmentReceiver, DEFAULT_CHUNK, DEFAULT_MAX_BYTES, MAGIC,
    MAX_CHUNK, MAX_METADATA, _as_transport, _require_mime,
    _validate_presentation,
)


@dataclass(frozen=True)
class ReceivedFile:
    """A verified file in a trusted directory and its NEXO manifest."""
    manifest: dict
    path: Path


class FileAttachmentSender:
    """Read local file chunks without ever materializing the whole file."""

    def __init__(
        self, path, *, mime="application/octet-stream",
        chunk_size=DEFAULT_CHUNK, max_bytes=DEFAULT_MAX_BYTES,
    ):
        if type(chunk_size) is not int or not 1 <= chunk_size <= MAX_CHUNK:
            raise ValueError("invalid chunk_size")
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be nonnegative")
        self.path = Path(path)
        self.mime = _require_mime(mime)
        self.chunk_size = chunk_size
        digest = hashlib.sha256()
        total = 0
        with self.path.open("rb") as source:
            while True:
                part = source.read(chunk_size)
                if not part:
                    break
                total += len(part)
                if total > max_bytes:
                    raise CodecError("attachment exceeds configured limit")
                digest.update(part)
        sha = digest.hexdigest()
        self.manifest = {
            "ref": "sha256:" + sha,
            "sha256": sha,
            "size": total,
            "mime": self.mime,
        }

    def frames(self, *, text=False, key=None):
        """Generate NXI metadata and chunks using a selected presentation."""
        _validate_presentation(text, key)
        size = self.manifest["size"]
        count = (size + self.chunk_size - 1) // self.chunk_size
        metadata = encode_binary({
            "manifest": self.manifest,
            "chunk_size": self.chunk_size,
            "chunk_count": count,
        })
        if len(metadata) > MAX_METADATA:
            raise CodecError("attachment metadata exceeds limit")
        yield _as_transport(
            MAGIC + b"M" + struct.pack(">I", len(metadata)) + metadata, text, key=key
        )
        expected_digest = bytes.fromhex(self.manifest["sha256"])
        second_digest = hashlib.sha256()
        with self.path.open("rb") as source:
            for index in range(count):
                length = min(self.chunk_size, size - index * self.chunk_size)
                part = source.read(length)
                if len(part) != length:
                    raise CodecError("source file changed during transfer")
                second_digest.update(part)
                packet = (
                    MAGIC + b"D" + expected_digest
                    + struct.pack(">II", index, length) + part
                )
                yield _as_transport(packet, text, key=key)
            if source.read(1) or second_digest.digest() != expected_digest:
                raise CodecError("source file changed during transfer")


class FileAttachmentReceiver(AttachmentReceiver):
    """Receive/verify an NXI/1 attachment with constant in-memory data usage.

    Use as a context manager. A temporary file stays private until commit()
    atomically publishes it in the trusted root under the verified SHA-256.
    The destination cannot be chosen through untrusted peer metadata.
    """

    def __init__(self, directory, *, max_bytes=DEFAULT_MAX_BYTES, key=None,
                 replay_guard=None):
        super().__init__(max_bytes=max_bytes, key=key,
                         replay_guard=replay_guard)
        self.root = Path(directory).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise ValueError("destination must be a directory")
        temp = tempfile.NamedTemporaryFile(
            dir=self.root, mode="w+b", prefix=".nexo-upload-", delete=False
        )
        self._temporary = Path(temp.name)
        self._file = temp
        self._hash = hashlib.sha256()
        self._written = 0
        self._published = False

    def _current_size(self):
        return self._written

    def _write_part(self, part):
        self._file.write(part)
        self._hash.update(part)
        self._written += len(part)

    def _finish(self):
        if (
            self._written != self._manifest["size"]
            or self._hash.hexdigest() != self._manifest["sha256"]
        ):
            raise CodecError("attachment integrity check failed")
        self._file.flush()

    def commit(self):
        """Atomically publish the verified blob without overwriting files.

        A repeated transfer to the same digest raises FileExistsError;
        the existing file is never overwritten or silently trusted.
        """
        if not self.complete:
            raise CodecError("incomplete attachment transfer")
        if self._published:
            raise CodecError("attachment already committed")
        self._file.flush()
        self._file.close()
        path = self.root / self._manifest["sha256"]
        try:
            os.link(self._temporary, path)  # atomic, no overwrite, same filesystem
        except BaseException:
            self.close()
            raise
        self._published = True
        self.close()
        return ReceivedFile(dict(self._manifest), path)

    def result(self):
        raise CodecError("disk receiver must use commit() instead of result()")

    def close(self):
        if not self._file.closed:
            self._file.close()
        self._temporary.unlink(missing_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()


def send_file(path, *, mime="application/octet-stream", chunk_size=DEFAULT_CHUNK,
              text=False, max_bytes=DEFAULT_MAX_BYTES, key=None):
    """Yield real NXI/1 packets from a file, without reading it fully."""
    return FileAttachmentSender(
        path, mime=mime, chunk_size=chunk_size, max_bytes=max_bytes
    ).frames(text=text, key=key)


def receive_file_to_directory(frames, directory, *, max_bytes=DEFAULT_MAX_BYTES,
                              image_only=False, key=None, replay_guard=None):
    """Return a verified file; reject incomplete/malformed packets and MIME.

    Caller supplies a trusted local directory. The file is digest-named.
    """
    with FileAttachmentReceiver(
        directory, max_bytes=max_bytes, key=key,
        replay_guard=replay_guard,
    ) as receiver:
        for frame in frames:
            receiver.accept(frame)
        if not receiver.complete:
            raise CodecError("incomplete attachment transfer")
        if image_only and not receiver._manifest["mime"].lower().startswith("image/"):
            raise CodecError("received attachment is not an image")
        return receiver.commit()
