"""Explicit plain-text facade over the existing NEXO/1 string wire type.

No JSON object is required. "opaque" is a base64url presentation of a NEXO
binary frame, NOT encryption and NOT a token compression technique.
"""
import base64
import binascii

from .codec import CodecError, MAX_FRAME, decode, encode, encode_binary

OPAQUE_PREFIX = "NXO1:"


def encode_text(text, *, mode="text"):
    """Encode arbitrary UTF-8 prose as NEXO text, bytes, or opaque base64url.

    Text mode uses the existing NEXO/1 string encoding; it is often longer
    than the original text. Binary is for byte-oriented transports, and opaque
    is a human-unfriendly but reversible textual presentation of those bytes.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if mode == "text":
        return encode(text)
    if mode == "binary":
        return encode_binary(text)
    if mode == "opaque":
        wire = encode_binary(text)
        return OPAQUE_PREFIX + base64.urlsafe_b64encode(wire).decode("ascii")
    raise ValueError("mode must be 'text', 'binary', or 'opaque'")


def decode_text(frame):
    """Decode a NEXO string frame, rejecting non-string values.

    Accepts NEXO/1 text, NEXO/1 bytes, and the optional NXO1: base64url
    wrapper. Not an encryption/decryption operation.
    """
    if isinstance(frame, str) and frame.startswith(OPAQUE_PREFIX):
        encoded = frame[len(OPAQUE_PREFIX):]
        if len(encoded) > ((MAX_FRAME + 2) // 3) * 4 + 4:
            raise CodecError("encoded frame size limit exceeded")
        try:
            wire = base64.b64decode(encoded, altchars=b"-_", validate=True)
        except (ValueError, binascii.Error, UnicodeError) as exc:
            raise CodecError("invalid opaque text encoding") from exc
        frame = wire
    value = decode(frame)
    if not isinstance(value, str):
        raise CodecError("expected plain-text NEXO frame")
    return value
