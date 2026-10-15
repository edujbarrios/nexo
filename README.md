# NEXO

**A compact, reversible message encoding for cooperating AI agents.**

NEXO is an experimental serialization protocol for structured messages between
AI-agent applications. It provides a dependency-free Python SDK and a separate
Rust core. The agent's **host application** handles the encoding and decoding;
the language model does not need to learn a new wire grammar.

> **Encoding is not encryption.** NEXO/1, the legacy opaque display, and
> NEXO64/1 are reversible encodings, not ciphers. Optional NXE64/1 is an
> explicitly separate **AES-256-GCM authenticated encryption** format;
> securely distributed keys and authenticated peers are still required.

## What is NEXO?

Agents routinely exchange requests, tool results, status updates, and other
structured data. Compact JSON works well but often repeats field names and
common values. **NEXO/1** represents some frequent keys and string values with
small, predefined dictionary IDs, encodes integers efficiently, and preserves
unknown strings as length-prefixed UTF-8.

The encoding is **lossless and reversible** for supported JSON-compatible
values. Two compatible applications can reconstruct the same message without
asking an LLM to parse the encoded form. **Plain text is already a supported
NEXO/1 value**: you do not have to build a JSON object to encode a note, a
sentence, or an entire document. Images and other binary attachments use a
separate chunked NXI/1 transport format.

### One message, three representations

Take this compact JSON object:

```json
{"status":"ok","task":42,"type":"result"}
```

**NEXO Text** is designed for channels that require text:

```text
NX1{3:.2;!1;.1;#42;.0;!0;
```

**NEXO Binary** is designed for byte-oriented transport (shown in
hexadecimal for readability):

```text
4e 58 01 07 03 00 02 08 01 00 01 03 54 00 00 08 00
```

| Representation | Size for this example |
|---|---:|
| Compact JSON | **41 bytes** |
| NEXO Text (UTF-8) | **25 bytes** |
| NEXO Binary | **17 bytes** |

These are the sizes of **one illustrative message**, not measured average
savings or a guarantee that NEXO will be smaller for other messages.

### How the encoding works

1. **Identify the version.** Text frames start with `NX1`;
   binary frames start with `4e 58 01`.
2. **Write the data type and structure.** For the example, `{3:` in
   text and `07 03` in binary mean an object with three key/value pairs.
3. **Use versioned dictionaries.** Dictionary key IDs `02`,
   `01`, and `00` stand for `status`,
   `task`, and `type`. Common values such
   as `ok` and `result` also have IDs.
4. **Encode numbers efficiently.** Signed integers use ZigZag followed by
   a variable-length integer (varint). In this example, `42` maps
   to `84`, which fits in the single hexadecimal byte `54`.
5. **Preserve arbitrary strings.** Strings without a dictionary entry are
   stored as UTF-8 bytes preceded by their byte length. Both peers use
   the same frozen V1 dictionaries and decoding rules.

See the [NEXO/1 protocol specification](docs/PROTOCOL.md) for the complete
tag tables, dictionary IDs, ZigZag, varints, UTF-8 framing, and resource limits.
To inspect both encodings yourself:

```sh
echo '{"status":"ok","task":42,"type":"result"}' | python -m nexo inspect
```

### Byte savings are not LLM token savings

Binary frames can save **transport bytes**, but putting their hexadecimal
representation into an LLM prompt does not imply fewer model tokens. NEXO
Text can use fewer *or more* context tokens than JSON, depending on the model
tokenizer, message content, envelope, and additional instructions. When a
tokenizer is supplied, the SDK compares complete serialized envelopes and
falls back to JSON unless NEXO is cheaper on that measurement.

Images and large files can be sent as real NXI/1 data chunks through an
authenticated host transport, or referenced by SHA-256 when both agents
already share a trusted blob store. Neither method reduces the token cost
of interpreting an image with a multimodal model.

> **Experimental v0.1.0.** No PyPI release or universal token-efficiency claim
> has been established. Both peers must support the same protocol version.
> NEXO is **source-available**, not OSI-approved open source. See the
> [restrictive license](LICENSE) before using the code.

