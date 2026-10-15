# NEXO

**A compact, reversible language for communication between AI agents.**  
**Un lenguaje de intercambio compacto y reversible para agentes de IA.**

> **NEXO is an encoding, not encryption.** It transforms structured messages
> into shorter representations; anyone with the published decoder can recover
> their contents. It does not provide secrecy, authentication or security.

## ¿Qué es NEXO y cómo funciona?

Cuando dos agentes intercambian resultados, órdenes o estados, suelen enviar
JSON con muchos nombres de campos y palabras repetidas. **NEXO/1** sustituye
algunos de esos nombres y valores habituales por identificadores numéricos
predefinidos; codifica números de forma compacta y conserva los textos
desconocidos en UTF-8. El receptor reconstruye el mensaje original sin perder
información. **No se necesita que el LLM conozca el formato**: la librería
decodifica los mensajes dentro del proceso anfitrión del agente.

Por ejemplo, este mensaje:

```json
{"status":"ok","task":42,"type":"result"}
```

se puede representar de dos maneras:

**NEXO Text** — para canales que solo admiten cadenas de texto:

```text
NX1{3:.2;!1;.1;#42;.0;!0;
```

**NEXO Binary** — para transporte entre procesos:

```text
4e 58 01 07 03 00 02 08 01 00 01 03 54 00 00 08 00
```

| Representación del ejemplo | Tamaño |
|---|---:|
| JSON compacto | **41 bytes** |
| NEXO Text (UTF-8) | **25 bytes** |
| NEXO Binary | **17 bytes** |

Estos números corresponden **solo a este ejemplo**, no son un benchmark ni
una promesa de ahorro universal.

### ¿Qué significan esos símbolos y bytes?

1. **Cabecera y versión:** `NX1` identifica texto NEXO/1;
   `4e 58 01` identifica binario NEXO/1.
2. **Estructura tipada:** `{3:` en texto y `07 03` en binario
   indican un objeto con tres pares clave-valor.
3. **Diccionarios de palabras:** en este ejemplo, el índice `02`
   representa `status`, el índice `01` representa
   `task` y el `00` representa `type`.
   Los valores `ok` y `result` también tienen códigos.
4. **Números compactos:** el número `42` se transforma mediante
   ZigZag en `84` y se guarda en un varint: `54` en hexadecimal.
5. **Contenido libre:** las cadenas que no están en el diccionario se
   transmiten en UTF-8 con su longitud. Los diccionarios son fijos y
   versionados, así que emisor y receptor deben usar la misma versión.

La [especificación NEXO/1](docs/PROTOCOL.md) documenta todos los tipos,
etiquetas, diccionarios, varints, ZigZag y límites de seguridad, byte a byte.
Para ver cómo se genera el ejemplo: `echo '{"status":"ok","task":42,"type":"result"}' | python -m nexo inspect`.

### Importante: bytes ≠ tokens de IA

La representación binaria ahorra **bytes de transporte**; no se debe pegar
su hexadecimal dentro del prompt esperando ahorrar tokens del modelo. NEXO
Text puede reducir o aumentar los **tokens de contexto** según el tokenizador,
el mensaje, el sobre de comunicación y las instrucciones adicionales. NEXO
puede comparar el coste real de texto y utilizar JSON cuando sea preferible.
Las imágenes se transmiten como bytes externos identificados por SHA-256,
no como un supuesto «lenguaje visual encriptado».

## How it works (English)

NEXO/1 is a **versioned, lossless structured-message encoding**, not a cipher.
It uses typed fields, frozen dictionaries for frequent keys and values,
compact ZigZag/varint integers, and length-delimited UTF-8 for other strings.
The same message can travel as a text frame (`NX1…`) or binary
frame (`4e5801…`). A receiving agent's **host application** runs
the decoder; the LLM itself does not need to interpret an opaque wire format.

**Optimization is measured, not assumed.** A smaller binary frame does not
necessarily consume fewer model tokens. With a supplied target tokenizer,
the Python SDK compares complete serialized message envelopes and falls
back to compact JSON when NEXO is not a net improvement on that measure.
Additional prompt/tool framing must be accounted for separately.

> **Experimental v0.1.0.** No PyPI release or model-independent token-savings
> claim. The project is **source-available under a restrictive
> Attribution–NonCommercial–NoDerivatives license**, not OSI open source.

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
outside the local benchmark.

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
