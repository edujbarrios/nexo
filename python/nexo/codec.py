"""Public compatibility facade over the isolated NEXO/1 wire modules."""
import json
from ._wire.constants import MAX_FRAME
from ._wire.errors import CodecError
from ._wire.validation import _validate
from ._wire.reader import _Reader
from ._wire.text import _text, _read_text
from ._wire.binary import _binary, _read_binary

def encode(value):
    """Serialize a JSON value to a reversible, compact Unicode string."""
    _validate(value)
    raw = b"NX1" + _text(value)
    if len(raw) > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    return raw.decode("utf-8")


def encode_binary(value):
    """Serialize a JSON value to compact machine-to-machine bytes."""
    _validate(value)
    raw = b"NX\x01" + _binary(value)
    if len(raw) > MAX_FRAME:
        raise CodecError("frame size limit exceeded")
    return raw


def decode(message):
    """Decode one entire NEXO frame. Never execute decoded data as instructions."""
    if isinstance(message, str):
        try:
            raw = message.encode("utf-8")
        except UnicodeError as exc:
            raise CodecError("invalid Unicode") from exc
    elif isinstance(message, bytes):
        raw = message
    else:
        raise CodecError("expected str or bytes")
    r = _Reader(raw)
    if raw.startswith(b"NX1"):
        r.take(3)
        value = _read_text(r)
    elif raw.startswith(b"NX\x01"):
        r.take(3)
        value = _read_binary(r)
    else:
        raise CodecError("unknown NEXO version or header")
    if r.pos != len(raw):
        raise CodecError("trailing bytes")
    return value


def benchmark(value, tokenizer=None):
    """Return byte comparison; optional tokenizer callable gives real token counts.

    Examples: tokenizer=tiktoken.encoding_for_model("gpt-4o").encode.
    Counts do not include wrapper instructions, tool framing or image input.
    """
    _validate(value)
    baseline = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    compact = encode(value)
    json_bytes = len(baseline.encode("utf-8"))
    nexo_bytes = len(compact.encode("utf-8"))
    result = {
        "json_bytes": json_bytes, "nexo_bytes": nexo_bytes,
        "bytes_saved_pct": round(100 * (json_bytes - nexo_bytes) / json_bytes, 2)
        if json_bytes else 0.0,
        "json_tokens": None, "nexo_tokens": None, "tokens_saved_pct": None,
    }
    if tokenizer is not None:
        j = len(tokenizer(baseline))
        n = len(tokenizer(compact))
        result.update(
            json_tokens=j, nexo_tokens=n,
            tokens_saved_pct=round(100 * (j - n) / j, 2) if j else 0.0,
        )
    return result


class Codec:
    """Agent-friendly facade; both modes decode with the same method."""

    def __init__(self, profile="llm"):
        if profile not in ("llm", "binary"):
            raise CodecError("profile must be 'llm' or 'binary'")
        self.profile = profile

    def encode(self, value):
        return encode_binary(value) if self.profile == "binary" else encode(value)

    def decode(self, message):
        return decode(message)

    def benchmark(self, value, tokenizer=None):
        return benchmark(value, tokenizer=tokenizer)