## NEXO64 image coding and authenticated encryption

**NEXO64/1** is a new NEXO-specific 64-symbol representation of arbitrary bytes,
including PNG, JPEG and WebP images. It uses a publicly specified permutation
of Base64's six-bit alphabet, versioned `NX64/1:` framing and a CRC32 checksum.
It is reversible, but **it is NOT encryption or compression**; binary transports
remain smaller. The checksum detects accidents, not malicious changes.

```python
from pathlib import Path
from nexo import encode_nexo64, decode_nexo64

photo = Path("photo.png").read_bytes()
frame = encode_nexo64(photo)             # NX64/1:...
assert decode_nexo64(frame) == photo
```

### Real image encryption: NXE64/1 with AES-256-GCM

Install the optional `crypto` extra (`python -m pip install '.[crypto]'` from
this checkout). `NXE64/1:` wraps AES-256-GCM ciphertext and a fresh random
nonce in the NEXO64 alphabet. Its authentication tag detects tampering or an
incorrect key. **The AES-GCM library provides the security, not the alphabet.**

```python
import secrets
from nexo import seal_nexo64, open_nexo64, send_image, receive_image

key = secrets.token_bytes(32)  # provision independently; never put in a prompt
encrypted_text = seal_nexo64(photo, key)  # NXE64/1:...
assert open_nexo64(encrypted_text, key) == photo

# Encrypt and authenticate each real NXI/1 image packet independently:
packets = list(send_image(photo, text="encrypted", key=key))
assert receive_image(packets, key=key).data == photo
```

Existing `NXI1:` Base64 and binary NXI/1 packet formats continue to work.
For the new unencrypted presentation, use `send_image(photo, text="nexo64")`.
For file-backed transfers, `send_file(path, text="encrypted", key=key)` and
`receive_file_to_directory(..., key=key)` stream image data to verified disk.
When a decryption key is supplied, NXI receivers refuse plaintext frames
instead of silently downgrading the transfer.

**Command line:**

```bash
python -m nexo encode64 < photo.png > photo.n64
python -m nexo decode64 < photo.n64 > restored.png
python -m nexo seal64 --key-file nexo.key < photo.png > photo.nxe64
python -m nexo open64 --key-file nexo.key < photo.nxe64 > restored.png
python -m nexo send-image --encoding nexo64 < photo.png > packets.txt
python -m nexo receive-image < packets.txt > restored.png
python -m nexo send-image --encoding encrypted --key-file nexo.key < photo.png > sealed.txt
python -m nexo receive-image --key-file nexo.key < sealed.txt > restored.png
```

The key file must contain exactly **32 raw bytes** and must be created and
distributed securely. Do not commit keys to Git or copy them into model
prompts. AES-GCM detects tampering, but alone it does not stop an attacker
from replaying an old valid message or establish peer identity. Use
authenticated TLS, application authorization and replay controls.

## Plain-text messages (no JSON required)

A string is a first-class NEXO/1 value. Use the explicit Python API:

```python
from nexo import encode_text, decode_text

wire = encode_text("Hello, agent B. This is just plain text.")
assert decode_text(wire) == "Hello, agent B. This is just plain text."

binary_frame = encode_text("Hello!", mode="binary")   # bytes for a byte transport
opaque_frame = encode_text("Hello!", mode="opaque")   # "NXO1:" + base64url bytes
assert decode_text(binary_frame) == decode_text(opaque_frame) == "Hello!"
```

The **opaque** form looks less readable but is standard reversible Base64:
it does **not** provide encryption, confidentiality, or improved token counts.
Plain NEXO strings usually have encoding overhead and are **not compressed
natural language**. Use TLS or another authenticated encrypted channel if the
actual message needs to remain confidential.

Command line:

```bash
printf 'Hello agent' | python -m nexo encode-text
printf 'Hello agent' | python -m nexo encode-text --opaque
printf 'Hello agent' | python -m nexo encode-text | python -m nexo decode-text
```

