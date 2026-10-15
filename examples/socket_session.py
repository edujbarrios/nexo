"""Two cooperating agents sharing NXF/1 control, messages and images.

This is deliberately LOCAL and uses insecure socketpair() for demonstration.
Remote agent clients should use AgentSocketSession.connect_tls(host, port).
A remote server must provide its own TLS endpoint and peer authorization.
"""
import base64
import socket
import threading

from nexo import AgentSocketSession, SocketFramedTransport

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def negotiate_other_agent(session, errors):
    try:
        session.negotiate()
    except Exception as exc:
        errors.append(exc)


left, right = socket.socketpair()
with AgentSocketSession(SocketFramedTransport(left, allow_insecure=True)) as a, \
     AgentSocketSession(SocketFramedTransport(right, allow_insecure=True)) as b:
    errors = []
    worker = threading.Thread(target=negotiate_other_agent, args=(b, errors))
    worker.start()
    a.negotiate()
    worker.join()
    if errors:
        raise errors[0]

    a.send_text("Hello from agent A.")
    assert b.receive_text() == "Hello from agent A."

    a.send_image(PNG, chunk_size=20)
    restored = b.receive_image()
    assert restored.data == PNG

    b.send({"type": "result", "status": "ok"})
    assert a.receive() == {"type": "result", "status": "ok"}

    print("Transport: NXF/1; image:", restored.manifest["ref"])
