"""Optional replay guard for NXE64/1 encrypted agent messages.

This cache only protects messages handled by the SAME guard object within a
running process. Durable, cross-host replay defenses require external state.
"""
import secrets

from nexo import CodecError, ReplayGuard, open_nexo64, seal_nexo64

key = secrets.token_bytes(32)  # demo key; never log or put in a prompt
guard = ReplayGuard(max_entries=128)
try:
    frame = seal_nexo64(b"encrypted message", key)
except ImportError:
    print("Install nexo[crypto] to enable encrypted replay protection.")
else:
    assert open_nexo64(frame, key, replay_guard=guard) == b"encrypted message"
    print("First authenticated message: accepted")
    try:
        open_nexo64(frame, key, replay_guard=guard)
    except CodecError:
        print("Repeated encrypted message: rejected")
    else:
        raise AssertionError("replay was not detected")
