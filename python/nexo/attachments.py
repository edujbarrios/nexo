"""Content-addressed attachment manifests and a process-local blob store.

A NEXO wire frame carries only a manifest. Blob bytes never appear in it.
"""
import hashlib
import re

from .codec import CodecError

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def make_manifest(data, mime="application/octet-stream"):
    """Create a stable manifest without copying binary payload into text."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if not isinstance(mime, str) or not mime:
        raise ValueError("mime must be a non-empty string")
    digest = hashlib.sha256(data).hexdigest()
    return {"ref": "sha256:" + digest, "sha256": digest,
            "size": len(data), "mime": mime}


def verify_manifest(manifest):
    """Validate manifest shape before interpreting its SHA as a blob filename."""
    if not isinstance(manifest, dict):
        raise CodecError("expected attachment manifest")
    digest = manifest.get("sha256")
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise CodecError("invalid SHA-256 digest")
    if manifest.get("ref") != "sha256:" + digest:
        raise CodecError("invalid attachment reference")
    size = manifest.get("size")
    if type(size) is not int or size < 0:
        raise CodecError("invalid attachment size")
    mime = manifest.get("mime")
    if not isinstance(mime, str) or not mime:
        raise CodecError("invalid attachment mime")
    return digest


def verify_bytes(manifest, data):
    """Fail closed when object bytes do not match their address and size."""
    digest = verify_manifest(manifest)
    if len(data) != manifest["size"] or hashlib.sha256(data).hexdigest() != digest:
        raise CodecError("attachment integrity check failed")
    return data


class MemoryBlobStore:
    """Local demonstration adapter. It does not transmit bytes over a network."""

    def __init__(self):
        self._blobs = {}

    def add(self, data, mime="application/octet-stream"):
        manifest = make_manifest(data, mime)
        self._blobs[manifest["sha256"]] = data
        return manifest

    def resolve(self, manifest):
        digest = verify_manifest(manifest)
        return verify_bytes(manifest, self._blobs[digest])
