"""Text NEXO/1 codec; UTF-8 length-prefixed strings."""
import math
from .constants import KEY_IDS, VALUE_IDS, KEYS, VALUES, MAX_DEPTH, MAX_ITEMS, MIN_I64, MAX_I64
from .errors import CodecError

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


