# NEXO/1 wire protocol — experimental specification

Exactly one JSON-compatible value is contained in each frame: null, bool,
signed i64, finite f64, UTF-8 string, array, or string-keyed object.

## Invariants

- Text header: `NX1` (3 UTF-8 bytes).
- Binary header: hexadecimal `4e5801`.
- String lengths measure UTF-8 **bytes**, not characters.
- Dictionary indexes are frozen in V1 and shared by Rust and Python.
- Object keys are deterministically sorted.
- Max frame 8 MiB; max depth 64; max elements per container 100,000.
- Unknown versions, duplicate keys and trailing garbage are rejected.
- Changes to tags, dictionary IDs or semantics require a new wire version.

## Text mode tags

| Tag | Definition |
|---|---|
| `_` | null |
| `+` and `-` | true and false |
| `#<i64>;` | signed integer |
| `^<float>;` | finite float |
| `:<utf8-byte-length>:<bytes>` | string |
| `!<id>;` | string from value dictionary |
| `[<count>:<items>` | array |
| `{<count>:<pairs>` | object |
| `.<id>;` | dictionary object key |

Literal keys use string framing. Braces and brackets do not require closing
characters because sizes provide exact boundaries.

## Binary mode

| Tag (hex) | Meaning |
|---|---|
| `00` | null |
| `01`, `02` | false, true |
| `03` | zigzag-encoded i64 as unsigned varint |
| `04` | big-endian IEEE-754 f64 |
| `05` | varint length and raw UTF-8 |
| `06` | varint count and array items |
| `07` | varint count and object pairs |
| `08` | value dictionary ID as varint |

Binary object keys are tag `00` + dictionary index, or tag `01` +
length-prefixed UTF-8 bytes.

## Golden conformance vector

Input:
```json
{"status":"ok","task":42,"type":"result"}
```

Text:
```text
NX1{3:.2;!1;.1;#42;.0;!0;
```

Binary hexadecimal:
```text
4e58010703000208010001035400000800
```

NEXO is not encryption, image compression or an LLM native tokenizer.
Image bytes should be delivered separately; a reference manifest can contain
`mime`, `size`, `sha256`, and `ref` fields.


## How NEXO actually encodes bytes

NEXO uses **type-length-value tags and a frozen pair of codebooks**, not
Base64 or a secret bit alphabet. The encoder walks a supported JSON value
recursively, writes one byte indicating the type, then writes the value.
Dictionary entries replace frequent *field names* and *string values*
with small integer IDs. Unknown names and values are encoded as raw UTF-8.
Decoding reconstructs the same logical values and does not require a model.

### A full byte-by-byte example

Input:

```json
{"status":"ok","task":42,"type":"result"}
```

Binary hex: `4e58010703000208010001035400000800`.

| Offset | Hex | Interpretation |
|---|---|---|
| 0–2 | `4e 58 01` | Protocol marker `NX`, binary version `01` |
| 3 | `07` | Object |
| 4 | `03` | Number of key/value pairs: 3 |
| 5–6 | `00 02` | Key from codebook, index 2 = `status` |
| 7–8 | `08 01` | Value codebook index 1 = `ok` |
| 9–10 | `00 01` | Key codebook index 1 = `task` |
| 11–12 | `03 54` | Signed integer: zigzag(42) = 84 = 0x54 |
| 13–14 | `00 00` | Key codebook index 0 = `type` |
| 15–16 | `08 00` | Value codebook index 0 = `result` |

The **complete binary frame is 17 bytes**. The equivalent compact
JSON is longer in bytes. That does *not* establish lower LLM token cost
because LLM tokenizers operate on text rather than this binary frame.

#### Unsigned varint and ZigZag

A varint writes 7 data bits per byte, with bit 7 signaling continuation.
For example, 300 decimal becomes `ac 02` because its lower seven
bits are `2c` and the continuation bit is set.

Signed integers use `zigzag(n) = (n << 1) ^ (n >> 63)` in
signed-64-bit arithmetic, then unsigned varint. Thus `0 → 0`,
`−1 → 1`, `1 → 2`, `−2 → 3`, `42 → 84`.
Small negative integers are almost as economical as small positives.

#### Strings and UTF-8 length

The string `ñ🤖` contains two Unicode code points, but
**six UTF-8 bytes**: `c3 b1 f0 9f a4 96`. It is encoded
as: `05 06 c3 b1 f0 9f a4 96`, where `05` is the
type tag, `06` is the byte length and the remaining six bytes
are the actual string. No Base64 inflation is involved.

#### Floats and nested values

A float uses the tag `04` followed by 8 IEEE-754 bytes in
big-endian order. Arrays begin with tag `06` and a varint element
count, followed by recursively encoded elements. Objects begin with
`07` and a pair count, then key/value pairs in sorted key order.

### How text differs from binary

Because many agent APIs require text, NEXO also provides UTF-8 frames
starting with `NX1`. The exact same input becomes:

```text
NX1{3:.2;!1;.1;#42;.0;!0;
```


