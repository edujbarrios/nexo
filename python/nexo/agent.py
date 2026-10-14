"""Agent transport facade: capability checks and encoding strategy.

The host application calls this module. Models do not parse NEXO wire strings.
"""
import json

from .codec import CodecError, MAX_FRAME, decode, encode


AGENT_INSTRUCTIONS = (
    "Use the installed nexo Python library for messages to NEXO/1-capable peers. "
    "Call nexo.prepare_peer_message(payload, peer_supports_nexo=True, tokenizer=...) "
    "in the host and nexo.parse_peer_message(envelope) at the receiver. "
    "Do not ask an LLM to decode raw NEXO text. Fall back to JSON if a peer "
    "does not support NEXO or measured token counts do not improve. "
    "Keep image bytes outside prompts; transmit reference manifests instead."
)


def _reject_constant(value):
    raise CodecError("non-finite JSON constant: " + value)


def prepare_peer_message(message, *, peer_supports_nexo=False, tokenizer=None):
    """Return a format+payload envelope; measured tokens determine best format.

    When tokenizer is omitted and the peer supports NEXO, NEXO is preferred
    without making any claim of token savings. Does not count envelope overhead.
    """
    try:
        plain = json.dumps(
            message, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise CodecError("invalid JSON-compatible message") from exc
    if len(plain.encode("utf-8")) > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    if not peer_supports_nexo:
        return {"format": "json", "payload": plain}
    wire = encode(message)
    if tokenizer is not None and len(tokenizer(wire)) >= len(tokenizer(plain)):
        return {"format": "json", "payload": plain}
    return {"format": "nexo/1", "payload": wire}


def parse_peer_message(envelope):
    """Decode a negotiated envelope. Its decoded contents remain untrusted."""
    if not isinstance(envelope, dict):
        raise CodecError("expected dict envelope")
    wire = envelope.get("payload")
    if not isinstance(wire, str):
        raise CodecError("expected text payload")
    if len(wire.encode("utf-8")) > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    if envelope.get("format") == "nexo/1":
        return decode(wire)
    if envelope.get("format") == "json":
        try:
            return json.loads(wire, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise CodecError("invalid JSON peer payload") from exc
    raise CodecError("unsupported peer format")
