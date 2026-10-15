# NEXO

[![PyPI version](https://img.shields.io/pypi/v/nexo-agent-protocol?label=PyPI)](https://pypi.org/project/nexo-agent-protocol/)
[![Python versions](https://img.shields.io/pypi/pyversions/nexo-agent-protocol?label=Python)](https://pypi.org/project/nexo-agent-protocol/)
[![CI](https://github.com/edujbarrios/nexo/actions/workflows/ci.yml/badge.svg)](https://github.com/edujbarrios/nexo/actions/workflows/ci.yml)

**A compact, reversible message encoding for cooperating AI agents.**

NEXO is an experimental, versioned **encoding and communication protocol**
for structured messages, plain text, and media exchanged between AI agents.
It defines reversible wire representations that cooperating applications can
interpret without asking a language model to learn a new grammar. The protocol
also distinguishes transport-byte optimization from model-token efficiency.

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

> **Experimental v0.1.0.** The PyPI badge reports published releases, which
> may lag behind the source repository. No universal token-efficiency claim
> has been established. Both peers must support the same protocol version.
> NEXO is **source-available**, not OSI-approved open source. See the
> [restrictive license](LICENSE) before using the code.

## The Python library: designed for AI agents

**The NEXO Python SDK is built for applications that host AI agents**—not
for an LLM to read or manually decode an opaque string. The sender's host
serializes a message, peers advertise supported formats, and the receiver's
host decodes the message before handing its contents to the model.

- **Agent-to-agent messages:** typed data and ordinary plain text, with
  explicit NEXO/1 capability negotiation and a JSON fallback.
- **Real media transfer:** images and files sent as verified NXI/1 packets
  or written to disk using bounded streaming.
- **Secure transport options:** NXF/1 framing over externally authenticated
  TLS, plus optional AES-256-GCM encrypted NXE64/1 presentations.
- **Practical integrations:** standalone Python, function-tool schemas,
  a CLI, and optional separately packaged Rust acceleration.

The PyPI distribution is **`nexo-agent-protocol`** and the Python import
remains `nexo`. Check the badge above for PyPI publication status.

```bash
python -m pip install nexo-agent-protocol
```

A minimal exchange between two compatible agent hosts:

```python
from nexo import AgentChannel, advertise_capabilities

# In production, exchange capabilities through an authenticated channel.
remote_offer = advertise_capabilities()
sender = AgentChannel.from_peer_capabilities(remote_offer)
receiver = AgentChannel.from_peer_capabilities(advertise_capabilities())

wire = sender.send({"type": "result", "task": 42, "status": "ok"})
print(wire)
print(receiver.receive(wire))
```

**Output** for this message (without an optional token-cost tokenizer):

```text
{'format': 'nexo/1', 'payload': 'NX1{3:.2;!1;.1;#42;.0;!0;'}
{'status': 'ok', 'task': 42, 'type': 'result'}
```

The host must verify that the peer can decode the negotiated version.
An LLM cannot be assumed to understand compressed NEXO frames on its own.
For actual remote connections, see [NXF/1 socket sessions](#authenticated-remote-agent-connections)
and the [agent pair example](examples/agent_pair.py).

## Why this repository exists

**Agents communicate constantly, but message encoding, capability discovery,
media transfer, and cost selection are often left to separate application
integrations.** JSON is interoperable yet repeats common keys; binary codecs
can save network bytes but cannot simply be pasted into LLM prompts; image
attachments and access controls must be engineered separately.

NEXO is an experiment in making those pieces work together behind one small,
**host-side API**. Its core question is practical: *can two cooperating agents
exchange typed data, arbitrary text and actual images using a reversible,
versioned protocol, while selecting the cheapest supported representation
for each transport and model?* The LLM does not need to memorize NEXO syntax.

### Where NEXO stands out

| Capability | What NEXO provides | What this does **not** imply |
|---|---|---|
| Typed agent messages | Versioned binary and text NEXO/1; deterministic dictionaries, Rust/Python parity fixtures | Not universally smaller than JSON or other codecs |
| Token-cost-aware fallback | Host compares complete text envelopes for a supplied model tokenizer and chooses JSON when NEXO loses | Not automatic provider-billing optimization |
| Plug-in communication | Versioned peer negotiation, `AgentChannel`, tool schemas and NXF/1 socket frames | Not a universal agent discovery or authorization service |
| Real image/file delivery | NXI/1 chunked transfers, SHA-256 checks, optional disk streaming and text-only presentation | Not image understanding or fewer vision tokens |
| Privacy option | Optional AES-256-GCM encrypted NXE64 frames and locally scoped replay tracking | Not secure key distribution, durable replay protection or an audited production messaging system |
| Inspectable engineering | Frozen golden vectors, hostile-input tests, benchmark comparisons and CI across Python and Rust | No claim to beat every alternative |

**Choosing an alternative is sometimes better.** Use plain JSON for
maximum compatibility or small one-off messages; a standard binary format
such as CBOR/MessagePack for general-purpose byte serialization; and TOON
when its text layout is more efficient for your model/workload. NEXO's
distinction is the *integrated agent-facing communication path*, not a
guaranteed compression ratio or a proprietary cryptographic primitive.

**Evidence, not marketing:** on a published nine-message synthetic corpus
using the `gpt-4o` tokenizer, NEXO Binary used fewer transport bytes than
compact JSON, **but NEXO Text consumed more tokens than JSON**; TOON had
the lowest serialized-envelope token count in that comparison. See
[measured benchmarks](docs/BENCHMARKS.md) and reproduce the results before
choosing a format for real traffic. NEXO is experimental and source-available
under the restrictive [NEXO license](LICENSE), not an OSI-open-source library.

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

**Output:** No stdout; the assertion succeeds. `frame` starts with `NX64/1:`.

### Real image encryption: NXE64/1 with AES-256-GCM

Install the optional `crypto` extra (`python -m pip install 'nexo-agent-protocol[crypto]'` from PyPI, or `'.[crypto]'` from this checkout). `NXE64/1:` wraps AES-256-GCM ciphertext and a fresh random
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

**Output:** No stdout; both assertions succeed, and encrypted bytes vary on each run.

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

**Output:** No stdout; both representations decode to `Hello!`.

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

**Output:** The first command prints `NX1:11:Hello agent`; the second an `NXO1:` reversible wrapper; the last prints `Hello agent`.

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

**Output:** No stdout on success. The server must implement NXF/1 over TLS; this illustrative hostname is **not a working server**.

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

**Output:** `received/<verified_sha256>` followed by that file's verified manifest. The digest depends on your input.

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

**Output:** A Python dictionary containing `mime: 'image/png'`, `size: <your file bytes>`, `sha256: <digest>`, and `ref: 'sha256:<digest>'`.

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

## Runnable examples and their outputs

Run the following from a checkout after `python -m pip install -e .`.
These are actual **stdout results observed in GitHub Actions** on the
[verified main CI run](https://github.com/edujbarrios/nexo/actions/runs/38731051914),
with irrelevant setup output omitted. The binaries/hash values below are from
the checked-in example inputs. Changing an image changes its SHA-256.

| Command | Expected stdout (representative lines) |
|---|---|
| `python examples/agent_pair.py` | `Transport: {'format': 'nexo/1', 'payload': 'NX1{3:.2;!1;.1;#42;.0;!0;'}` then `Decoded: {'status': 'ok', 'task': 42, 'type': 'result'}`; also prints the host instruction text |
| `python examples/handshake.py` | `Negotiated: nexo/1 Decoded: {'status': 'pending', 'task': 42, 'type': 'request'}` |
| `python examples/attachments.py` | A dictionary with `type: 'image'` and a SHA-256 manifest (`size: 19` for the built-in test blob) |
| `python examples/plain_text.py` | Begins `text : NX1:50:Hello, agent B. This is plain text, not JSON. 🤖`; ends `Channel round-trip: nexo/1` |
| `python examples/image_transfer.py` | `Image transferred over a socket: sha256:6b1048f8a6d40bac0b2954c18fefa40c4ea7a96120fc2e54b7317c0e43c2bbec` |
| `python examples/socket_session.py` | `Transport: NXF/1; image: sha256:6b1048f8a6d40bac0b2954c18fefa40c4ea7a96120fc2e54b7317c0e43c2bbec` |
| `python examples/stream_image_file.py` | `Streamed and SHA-256 verified: 6b1048f8a6d40bac0b2954c18fefa40c4ea7a96120fc2e54b7317c0e43c2bbec` |
| `python examples/nexo64_images.py` | `Custom binary-to-text frame prefix: NX64/1`, followed by an AES-GCM success line if `nexo[crypto]` is installed, or an optional-dependency skip line otherwise |
| `python examples/replay_guard.py` | With `nexo[crypto]`: `First authenticated message: accepted` then `Repeated encrypted message: rejected`. Without the optional extra: an installation hint |

The corresponding [source files](examples/) perform additional
round-trip assertions; a successful assertion produces **no stdout**.
Random AES-GCM nonces make ciphertext different on every run, so encrypted
byte strings are intentionally **not** provided as fixed example outputs.

### CLI example: actual decoded sizes

```bash
echo '{"status":"ok","task":42,"type":"result"}' | python -m nexo inspect
```

**Output (from CI; fields shown exactly):**

```json
{
  "protocol": "nexo/1",
  "json_bytes": 41,
  "nexo_text_bytes": 25,
  "nexo_binary_bytes": 17,
  "nexo_text": "NX1{3:.2;!1;.1;#42;.0;!0;",
  "nexo_binary_hex": "4e58010703000208010001035400000800",
  "decoded_equal": true,
  "note": "Byte lengths are not model token counts."
}
```

**Other command outputs:** `python -m nexo encode-text` prints an
`NX1:...` text frame; `encode64` prints `NX64/1:...` and `seal64` prints
`NXE64/1:...`. When redirected into `photo.n64`, `photo.nxe64`, or
`restored.png`, the commands write **files**, not status text. Their
round-trip result is exact byte equality with the original input image;
encrypted strings vary because every encryption uses a fresh nonce.

## PyPI distribution and release policy

Distribution: **`nexo-agent-protocol`**; Python import: **`nexo`**; CLI:
**`nexo`**. Do not confuse this project with the separately owned `nexo`
distribution on PyPI. The proposed new distribution name is **not reserved**
until the maintainer registers/publishes it.

A first `0.1.0` release is prepared but not yet uploaded. After GitHub
Actions and PyPI Trusted Publishing have been configured, pushing an approved
`v0.1.0` tag triggers the release workflow. See
[PyPI publishing and TestPyPI instructions](docs/PUBLISHING.md).

The pure-Python release does not need Rust. The optional `nexo-native` PyO3
extension remains a **separate, unpublished distribution** until a
cross-platform wheel release matrix and name ownership are validated.
This source-available software retains its **noncommercial/no-derivatives**
license on PyPI.

## Installation

Python 3.9+. The default SDK needs no Rust compiler. The PyPI distribution
is `nexo-agent-protocol`; the import and CLI command remain `nexo`.
The short PyPI distribution name `nexo` belongs to another project.

```sh
python -m pip install nexo-agent-protocol
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

**Output:** Prints the `AGENT_INSTRUCTIONS` string. The final equality assertion is silent.

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

**Output:** No stdout. `frame` is an envelope containing `format` and `payload`.

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

**Output:** No stdout; decoding restores the original object.

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

**Output:** No stdout. The selected envelope format depends on the supplied tokenizer and the specific message.

### Low-level interface

```python
from nexo import Codec, encode, decode, benchmark

message = {"type": "result", "task": 42, "status": "ok"}
assert decode(encode(message)) == message
assert decode(Codec(profile="binary").encode(message)) == message
print(benchmark(message))   # no tokenizer: token fields are None
```

**Output:** A metrics dictionary with JSON/NEXO byte counts; token fields are `None` without a tokenizer.

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

**Output:** No stdout; the SHA-256 reference resolves back to identical bytes.

For multiple cooperating processes on the **same trusted filesystem**, use
`FileBlobStore` for persistent, content-addressed data:

```python
from nexo import FileBlobStore
store = FileBlobStore("./agent-shared-blobs")
reference = store.add(b"image bytes", mime="image/png")
assert store.resolve(reference) == b"image bytes"
```

**Output:** No stdout; the stored bytes match the original.

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
