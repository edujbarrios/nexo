"""Show NEXO64 custom image-to-text coding and real AES-GCM encryption.

Install the optional crypto dependency for the encrypted demonstration:
    pip install -e ".[crypto]"

The NEXO64 alphabet is public and provides no secrecy. NXE64/1 is
authenticated encryption, powered by cryptography, not by the alphabet.
"""
import base64
import secrets

from nexo import (
    encode_nexo64, decode_nexo64, seal_nexo64, open_nexo64,
    send_image, receive_image,
)

image = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)
coded = encode_nexo64(image)
assert decode_nexo64(coded) == image
print("Custom binary-to-text frame prefix:", coded.split(":", 1)[0])

key = secrets.token_bytes(32)  # ephemeral demo key, never logged
try:
    encrypted = seal_nexo64(image, key)
except ImportError:
    print("Optional cryptography dependency missing; skipping encrypted example")
else:
    assert open_nexo64(encrypted, key) == image
    protected_packets = send_image(image, text="encrypted", key=key)
    assert receive_image(protected_packets, key=key).data == image
    print("Encrypted image transport succeeded with AES-256-GCM")
