"""Run after installing nexo: python examples/agent_pair.py"""
from nexo import AGENT_INSTRUCTIONS, parse_peer_message, prepare_peer_message

print("Agent instruction:", AGENT_INSTRUCTIONS)
data = {"type": "result", "task": 42, "status": "ok"}
envelope = prepare_peer_message(data, peer_supports_nexo=True)
print("Transport:", envelope)
print("Decoded:", parse_peer_message(envelope))
