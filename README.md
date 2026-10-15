# NEXO

**A compact, reversible message encoding for cooperating AI agents.**

NEXO is an experimental serialization protocol for structured messages between
AI-agent applications. It provides a dependency-free Python SDK and a separate
Rust core. The agent's **host application** handles the encoding and decoding;
the language model does not need to learn a new wire grammar.

> **Encoding is not encryption.** NEXO does not hide the contents of a message.
> Anyone with the protocol decoder can recover the original data. It provides
> no secrecy, authentication, or authorization.

## What is NEXO?

Agents routinely exchange requests, tool results, status updates, and other
structured data. Compact JSON works well but often repeats field names and
common values. **NEXO/1** represents some frequent keys and string values with
small, predefined dictionary IDs, encodes integers efficiently, and preserves
unknown strings as length-prefixed UTF-8.

The encoding is **lossless and reversible** for supported JSON-compatible
values. Two compatible applications can reconstruct the same message without
asking an LLM to parse the encoded form.

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

Images and large files should be sent through an authenticated external
storage mechanism with SHA-256 references in messages; this does not reduce
the token cost of interpreting an image with a multimodal model.

> **Experimental v0.1.0.** No PyPI release or universal token-efficiency claim
> has been established. Both peers must support the same protocol version.
> NEXO is **source-available**, not OSI-approved open source. See the
> [restrictive license](LICENSE) before using the code.

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
`nexo.TOOL_SCHEMAS` provides framework-agnostic tool definitions.


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
