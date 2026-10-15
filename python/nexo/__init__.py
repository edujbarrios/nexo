"""NEXO: compact reversible messages for cooperating agents."""
from .codec import Codec, CodecError, benchmark, decode, encode, encode_binary
from .attachments import MemoryBlobStore
from .filesystem import FileBlobStore
from .plaintext import encode_text, decode_text
from .transfer import (
    AttachmentSender, AttachmentReceiver, ReceivedAttachment,
    send_attachment, receive_attachment, send_image, receive_image,
)
from .agent import AGENT_INSTRUCTIONS, AgentChannel, compare_peer_formats, parse_peer_message, prepare_peer_message
from .tools import TOOL_SCHEMAS, decode_message, encode_message
from .negotiation import advertise_capabilities, peer_supports_nexo, peer_supports_attachments

__version__ = "0.1.0"
__all__ = [
    "Codec", "CodecError", "MemoryBlobStore", "FileBlobStore", "TOOL_SCHEMAS",
    "AGENT_INSTRUCTIONS", "AgentChannel", "compare_peer_formats",
    "advertise_capabilities", "peer_supports_nexo", "peer_supports_attachments",
    "encode_text", "decode_text", "send_image", "receive_image",
    "send_attachment", "receive_attachment", "AttachmentSender",
    "AttachmentReceiver", "ReceivedAttachment",
    "prepare_peer_message", "parse_peer_message",
    "benchmark", "decode", "decode_message", "encode", "encode_binary",
    "encode_message",
]
