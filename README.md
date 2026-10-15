# NEXO

**Compact, reversible messages for cooperating AI agents.**

NEXO is an experimental serialization protocol with a dependency-free Python
SDK and an independent Rust core. **An agent developer can say "Use NEXO"**
and call a stable library API, rather than forcing an LLM to learn the wire
format.

> Experimental v0.1.0. No PyPI release has been published. Byte savings are
> not necessarily token savings. No universal token-efficiency claim has been
> validated. Both peers must have a compatible decoder.

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

CLI: `python -m nexo encode`, `python -m nexo decode` and
`python -m nexo bench` use stdin and stdout. For agent function calling,
`nexo.TOOL_SCHEMAS` provides framework-agnostic tool definitions.


## Reproducible baseline benchmarks

Run `python benchmarks/run.py` to compare payload byte sizes against compact
JSON. Install the optional tokenizer extra, then run
`python benchmarks/run.py --model gpt-4o` for tokenizer-specific payload
counts. Results may show NEXO losing; envelope-aware figures still exclude actual LLM
provider framing, tool schemas, and any model-instruction overhead not explicitly supplied.

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
- `python/nexo/agent.py`: application-layer capability and cost strategy.
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
