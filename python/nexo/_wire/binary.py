"""Binary NEXO/1 codec; zigzag integers and unsigned varints."""
import math
import struct
from .constants import KEY_IDS, VALUE_IDS, KEYS, VALUES, MAX_DEPTH, MAX_ITEMS
from .errors import CodecError

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