## Authenticated remote agent connections

For communicating across computers, NEXO includes a bounded **NXF/1**
length-framed socket adapter that transports ordinary agent messages, plain
text, and real NXI/1 image data over one connection. `connect_tls`
uses Python's standard certificate- and hostname-verifying TLS client.
This is a transport security layer, **not encryption within the NEXO codec**.

```python
from nexo import AgentSocketSession

# Connect to a server that already supports NXF/1 over authenticated TLS.
with AgentSocketSession.connect_tls("agent.example.com", 443) as peer:
    peer.negotiate()                     # both peers exchange capabilities
    peer.send_text("Hello from agent A") # arbitrary plain text, not JSON
    peer.send_image(open("photo.png", "rb").read(), mime="image/png")
```

The recipient must run the complementary NXF/1 receiver over a TLS
connection; a general-purpose HTTPS server **will not** understand these
frames. See [the local socket example](examples/socket_session.py) for
a working pair of agents on `socket.socketpair()`. Plain sockets
are rejected by default; the example explicitly uses
`allow_insecure=True` only for trusted local testing.

TLS checks a remote **server certificate and hostname**. The application must
still authorize agents and, if appropriate, require mutual TLS/client identity.
NXF/1 packets have strict size bounds, incomplete-frame detection, and
separate types for capabilities, message envelopes, and image chunks.
It does not implement retries, replay protection, concurrent multiplexed
image transfers, or an agent identity registry.

## Streaming large image files without loading them into RAM

For file-backed images, use the **disk-streaming NXI/1 adapters**. They read
the source in bounded chunks and calculate SHA-256 incrementally. The receiver
writes to a private temporary file in a trusted directory, checks size and
hash, then publishes the verified file under its digest name using an atomic
no-overwrite filesystem link.

```python
from nexo import send_file, receive_file_to_directory

frames = send_file("photo.png", mime="image/png", chunk_size=256 * 1024)
result = receive_file_to_directory(
    frames, "./received", image_only=True
)
print(result.path)      # received/<verified_sha256>
print(result.manifest)  # size, mime, hash and content-addressed ref
```

With a negotiated NXF/1 socket session, use
`session.send_image_file(path)` on the sender and
`session.receive_image_to_directory(directory)` on the receiver
instead of handling frames manually. See
[the end-to-end socket example](examples/stream_image_file.py).

This API does **not** place full image bytes in Python memory; it still reads
each chunk, keeps a SHA-256 state, and requires trusted local disk capacity.
The sender hashes the source once and reads it again to send, detecting
changes that invalidate the hash. A repeated digest filename raises
`FileExistsError` rather than overwriting existing content.
An incomplete or corrupted transfer leaves **no published file**; use a
context manager for cleanup of abandoned temporary transfers.

Transport confidentiality still requires TLS and per-agent authorization.
Storage and streaming do not change the image input cost of multimodal LLMs.

## Sending images between agents

**NXI/1 actually transports the image bytes.** Unlike a shared-store
manifest alone, the sender emits bounded binary packets containing an image
manifest and the image data in chunks. The receiver verifies chunk order,
length, total size and SHA-256 before returning a complete image. The agent
framework is responsible for carrying packets over a trusted transport.

```python
from pathlib import Path
from nexo import AgentChannel, advertise_capabilities

image = Path("photo.png").read_bytes()
remote_capabilities = advertise_capabilities()  # sent over authenticated JSON
channel = AgentChannel.from_peer_capabilities(remote_capabilities)

# Send each frame over your authenticated WebSocket, TLS stream, or message bus.
frames = list(channel.send_image(image, mime="image/png"))
received = channel.receive_image(frames)
assert received.data == image
print(received.manifest)  # mime, ref, sha256, size
```

For a text-only transport, set `text=True` in `send_image`:
packets then begin with `NXI1:` and contain Base64. Base64
increases the transfer size; it does not encrypt it. Do **not** put those
Base64 packets into the LLM context and expect image understanding or token
savings. Route image bytes into your multimodal model or image processor
through its supported API.

