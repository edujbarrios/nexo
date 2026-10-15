"""Host-side agent transport facade.

A model should never be asked to decompress NEXO/1 by reasoning about the
wire format. Peers explicitly negotiate NEXO support; otherwise we use JSON.
The tokenizer adapter is optional and deliberately independent of any vendor.
"""
from dataclasses import dataclass
import json
from typing import Callable, Optional

from .codec import CodecError, MAX_FRAME, decode, encode
from .negotiation import peer_supports_attachments, peer_supports_nexo
from .plaintext import decode_text as decode_plain_text
from .transfer import DEFAULT_MAX_BYTES, receive_image, send_image


AGENT_INSTRUCTIONS = (
    "Use the installed nexo Python library for messages to NEXO/1-capable peers. "
    "Exchange nexo.advertise_capabilities() first, then initialize "
    "nexo.AgentChannel.from_peer_capabilities(remote_offer, tokenizer=...) in the host; "
    "send messages with channel.send(data), decode with channel.receive(envelope). "
    "Do not ask an LLM to decode raw NEXO text. Fall back to JSON if the peer "
    "does not support NEXO or measured token counts do not improve. "
    "Send actual images via NXI/1 attachment frames over an authenticated host " 
    "transport; do not put binary image payloads in LLM prompts."
)


def _reject_constant(value):
    raise CodecError("non-finite JSON constant: " + value)


def _canonical_json(value):
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CodecError("invalid JSON-compatible message") from exc


def _envelope(format_name, payload):
    return {"format": format_name, "payload": payload}


def _measure(message, tokenizer):
    # Include the actual compact JSON envelope, rather than just its payload.
    return len(tokenizer(_canonical_json(message)))


def compare_peer_formats(message, tokenizer, *, nexo_setup_tokens=0):
    """Measure total *serialized envelope* tokens for two candidate formats.

    nexo_setup_tokens amortizes any known extra protocol instruction cost for
    this message. Actual tool schema, provider framing and vision-token billing
    remain outside this comparison. Negative savings are reported honestly.
    """
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable")
    if type(nexo_setup_tokens) is not int or nexo_setup_tokens < 0:
        raise ValueError("nexo_setup_tokens must be a nonnegative integer")
    plain = _canonical_json(message)
    wire = encode(message)
    json_tokens = _measure(_envelope("json", plain), tokenizer)
    nexo_tokens = _measure(_envelope("nexo/1", wire), tokenizer)
    effective = nexo_tokens + nexo_setup_tokens
    return {
        "json_envelope_tokens": json_tokens,
        "nexo_envelope_tokens": nexo_tokens,
        "nexo_setup_tokens": nexo_setup_tokens,
        "nexo_effective_tokens": effective,
        "tokens_saved": json_tokens - effective,
        "preferred_format": "nexo/1" if effective < json_tokens else "json",
    }


def prepare_peer_message(
    message, *, peer_supports_nexo=False, tokenizer=None, nexo_setup_tokens=0,
):
    """Prepare a structured, version-negotiated envelope for a peer.

    Without tokenizer and for a capable peer, NEXO is preferred for backwards
    compatibility, *not* because token savings can be assumed. When tokenizer
    is supplied, choose using full serialized envelopes and optional setup
    overhead. Unknown recipients always receive JSON.
    """
    if type(nexo_setup_tokens) is not int or nexo_setup_tokens < 0:
        raise ValueError("nexo_setup_tokens must be a nonnegative integer")
    plain = _canonical_json(message)
    try:
        size = len(plain.encode("utf-8"))
    except UnicodeError as exc:
        raise CodecError("invalid Unicode") from exc
    if size > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    json_envelope = _envelope("json", plain)
    if not peer_supports_nexo:
        return json_envelope
    try:
        wire = encode(message)
    except CodecError:
        # JSON can represent some values outside the NEXO/1 domain, such as
        # unsigned integers above i64::MAX. Do not break agent communication.
        return json_envelope
    nexo_envelope = _envelope("nexo/1", wire)
    if tokenizer is not None:
        if not callable(tokenizer):
            raise TypeError("tokenizer must be callable")
        json_tokens = _measure(json_envelope, tokenizer)
        nexo_tokens = _measure(nexo_envelope, tokenizer) + nexo_setup_tokens
        if nexo_tokens >= json_tokens:
            return json_envelope
    return nexo_envelope


