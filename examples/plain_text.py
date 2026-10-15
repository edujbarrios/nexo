"""Plain text is a first-class NEXO/1 value; JSON objects are not required."""
from nexo import AgentChannel, advertise_capabilities, decode_text, encode_text

message = "Hello, agent B. This is plain text, not JSON. 🤖"
for mode in ("text", "binary", "opaque"):
    encoded = encode_text(message, mode=mode)
    assert decode_text(encoded) == message
    print(mode, ":", encoded if mode != "binary" else encoded.hex())

# Use the same capability-negotiated host facade for ordinary text messaging.
sender = AgentChannel.from_peer_capabilities(advertise_capabilities())
frame = sender.send_text(message)
assert sender.receive_text(frame) == message
print("Channel round-trip:", frame["format"])

# Note: opaque is reversible base64 encoding, not encryption.