```bash
python -m nexo send-image --mime image/png < photo.png > packets.txt
python -m nexo receive-image < packets.txt > restored.png
```

The [image-transfer example](examples/image_transfer.py) demonstrates
two agents exchanging the actual image data over a local OS socket with
length-prefix framing. Remote integration requires an **authenticated encrypted
transport** such as TLS and appropriate permissions. NEXO's SHA-256 check
detects corruption; it does **not** prevent an attacker from replacing both
the bytes and their hash.

The default transfer limit is 64 MiB per attachment, with a maximum of
1 MiB per chunk. Receivers require an explicit `nxi/1`
capability advertisement and reject incomplete or inconsistent transfers.
NXI/1 is an extension alongside NEXO/1; it does not alter existing messages.

## Installation

Python 3.9+. The default SDK needs no Rust compiler.

```sh
python -m pip install "git+https://github.com/edujbarrios/nexo.git"
```

Alternatively clone this repository and run `python -m pip install -e .`.

## Agent-first API

```python
from nexo import prepare_peer_message, parse_peer_message, AGENT_INSTRUCTIONS

print(AGENT_INSTRUCTIONS)  # paste into the agent host's instructions
message = {"type": "result", "status": "ok", "task": 42}
frame = prepare_peer_message(message, peer_supports_nexo=True)
received = parse_peer_message(frame)
assert received == message
```

The **host application** calls the decoder. An arbitrary LLM cannot decode an
opaque NEXO frame by itself. Send a NEXO frame only after the receiving agent
has agreed it can decode `nexo/1`.

Agents can negotiate supported formats without involving the LLM:

```python
from nexo import AgentChannel, advertise_capabilities

remote_offer = advertise_capabilities()  # received as ordinary JSON
channel = AgentChannel.from_peer_capabilities(remote_offer)
frame = channel.send({"type": "request", "task": 42})
```

Capability exchange is not authentication. Host applications must authenticate
peer identities and authorize messages separately. Unknown versions default
to JSON.

For reusable host integrations, the `AgentChannel` façade keeps peer capability,
tokenizer and optional protocol setup overhead in one place:

```python
from nexo import AgentChannel

channel = AgentChannel(peer_supports_nexo=True)
outbound = channel.send({"type": "result", "task": 42})
assert channel.receive(outbound) == {"type": "result", "task": 42}
```

The optional `tokenizer` argument takes a function mapping text to a token
sequence. NEXO is selected only if the **entire serialized envelope** costs fewer
tokens than the JSON envelope. If you know the extra protocol instruction cost,
pass `nexo_setup_tokens` to account for it. The caller must still count actual
provider/tool framing, repeated prompts and any visual tokens separately.
If the message is valid JSON but outside NEXO/1's signed-i64 or depth
constraints, the agent transport automatically falls back to JSON.

```python
import tiktoken  # install optional extra: pip install ".[tokens]"
from nexo import prepare_peer_message

tokenize = tiktoken.encoding_for_model("gpt-4o").encode
frame = prepare_peer_message(
    {"type": "result", "status": "ok"},
    peer_supports_nexo=True,
    tokenizer=tokenize,
)
```

### Low-level interface

```python
from nexo import Codec, encode, decode, benchmark

message = {"type": "result", "task": 42, "status": "ok"}
assert decode(encode(message)) == message
assert decode(Codec(profile="binary").encode(message)) == message
print(benchmark(message))   # no tokenizer: token fields are None
```

CLI: `python -m nexo encode`, `decode`, `bench` and `inspect` use stdin and stdout.
Use `inspect` to see *both* wire representations and how many bytes each needs:

```sh
echo '{"status":"ok","task":42,"type":"result"}' | python -m nexo inspect
```

The inspection includes hex output for the binary wire, UTF-8 text mode,
and a reversible roundtrip check. See the byte-by-byte breakdown in
[Protocol](docs/PROTOCOL.md). For agent function calling,
`nexo.TOOL_SCHEMAS` provides framework-agnostic tool definitions, including
`nexo_encode_text` / `nexo_decode_text` for plain-text messages.


