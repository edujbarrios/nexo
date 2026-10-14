"""NEXO/1 lossless JSON-value serialization reference implementation.

Text wire format: UTF-8 'NX1' followed by a typed value.
Binary wire format: b'NX\x01' followed by a typed value.
No trained model can be assumed to understand an encoded message without a decoder.
"""
import json
import math
import struct

KEYS = ("type", "task", "status", "data", "id", "name", "files", "changed",
        "content", "message", "role", "agent", "timestamp", "error", "result",
        "tool", "args", "output", "mime", "sha256", "size", "ref", "version",
        "metadata", "input", "model", "tokens", "cost")
VALUES = ("result", "ok", "error", "request", "pending", "running", "done",
          "failed", "system", "user", "assistant", "tool", "text", "image",
          "file", "success", "warning")
KEY_IDS = {name: i for i, name in enumerate(KEYS)}
VALUE_IDS = {name: i for i, name in enumerate(VALUES)}
MAX_FRAME = 8 * 1024 * 1024
MAX_ITEMS = 100_000
MAX_DEPTH = 64
MIN_I64, MAX_I64 = -(2**63), 2**63 - 1


class CodecError(ValueError):
    """An input is invalid, unsupported, or exceeds resource limits."""


def _validate(v, depth=0):
    if depth > MAX_DEPTH:
        raise CodecError("nesting limit exceeded")
    if v is None or type(v) in (str, bool):
        if isinstance(v, str):
            try:
                v.encode("utf-8")
            except UnicodeError as exc:
                raise CodecError("invalid Unicode string") from exc
        return
    if type(v) is int:
        if not MIN_I64 <= v <= MAX_I64:
            raise CodecError("integer must fit signed 64 bits")
    elif type(v) is float:
        if not math.isfinite(v):
            raise CodecError("non-finite float")
    elif type(v) in (dict, list):
        if len(v) > MAX_ITEMS:
            raise CodecError("container item limit exceeded")
        if type(v) is dict:
            for key, value in v.items():
                if type(key) is not str:
                    raise CodecError("JSON object keys must be strings")
                _validate(key, depth + 1)
                _validate(value, depth + 1)
        else:
            for value in v:
                _validate(value, depth + 1)
    else:
        raise CodecError("only JSON-compatible values are supported")


def _text_string(s):
    raw = s.encode("utf-8")
    return b":" + str(len(raw)).encode("ascii") + b":" + raw


def _text(v):
    if v is None:
        return b"_"
    if v is True:
        return b"+"
    if v is False:
        return b"-"
    if type(v) is int:
        return b"#" + str(v).encode("ascii") + b";"
    if type(v) is float:
        return b"^" + repr(v).encode("ascii") + b";"
    if type(v) is str:
        if v in VALUE_IDS:
            return b"!" + str(VALUE_IDS[v]).encode("ascii") + b";"
        return _text_string(v)
    if type(v) is list:
        return b"[" + str(len(v)).encode("ascii") + b":" + b"".join(_text(x) for x in v)
    return b"{" + str(len(v)).encode("ascii") + b":" + b"".join(
        (b"." + str(KEY_IDS[k]).encode("ascii") + b";" if k in KEY_IDS
         else _text_string(k)) + _text(x)
        for k, x in sorted(v.items())
    )


def _varint(n):
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def _binary_string(s):
    raw = s.encode("utf-8")
    return _varint(len(raw)) + raw


def _binary(v):
    if v is None:
        return b"\x00"
    if v is False:
        return b"\x01"
    if v is True:
        return b"\x02"
    if type(v) is int:
        return b"\x03" + _varint((v << 1) ^ (v >> 63))
    if type(v) is float:
        return b"\x04" + struct.pack(">d", v)
    if type(v) is str:
        if v in VALUE_IDS:
            return b"\x08" + _varint(VALUE_IDS[v])
        return b"\x05" + _binary_string(v)
    if type(v) is list:
        return b"\x06" + _varint(len(v)) + b"".join(_binary(x) for x in v)
    return b"\x07" + _varint(len(v)) + b"".join(
        (b"\x00" + _varint(KEY_IDS[k]) if k in KEY_IDS else
         b"\x01" + _binary_string(k)) + _binary(x)
        for k, x in sorted(v.items())
    )


