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
