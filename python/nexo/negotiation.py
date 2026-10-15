"""Pure versioned capability negotiation between agent host applications."""
from .codec import MAX_FRAME

CAPABILITY_PROTOCOL = "nexo-capabilities/1"


def advertise_capabilities(*, allow_nexo=True):
    """Send this advertisement as ordinary JSON over an authenticated channel."""
    if type(allow_nexo) is not bool:
        raise TypeError("allow_nexo must be bool")
    return {
        "protocol": CAPABILITY_PROTOCOL,
        "formats": ["json", "nexo/1"] if allow_nexo else ["json"],
        "max_frame_bytes": MAX_FRAME,
    }


def peer_supports_nexo(advertisement):
    """Unknown versions and malformed offers conservatively fall back to JSON."""
    if not isinstance(advertisement, dict):
        return False
    if advertisement.get("protocol") != CAPABILITY_PROTOCOL:
        return False
    formats = advertisement.get("formats")
    if not isinstance(formats, list) or len(formats) > 16:
        return False
    if any(not isinstance(value, str) for value in formats):
        return False
    maximum = advertisement.get("max_frame_bytes")
    if type(maximum) is not int or maximum < MAX_FRAME:
        return False  # V1 does not negotiate smaller limits
    return "nexo/1" in formats and "json" in formats