Here, `{3:` means an object of three pairs; `.2;`
is the key code for `status` and `!1;` the value
code for `ok`. Text-mode strings have explicit UTF-8 byte
lengths, so no arbitrary punctuation can corrupt field boundaries.

Python provides a convenience façade (`encode()`,
`encode_binary()`, `decode()`) over this grammar;
Rust implements the same domain protocol. Agents should call the library
**outside** their LLM context and pass the decoded result into the model only
when the model actually needs it.

The single source of cross-language golden examples is
[fixtures/conformance.json](../fixtures/conformance.json).
Both Python and Rust test it. An optional PyO3-wheel CI job checks that
the native Python binding produces the identical bytes.

### Limits and security

V1 accepts only JSON-compatible data with signed-64-bit integers and
finite floats. Frame size is limited to 8 MiB; container item count and
nesting depth are bounded. Unknown tags, duplicate object keys, bad UTF-8
and trailing bytes are rejected. **Encoding is not authentication, encryption,
authorization or sanitization of agent instructions.**

## Canonical unsigned varints

NEXO/1 writers emit unsigned varints in their *shortest* byte representation.
Decoders reject redundant high-order zero groups (for example, `80 00`
instead of `00`) and unsigned 64-bit overflow. This removes multiple
byte spellings for the same integer value. The fixed rejection vectors
in [fixtures/invalid_frames.json](../fixtures/invalid_frames.json) are
tested by both Rust and Python.

## Plain-text and opaque display formats

NEXO/1 already supports a UTF-8 string at the top level; no JSON object is
necessary. For example, `Hello agents` becomes `NX1:12:Hello agents`
in text mode, or `4e5801050c48656c6c6f206167656e7473`
in binary mode. The Python SDK exposes `encode_text` and
`decode_text` to make this use case explicit.

A convenience presentation `NXO1:` followed by RFC 4648-style
URL-safe Base64 wraps a complete NEXO/1 binary frame. Decoding Base64 followed
by the existing binary decoder restores the string. This display wrapper is
**not encrypted or compressed**, and is never a substitute for TLS/AEAD.

## NXI/1 attachment transport extension

NXI/1 carries **actual binary file contents** in bounded chunks. It is
separate from the NEXO/1 JSON-compatible value format; no NEXO/1 tags or
dictionaries have been modified. Consumers must negotiate both NEXO support
and the explicit `nxi/1` attachment capability.

All binary packets start with four bytes `4e 58 49 01` (ASCII
`NXI` plus binary version 1) followed by a one-byte kind:

| Kind | Wire fields |
|---|---|
| `4d` (`M`) | `u32be(metadata_length)` + NEXO/1 binary metadata |
| `44` (`D`) | `sha256_digest[32]` + `u32be(chunk_index)` + `u32be(data_length)` + raw chunk bytes |

The metadata is a NEXO/1 binary object with exactly the fields
`manifest`, `chunk_size`, and `chunk_count`.
The manifest has exactly `ref`, `sha256`,
`size`, and `mime`. Hashes use SHA-256 of the
complete original file; `ref` is `sha256:<64 lowercase hex>`.
The chunk count must equal ceiling(size / chunk_size). The final chunk may
be shorter; no other packet may be. An empty file consists of metadata only.

Implementations accept a maximum 4 KiB metadata object, 1 MiB data chunk,
and by default 64 MiB per complete attachment. A receiver must reject extra,
missing, duplicate, out-of-order, oversized, corrupted, or unknown-version
packets. A transfer requires one dedicated receiver instance; interleaved
transfers need independently managed sessions at the host transport layer.

A text-only presentation starts with `NXI1:` plus standard
Base64 of each complete binary packet. This is a presentation encoding
only; it increases size and does not provide secrecy.

**Security:** SHA-256 verifies unkeyed content integrity, not sender identity
or authorization. Authenticate and encrypt the *external* transport.
The SDK does not connect to remote hosts on its own and does not parse,
render, or sanitize the transferred image pixels. Media decoding and
multimodal model inputs remain the caller's responsibility.


## NXF/1 network framing (optional host transport adapter)

NXF/1 is not a new NEXO core value format and does not change NEXO/1 or
NXI/1 codecs. It frames multiple *complete* control, message and binary
attachment packets on one **ordered, reliable byte stream** (typically TLS):

| Offset | Size | Definition |
|---|---:|---|
| 0 | 4 bytes | `4e 58 46 01` = `NXF` plus version 1 |
| 4 | 1 byte | packet kind `43` (C), `45` (E), or `49` (I) |
| 5 | 4 bytes | unsigned big-endian payload length |
| 9 | length bytes | exactly one packet payload |

- **C:** capability advertisement JSON encoded as UTF-8, using
  `nexo.advertise_capabilities()` and processed by
  `AgentChannel.from_peer_capabilities`. Each peer sends a C
  packet, then receives the peer's C packet before sending NEXO data.
- **E:** UTF-8 JSON containing exactly one agent envelope with `format`
  and `payload` fields, processed by the existing agent
  encoder/decoder. May contain plain-text strings or structured values.
