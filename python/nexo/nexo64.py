"""NEXO64/1: a versioned, reversible binary-to-text presentation.

NEXO64 uses a documented permutation of RFC 4648 base64url's 64 symbols.
The permutation is NOT a secret, encryption, or compression. The CRC32 is
only for detecting accidental corruption, not malicious modification.

NXE64/1 is distinct: it uses NEXO64 to display a ciphertext produced by
the audited AES-256-GCM implementation in the optional cryptography package.
"""
import base64
import binascii
import secrets
import zlib

from .codec import CodecError

STANDARD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
NEXO_ALPHABET = "".join(STANDARD_ALPHABET[(i * 37 + 11) % 64] for i in range(64))
ENCODE_PREFIX = "NX64/1:"
ENCRYPTED_PREFIX = "NXE64/1:"
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
_NONCE_LENGTH = 12
_KEY_LENGTH = 32
_AAD_PREFIX = b"NEXO64/AES-256-GCM/1\x00"
_TO_NEXO = str.maketrans(STANDARD_ALPHABET, NEXO_ALPHABET)
_FROM_NEXO = str.maketrans(NEXO_ALPHABET, STANDARD_ALPHABET)

if len(NEXO_ALPHABET) != 64 or len(set(NEXO_ALPHABET)) != 64:
    raise RuntimeError("invalid NEXO64 alphabet")


def _bound(limit):
    if type(limit) is not int or limit < 0:
        raise ValueError("max_bytes must be a nonnegative integer")


def encode_nexo64(data):
    """Encode arbitrary bytes as NX64/1 text with CRC32 integrity check."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    encoded = base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
    return ENCODE_PREFIX + encoded.translate(_TO_NEXO) + ":" + format(
        zlib.crc32(data) & 0xFFFFFFFF, "08x"
    )


def decode_nexo64(frame, *, max_bytes=DEFAULT_MAX_BYTES):
    """Strictly decode NX64/1, bounding allocation and checking canonical text."""
    _bound(max_bytes)
    if not isinstance(frame, str) or not frame.startswith(ENCODE_PREFIX):
        raise CodecError("expected NX64/1 frame")
    tail = frame[len(ENCODE_PREFIX):]
    if len(tail) > ((max_bytes + 2) // 3) * 4 + 9:
        raise CodecError("NEXO64 frame exceeds size limit")
    parts = tail.split(":")
    if len(parts) != 2:
        raise CodecError("invalid NEXO64 frame")
    payload, checksum = parts
    if len(checksum) != 8 or any(c not in "0123456789abcdef" for c in checksum):
        raise CodecError("invalid NEXO64 checksum")
    if any(c not in NEXO_ALPHABET for c in payload) or len(payload) % 4 == 1:
        raise CodecError("invalid NEXO64 alphabet or length")
    try:
        ordinary = payload.translate(_FROM_NEXO)
        binary = base64.b64decode(
            (ordinary + "=" * (-len(ordinary) % 4)).encode("ascii"),
            altchars=b"-_", validate=True,
        )
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise CodecError("invalid NEXO64 payload") from exc
    if len(binary) > max_bytes:
        raise CodecError("NEXO64 payload exceeds size limit")
    if encode_nexo64(binary) != frame:
        raise CodecError("non-canonical NEXO64 payload")
    if zlib.crc32(binary) & 0xFFFFFFFF != int(checksum, 16):
        raise CodecError("NEXO64 checksum mismatch")
    return binary


def _aes(key):
    if not isinstance(key, bytes) or len(key) != _KEY_LENGTH:
        raise ValueError("AES-256-GCM key must contain exactly 32 bytes")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ImportError(
            "AES-256-GCM requires the optional extra: pip install 'nexo[crypto]'"
        ) from exc
    return AESGCM(key)


def _aad(aad):
    if not isinstance(aad, bytes):
        raise TypeError("aad must be bytes")
    return _AAD_PREFIX + aad


def seal_nexo64(data, key, *, aad=b""):
    """Encrypt bytes with AES-256-GCM and render ciphertext as NEXO64 text.

    A fresh random 96-bit nonce is generated for each call. The caller must
    keep the key private, share it securely out of band, and handle key rotation.
    This does not provide sender identity or replay protection on its own.
    """
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    cipher = _aes(key)
    authenticated_aad = _aad(aad)
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    sealed = nonce + cipher.encrypt(nonce, data, authenticated_aad)
    return ENCRYPTED_PREFIX + encode_nexo64(sealed)[len(ENCODE_PREFIX):]


def open_nexo64(frame, key, *, aad=b"", max_bytes=DEFAULT_MAX_BYTES):
    """Authenticate and decrypt an NXE64/1 frame. Tampering fails closed."""
    _bound(max_bytes)
    cipher = _aes(key)
    authenticated_aad = _aad(aad)
    if not isinstance(frame, str) or not frame.startswith(ENCRYPTED_PREFIX):
        raise CodecError("expected encrypted NXE64/1 frame")
    bound = max_bytes + _NONCE_LENGTH + 16
    payload = decode_nexo64(
        ENCODE_PREFIX + frame[len(ENCRYPTED_PREFIX):], max_bytes=bound,
    )
    if len(payload) < _NONCE_LENGTH + 16:
        raise CodecError("truncated encrypted NEXO64 frame")
    nonce, ciphertext = payload[:_NONCE_LENGTH], payload[_NONCE_LENGTH:]
    try:
        return cipher.decrypt(nonce, ciphertext, authenticated_aad)
    except Exception as exc:
        # cryptography.exceptions.InvalidTag for tampering or incorrect keys.
        # Avoid revealing error details from the authentication oracle.
        from cryptography.exceptions import InvalidTag
        if isinstance(exc, InvalidTag):
            raise CodecError("NEXO64 authentication failed") from exc
        raise
