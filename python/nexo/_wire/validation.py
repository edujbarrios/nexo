"""Pure value validation shared by both output formats."""
import math
from .constants import MAX_DEPTH, MAX_ITEMS, MIN_I64, MAX_I64
from .errors import CodecError

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