## Reproducible benchmarks

Measure NEXO text/binary, compact JSON and optionally TOON. All formats must
decode correctly before their measurements count:

```sh
python benchmarks/run.py                       # stdlib JSON vs NEXO
python -m pip install tiktoken toon-format   # optional benchmarking tools
python benchmarks/run.py --model gpt-4o --toon --nexo-setup-tokens 10
```

Reports include negative results, raw byte sizes, tokenizer-specific
payload/envelope estimates and a clear distinction between supported and
unsupported TOON inputs. Full provider framing and model inference costs are
outside the local benchmark. See [measured benchmark results](docs/BENCHMARKS.md)
for a reproducible comparison that includes cases where NEXO is worse.

To compare **local serialization throughput** for standard-library JSON,
the Python reference codec, and (if installed) the optional Rust wheel:

```sh
python benchmarks/speed.py --iterations 1000 --repeats 5
```

The throughput script checks decoding correctness and prints measured
operations per second with environment metadata. Timings are machine- and
workload-specific, **not** LLM token-savings or agent-end-to-end results.

## Images and files

Encode small **references** to binary objects rather than textifying all their
bytes into an LLM prompt. NEXO includes a demonstration memory store:

```python
from nexo import MemoryBlobStore, encode

store = MemoryBlobStore()
manifest = store.add(b"sample image bytes", mime="image/png")
wire = encode({"type": "image", "data": manifest})
assert store.resolve(manifest) == b"sample image bytes"
```

For multiple cooperating processes on the **same trusted filesystem**, use
`FileBlobStore` for persistent, content-addressed data:

```python
from nexo import FileBlobStore
store = FileBlobStore("./agent-shared-blobs")
reference = store.add(b"image bytes", mime="image/png")
assert store.resolve(reference) == b"image bytes"
```

The store verifies SHA-256 on read, rejects path-like digests, and makes
writes atomic. A shared disk is not an authenticated remote transport.
Never grant arbitrary untrusted agents write access to the store directory.

The in-memory store is local to a process. Distributed agents must supply an
authenticated shared store; the current SDK has no network-backed object store.
Image understanding still requires a proper multimodal model input.

## Development and architecture

- `crates/nexo-core/src/`: Rust wire protocol with separate text, binary,
  reader, constants and error modules.
- `crates/nexo-python/`: optional PyO3 binding layer.
- `python/nexo/codec.py`: Python public facade with internal _wire/ codec modules.
- `python/nexo/agent.py`: agent-channel facade and token-cost strategy.
- `python/nexo/negotiation.py`: explicit versioned capability negotiation.
- `python/nexo/filesystem.py`: persistent, verified attachment storage.
- `python/nexo/native.py`: optional Rust extension adapter.
- `python/nexo/tools.py`: agent function-tool adapter.
- `python/nexo/attachments.py`: content-addressed blob adapter.
- `tests/`, `examples/`, `docs/`: conformance, quickstarts and specifications.

See [AGENTS.md](AGENTS.md), [architecture](docs/ARCHITECTURE.md),
[protocol](docs/PROTOCOL.md), and [roadmap](docs/ROADMAP.md).

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
cargo test -p nexo-core
cargo check -p nexo-python
```

### Optional Rust acceleration

First install the Python SDK and Rust; then:

```sh
python -m pip install maturin
maturin develop --manifest-path crates/nexo-python/Cargo.toml
```

The native module is explicitly opt-in via `from nexo import native`. NEXO
continues to use the dependency-free Python implementation by default.

## License and attribution

**NEXO is source-available, not OSI-approved open source.**
Copyright (c) 2026 Eduardo J. Barrios. The
[NEXO Attribution–NonCommercial–NoDerivatives License 1.0](LICENSE)
allows noncommercial unmodified use and citation with attribution; modifications
and commercial use require express written authorization. The custom license
has not been independently reviewed by legal counsel. Earlier distributions
under BSD-3-Clause retain rights already granted under that earlier license.
