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
