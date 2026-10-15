"""Transfer an actual image over an OS socket between two NEXO agent hosts.

socket.socketpair() uses a LOCAL socket for a portable self-contained demo.
For remote agents, use an authenticated, encrypted TLS/WebSocket/gRPC channel.
NEXO itself provides framing and SHA-256 verification, NOT encryption.
"""
import base64
import socket
import struct

from nexo import AgentChannel, advertise_capabilities

png_bytes = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)

receiver_offer = advertise_capabilities()
sender = AgentChannel.from_peer_capabilities(receiver_offer)
receiver = AgentChannel.from_peer_capabilities(advertise_capabilities())

# Socket framing is separate from the NXI/1 attachment-frame contents.
def take_exact(sock, length):
    data = bytearray()
    while len(data) < length:
        piece = sock.recv(length - len(data))
        if not piece:
            raise EOFError("socket closed in the middle of an attachment frame")
        data.extend(piece)
    return bytes(data)


def incoming(sock):
    while True:
        four_bytes = sock.recv(4)
        if not four_bytes:
            break
        while len(four_bytes) < 4:
            four_bytes += take_exact(sock, 4 - len(four_bytes))
        size = struct.unpack(">I", four_bytes)[0]
        if size > 1024 * 1024 + 8192:
            raise ValueError("socket frame size limit exceeded")
        yield take_exact(sock, size)


with socket.socketpair() as (tx, rx):
    for packet in sender.send_image(png_bytes, mime="image/png", chunk_size=20):
        tx.sendall(struct.pack(">I", len(packet)) + packet)
    tx.shutdown(socket.SHUT_WR)
    restored = receiver.receive_image(incoming(rx))

assert restored.data == png_bytes
print("Image transferred over a socket:", restored.manifest["ref"])
