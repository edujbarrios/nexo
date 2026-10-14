"""Optional PyO3 adapter; the standard-library reference implementation is default."""
try:
    import nexo_native as _native
except ImportError:
    _native = None


def available():
    return _native is not None


def _required():
    if _native is None:
        raise RuntimeError("nexo-native not installed; use nexo.encode instead")
    return _native


def encode(value):
    return _required().encode_text(value)


def encode_binary(value):
    return _required().encode_binary(value)


def decode(wire):
    return _required().decode(wire)
