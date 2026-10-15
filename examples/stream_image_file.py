"""Transfer an image from disk to disk without buffering it in Python RAM.

The demo uses trusted local socketpair() transport. Use TLS and host-level
authorization for agents connected across different machines.
"""
import base64
from pathlib import Path
import socket
import tempfile
import threading

from nexo import AgentSocketSession, SocketFramedTransport

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    original = path / "image.png"
    original.write_bytes(PNG)
    a, b = socket.socketpair()
    with AgentSocketSession(
        SocketFramedTransport(a, allow_insecure=True)
    ) as sender, AgentSocketSession(
        SocketFramedTransport(b, allow_insecure=True)
    ) as receiver:
        sender_ready = threading.Thread(target=sender.negotiate, daemon=True)
        sender_ready.start()
        receiver.negotiate()
        sender_ready.join()

        tx = threading.Thread(
            target=lambda: sender.send_image_file(original, mime="image/png"),
            daemon=True,
        )
        tx.start()
        verified = receiver.receive_image_to_directory(path / "received")
        tx.join()
        assert verified.path.read_bytes() == PNG
        print("Streamed and SHA-256 verified:", verified.path.name)