def parse_peer_message(envelope):
    """Decode one agreed envelope. Decoded content must remain untrusted."""
    if not isinstance(envelope, dict):
        raise CodecError("expected dict envelope")
    wire = envelope.get("payload")
    if not isinstance(wire, str):
        raise CodecError("expected text payload")
    try:
        size = len(wire.encode("utf-8"))
    except UnicodeError as exc:
        raise CodecError("invalid Unicode") from exc
    if size > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    if envelope.get("format") == "nexo/1":
        return decode(wire)
    if envelope.get("format") == "json":
        try:
            return json.loads(wire, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
            raise CodecError("invalid JSON peer payload") from exc
    raise CodecError("unsupported peer format")


@dataclass(frozen=True)
class AgentChannel:
    """Small host-side facade suitable for dependency injection into agents.

    Set peer_supports_nexo only *after* explicit peer capability negotiation.
    The channel never sends messages; you own the transport and authentication.
    """

    peer_supports_nexo: bool = False
    tokenizer: Optional[Callable] = None
    nexo_setup_tokens: int = 0
    peer_supports_attachments: bool = False
    max_attachment_bytes: int = DEFAULT_MAX_BYTES

    @classmethod
    def from_peer_capabilities(
        cls, advertisement, *, tokenizer=None, nexo_setup_tokens=0,
    ):
        """Initialize after an explicit peer capability advertisement."""
        return cls(
            peer_supports_nexo=peer_supports_nexo(advertisement),
            tokenizer=tokenizer,
            nexo_setup_tokens=nexo_setup_tokens,
            peer_supports_attachments=peer_supports_attachments(advertisement),
            max_attachment_bytes=(
                advertisement["max_attachment_bytes"]
                if peer_supports_attachments(advertisement) else DEFAULT_MAX_BYTES
            ),
        )

    def send(self, message):
        return prepare_peer_message(
            message, peer_supports_nexo=self.peer_supports_nexo,
            tokenizer=self.tokenizer, nexo_setup_tokens=self.nexo_setup_tokens,
        )

    def send_text(self, text):
        """Send raw plain text without wrapping it in a user-defined JSON object."""
        if not isinstance(text, str):
            raise TypeError("text must be str")
        return self.send(text)

    def receive_text(self, envelope):
        """Decode a peer envelope and require a plain text result."""
        value = self.receive(envelope)
        if not isinstance(value, str):
            raise CodecError("expected plain-text message")
        return value

    def send_image(self, data, *, mime="image/png", chunk_size=256 * 1024,
                   text=False):
        """Yield real image frames for an already authenticated transport."""
        if not self.peer_supports_attachments:
            raise CodecError("peer did not negotiate NXI/1 attachment support")
        if len(data) > self.max_attachment_bytes:
            raise CodecError("image exceeds peer attachment limit")
        return send_image(data, mime=mime, chunk_size=chunk_size, text=text)

    def receive_image(self, frames, *, store=None):
        """Reassemble and verify an image; no network transport is provided."""
        if not self.peer_supports_attachments:
            raise CodecError("peer did not negotiate NXI/1 attachment support")
        return receive_image(
            frames, max_bytes=self.max_attachment_bytes, store=store,
        )

    def receive(self, envelope):
        return parse_peer_message(envelope)

    def explain(self, message):
        """Report the comparison when a tokenizer is configured."""
        if self.tokenizer is None:
            raise ValueError("configure tokenizer for token accounting")
        return compare_peer_formats(
            message, self.tokenizer, nexo_setup_tokens=self.nexo_setup_tokens,
        )
