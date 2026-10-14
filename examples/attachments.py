"""Illustrate a content-addressed manifest without inline Base64."""
from nexo import MemoryBlobStore, decode, encode

store = MemoryBlobStore()
manifest = store.add(b"example image bytes", mime="image/png")
wire = encode({"type": "image", "data": manifest})
decoded = decode(wire)
assert store.resolve(decoded["data"]) == b"example image bytes"
print(decoded)
