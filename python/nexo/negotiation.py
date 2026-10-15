"""Pure versioned capability negotiation between agent host applications."""
from .codec import MAX_FRAME
from .transfer import DEFAULT_MAX_BYTES

CAPABILITY_PROTOCOL = "nexo-capabilities/1"


def advertise_capabilities(*, allow_nexo=True, allow_attachments=True,
                           max_attachment_bytes=DEFAULT_MAX_BYTES):
    """Send this declaration as JSON over an authenticated control channel.

    NXI/1 image transfer is separate from the NEXO/1 object/string codec.
    """
    if type(allow_nexo) is not bool or type(allow_attachments) is not bool:
        raise TypeError("capability flags must be bool")
    if type(max_attachment_bytes) is not int or not 0 <= max_attachment_bytes <= DEFAULT_MAX_BYTES:
        raise ValueError("invalid max_attachment_bytes")
    return {
        "protocol": CAPABILITY_PROTOCOL,
        "formats": ["json", "nexo/1"] if allow_nexo else ["json"],
        "max_frame_bytes": MAX_FRAME,
        "attachments": ["nxi/1"] if allow_nexo and allow_attachments else [],
        "max_attachment_bytes": max_attachment_bytes,
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


def peer_supports_attachments(advertisement):
    """Opt in only if the peer explicitly declares the NXI/1 frame protocol."""
    if not peer_supports_nexo(advertisement):
        return False
    formats = advertisement.get("attachments")
    if not isinstance(formats, list) or len(formats) > 8:
        return False
    if any(not isinstance(name, str) for name in formats):
        return False
    limit = advertisement.get("max_attachment_bytes")
    if type(limit) is not int or not 0 <= limit <= DEFAULT_MAX_BYTES:
        return False
    return "nxi/1" in formats
