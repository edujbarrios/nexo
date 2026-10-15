"""Persistent content-addressed local attachment adapter for cooperating agents.

Share the directory through a trusted filesystem mount for cross-process
reuse. Do not point this at an untrusted, writable-by-everyone path.
"""
import os
from pathlib import Path
import tempfile

from .attachments import make_manifest, verify_bytes, verify_manifest
from .codec import CodecError


class FileBlobStore:
    """Local on-disk store, atomic writes, verified reads, no network access.

    The root directory must be trusted by the host. A default per-blob size
    limit protects callers from blindly reading oversized files.
    """

    def __init__(self, root, *, max_blob_bytes=64 * 1024 * 1024):
        if type(max_blob_bytes) is not int or max_blob_bytes < 1:
            raise ValueError("max_blob_bytes must be positive")
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise ValueError("blob root must be a directory")
        self.max_blob_bytes = max_blob_bytes

    def _path(self, manifest):
        return self.root / verify_manifest(manifest)

    def add(self, data, mime="application/octet-stream"):
        manifest = make_manifest(data, mime)
        if manifest["size"] > self.max_blob_bytes:
            raise CodecError("attachment exceeds configured limit")
        destination = self._path(manifest)
        # Temporary files live within the same filesystem for atomic replace.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.root, prefix=".nexo-", delete=False,
            ) as file:
                temp_path = Path(file.name)
                file.write(data)
            os.replace(temp_path, destination)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return manifest

    def resolve(self, manifest):
        path = self._path(manifest)
        if manifest["size"] > self.max_blob_bytes:
            raise CodecError("attachment exceeds configured limit")
        # On POSIX, reject symlinks for untrusted filenames. The containing
        # directory remains a trusted administration boundary.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as file:
            data = file.read(self.max_blob_bytes + 1)
        if len(data) > self.max_blob_bytes:
            raise CodecError("stored attachment exceeds configured limit")
        return verify_bytes(manifest, data)
