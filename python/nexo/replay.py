"""Bounded in-process NXE64/1 nonce replay rejection.

This is a best-effort optional *local* guard, not a durable distributed replay
protocol. For multi-host or restart-safe replay prevention, use durable
session IDs and counters in an authenticated application protocol.
"""
import hashlib
import hmac
import threading

from .codec import CodecError


class ReplayGuard:
    """Remember authenticated AES-GCM key+nonce pairs, failing closed when full.

    Reuse the same instance across multiple encrypted receives in a session.
    Each accepted packet consumes an entry even if a later packet fails.
    An invalid AES-GCM tag never consumes an entry. No implicit eviction is
    allowed: eviction would permit an attacker to replay older packets.
    """

    def __init__(self, *, max_entries=65536):
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self.max_entries = max_entries
        self._seen = set()
        self._lock = threading.Lock()

    @property
    def count(self):
        with self._lock:
            return len(self._seen)

    def record_authenticated(self, key, nonce):
        """Atomically reject repeated authenticated nonces under the same key."""
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("expected 32-byte AES-256-GCM key")
        if not isinstance(nonce, bytes) or len(nonce) != 12:
            raise ValueError("expected 12-byte AES-GCM nonce")
        fingerprint = hmac.new(
            key, b"NEXO64/REPLAY/1\x00" + nonce, hashlib.sha256
        ).digest()
        with self._lock:
            if fingerprint in self._seen:
                raise CodecError("replayed authenticated NEXO64 packet")
            if len(self._seen) >= self.max_entries:
                raise CodecError("NEXO64 replay guard exhausted; start a new session")
            self._seen.add(fingerprint)