class _Reader:
    def __init__(self, raw):
        if len(raw) > MAX_FRAME:
            raise CodecError("frame size limit exceeded")
        self.raw, self.pos = raw, 0

    def take(self, n):
        if n < 0 or n > len(self.raw) - self.pos:
            raise CodecError("truncated frame")
        data = self.raw[self.pos:self.pos + n]
        self.pos += n
        return data

    def byte(self):
        return self.take(1)[0]

    def decimal(self, delimiter):
        start = self.pos
        while self.pos < len(self.raw) and self.raw[self.pos] != delimiter:
            self.pos += 1
            if self.pos - start > 64:
                raise CodecError("numeric field too long")
        if self.pos == len(self.raw):
            raise CodecError("unterminated numeric field")
        raw = self.raw[start:self.pos]
        self.pos += 1
        if not raw or any(b < 48 or b > 57 for b in raw):
            raise CodecError("invalid unsigned number")
        return int(raw)

    def signed(self):
        start = self.pos
        while self.pos < len(self.raw) and self.raw[self.pos] != 59:
            self.pos += 1
            if self.pos - start > 64:
                raise CodecError("numeric field too long")
        if self.pos == len(self.raw):
            raise CodecError("unterminated number")
        raw = self.raw[start:self.pos]
        self.pos += 1
        try:
            return raw.decode("ascii")
        except UnicodeError as exc:
            raise CodecError("non-ASCII number") from exc

    def string(self):
        try:
            return self.take(self.decimal(58)).decode("utf-8")
        except UnicodeError as exc:
            raise CodecError("invalid UTF-8") from exc

    def varint(self):
        n = 0
        for shift in range(0, 70, 7):
            b = self.byte()
            if shift == 63 and b > 1:
                raise CodecError("varint overflow")
            n |= (b & 127) << shift
            if b < 128:
                return n
        raise CodecError("varint overflow")

    def binary_string(self):
        try:
            return self.take(self.varint()).decode("utf-8")
        except UnicodeError as exc:
            raise CodecError("invalid UTF-8") from exc


def _read_text(r, depth=0):
    if depth > MAX_DEPTH:
        raise CodecError("nesting limit exceeded")
    tag = r.byte()
    if tag == 95:
        return None
    if tag == 43:
        return True
    if tag == 45:
        return False
    if tag == 35:
        try:
            value = int(r.signed())
        except ValueError as exc:
            raise CodecError("invalid integer") from exc
        if not MIN_I64 <= value <= MAX_I64:
            raise CodecError("integer out of range")
        return value
    if tag == 94:
        try:
            value = float(r.signed())
        except ValueError as exc:
            raise CodecError("invalid float") from exc
        if not math.isfinite(value):
            raise CodecError("non-finite float")
        return value
    if tag == 58:
        return r.string()
    if tag == 33:
        idx = r.decimal(59)
        if idx >= len(VALUES):
            raise CodecError("unknown value code")
        return VALUES[idx]
    if tag in (91, 123):
        count = r.decimal(58)
        if count > MAX_ITEMS:
            raise CodecError("container item limit exceeded")
        if tag == 91:
            return [_read_text(r, depth + 1) for _ in range(count)]
        obj = {}
        for _ in range(count):
            key_tag = r.byte()
            if key_tag == 46:
                idx = r.decimal(59)
                if idx >= len(KEYS):
                    raise CodecError("unknown key code")
                key = KEYS[idx]
            elif key_tag == 58:
                key = r.string()
            else:
                raise CodecError("invalid key tag")
            if key in obj:
                raise CodecError("duplicate object key")
            obj[key] = _read_text(r, depth + 1)
        return obj
    raise CodecError("unknown text tag")


def _read_binary(r, depth=0):
    if depth > MAX_DEPTH:
        raise CodecError("nesting limit exceeded")
    tag = r.byte()
    if tag == 0:
        return None
    if tag == 1:
        return False
    if tag == 2:
        return True
    if tag == 3:
        n = r.varint()
        return (n >> 1) ^ -(n & 1)
    if tag == 4:
        value = struct.unpack(">d", r.take(8))[0]
        if not math.isfinite(value):
            raise CodecError("non-finite float")
        return value
    if tag == 5:
        return r.binary_string()
    if tag == 8:
        idx = r.varint()
        if idx >= len(VALUES):
            raise CodecError("unknown value code")
        return VALUES[idx]
    if tag in (6, 7):
        count = r.varint()
        if count > MAX_ITEMS:
            raise CodecError("container item limit exceeded")
        if tag == 6:
            return [_read_binary(r, depth + 1) for _ in range(count)]
        obj = {}
        for _ in range(count):
            key_tag = r.byte()
            if key_tag == 0:
                idx = r.varint()
                if idx >= len(KEYS):
                    raise CodecError("unknown key code")
                key = KEYS[idx]
            elif key_tag == 1:
                key = r.binary_string()
            else:
                raise CodecError("invalid key tag")
            if key in obj:
                raise CodecError("duplicate object key")
            obj[key] = _read_binary(r, depth + 1)
        return obj
    raise CodecError("unknown binary tag")


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