- **I:** one full **binary** NXI/1 metadata/data packet. Packet count and
  sizes come from NXI/1; the session reads packets until SHA-256 and the
  advertised size are verified. Transport framing does not re-encode images.

Control/envelope payloads are limited to 8 MiB; I payloads are limited
to 1 MiB data plus bounded NXI metadata and framing. The decoder checks the
length **before** allocating the payload and rejects unknown versions,
unexpected packet kinds, malformed/duplicate-key JSON and truncated streams.
Packets of a different kind cannot be silently interpreted as image data.

Capability negotiation is **directional**: the remote peer's declaration
determines what this agent may send. The *local* declaration determines what
this agent agrees to receive and its inbound size limits. NXF/1 sessions
process a single image transfer at a time (multiple independent sockets or
a future protocol are needed for concurrent transfers).

### Security boundary

NXF/1 **does not implement cryptography itself**. The reference client
`SocketFramedTransport.connect_tls(host, port)` uses Python
TLS with trusted root certificate and hostname validation enabled. A normal
HTTP(S) endpoint will not speak this custom framed protocol; deploy a peer
server that speaks NXF/1 over TLS. Incoming server-side TLS sockets require
appropriate certificates and (when needed) client-certificate verification.

The application must additionally authorize peer identities and prevent
replays and unauthorized access to exchanged content. An explicit
`allow_insecure=True` bypass exists **only** to demonstrate
local socketpair() communication in tests. Image SHA-256 checks detect
accidental/unauthenticated corruption but are not message authentication;
the TLS and host authorization layer supplies that boundary.

`AgentSocketSession` supports text, structured messages and
image transfers but does not provide retries, disk spill, resumability,
multi-attachment multiplexing or asynchronous networking. Remote deployment
requires suitable connection lifetimes, timeouts, access controls and
application-level error handling.


### Disk-backed NXI/1 streaming adapters

`FileAttachmentSender` reads a local file in bounded
`chunk_size` blocks, first computing the full SHA-256 then
emitting ordinary NXI/1 metadata and data frames. The sender checks its
read-back hash and size so mutations during the transfer cannot silently
produce a mismatched output.

`FileAttachmentReceiver` processes the **same NXI/1 frame
format** as the in-memory receiver, but appends chunks into a private
temporary file. After verifying the exact advertised size and SHA-256, the
caller invokes `commit()`. It creates the destination
`<digest>` filename with an atomic exclusive hard link
(no overwrite) inside a trusted root and removes the temporary file.
Incomplete, corrupted, wrong-MIME and uncommitted transfers must not
publish any output. On-disk paths are controlled by the receiver, never
taken from sender filenames.

The high-level `receive_file_to_directory(..., image_only=True)`
helper and NXF/1 session's `receive_image_to_directory` use
this strategy. The transport itself is still TLS-only for remote peers;
SHA-256 alone is not sender authentication. Disk persistence and crash
durability are separate concerns and require host filesystem policy.

## NEXO64/1 — versioned binary-to-text alphabet

Syntax: `NX64/1:<payload>:<crc32>` where the payload uses an unpadded,
permuted Base64url alphabet and the CRC32 is eight lowercase hex digits.
The standard alphabet is
`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_`.
The NEXO64 alphabet is frozen as:

`nexo_alphabet[i] = standard_alphabet[(37*i + 11) mod 64]`, for `i = 0..63`.

37 is coprime with 64, making this a reversible mapping. Serialize binary
bytes using RFC 4648 Base64url, strip `=` padding, replace each standard
symbol with its NEXO64 counterpart, and append CRC32 of the original bytes.
Decoders reverse the mapping, require canonical Base64, check the checksum
and enforce a maximum decoded size. **This is not encryption.** The public
alphabet and CRC32 cannot protect against deliberate tampering or disclosure.

## NXE64/1 — AES-256-GCM authenticated encryption

Syntax: `NXE64/1:<payload>:<crc32>`, with the same NEXO64 mapping applied to
`nonce[12] || AES-256-GCM-ciphertext || authentication-tag[16]`.
The CRC32 covers that complete binary payload, but provides no security;
the AES-GCM tag is the cryptographic integrity/authentication mechanism.
Keys are exactly 32 random bytes. Every encryption generates a random
96-bit nonce via the OS cryptographic randomness provider.

Additional authenticated data is the binary prefix
`b"NEXO64/AES-256-GCM/1\x00"` followed by the caller-provided AAD.
Encrypted NXI/1 packets use application AAD `b"NXI/1"`; each packet
receives a fresh nonce, preserving the existing NXI/1 wire format after
decryption. Receivers configured with a key reject non-encrypted packets
to prevent a plaintext downgrade. AES-GCM rejects modified ciphertext,
incorrect AAD and incorrect keys.

Key establishment, sender identity, replay resistance and authorization
are outside this encoding. Do not substitute a secret alphabet or a CRC
for authenticated encryption. `cryptography` is an optional Python extra.
