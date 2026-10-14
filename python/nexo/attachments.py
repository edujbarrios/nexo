"""Content-addressed attachments; image pixels are not encoded into LLM text."""
import hashlib

from .codec import CodecError


class MemoryBlobStore:
    """Local demonstration store. Processes need a shared store in production."""

    def __init__(self):
        self._blobs = {}

    def add(self, data, mime="application/octet-stream"):
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        if not isinstance(mime, str) or not mime:
            raise ValueError("mime must be a non-empty string")
        digest = hashlib.sha256(data).hexdigest()
        self._blobs[digest] = data
        return {"ref": "sha256:" + digest, "sha256": digest, "size": len(data), "mime": mime}

    def resolve(self, manifest):
        digest = manifest.get("sha256")
        if not isinstance(digest, str) or manifest.get("ref") != "sha256:" + digest:
            raise CodecError("invalid attachment reference")
        data = self._blobs[digest]
        if len(data) != manifest.get("size") or hashlib.sha256(data).hexdigest() != digest:
            raise CodecError("attachment integrity check failed")
        return data
