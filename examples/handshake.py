"""Host-side capability negotiation before sending a NEXO frame."""
from nexo import AgentChannel, advertise_capabilities

remote_offer = advertise_capabilities()  # send in authenticated JSON control path
channel = AgentChannel.from_peer_capabilities(remote_offer)
message = {"type": "request", "task": 42, "status": "pending"}
frame = channel.send(message)
assert channel.receive(frame) == message
print("Negotiated:", frame["format"], "Decoded:", channel.receive(frame))
