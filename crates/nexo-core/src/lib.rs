//! NEXO/1 deterministic, versioned serialization of JSON-compatible values.
//! Machine transport favors bytes; text favors compatibility with agent tool results.
//! Token savings depend on model tokenizers and MUST be benchmarked independently.

use serde_json::{Map, Number, Value};
use std::{error::Error, fmt};

pub const MAX_FRAME: usize = 8 * 1024 * 1024;
pub const MAX_DEPTH: usize = 64;
pub const MAX_ITEMS: usize = 100_000;
const TEXT_MAGIC: &[u8] = b"NX1";
const BINARY_MAGIC: &[u8] = b"NX\x01";

pub const KEYS: &[&str] = &[
    "type", "task", "status", "data", "id", "name", "files", "changed",
    "content", "message", "role", "agent", "timestamp", "error", "result",
    "tool", "args", "output", "mime", "sha256", "size", "ref", "version",
    "metadata", "input", "model", "tokens", "cost",
];
pub const VALUES: &[&str] = &[
    "result", "ok", "error", "request", "pending", "running", "done",
    "failed", "system", "user", "assistant", "tool", "text", "image",
    "file", "success", "warning",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CodecError(pub String);
impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl Error for CodecError {}

type Result<T> = std::result::Result<T, CodecError>;
fn fail<T>(message: &str) -> Result<T> {
    Err(CodecError(message.to_string()))
}
fn guard_depth(depth: usize) -> Result<()> {
    if depth > MAX_DEPTH { fail("nesting limit exceeded") } else { Ok(()) }
}
fn guard_count(count: usize) -> Result<()> {
    if count > MAX_ITEMS { fail("container item limit exceeded") } else { Ok(()) }
}
fn guard_frame(data: &[u8]) -> Result<()> {
    if data.len() > MAX_FRAME { fail("frame size limit exceeded") } else { Ok(()) }
}
fn key_id(name: &str) -> Option<usize> {
    KEYS.iter().position(|item| *item == name)
}
fn value_id(name: &str) -> Option<usize> {
    VALUES.iter().position(|item| *item == name)
}
fn append_decimal(out: &mut Vec<u8>, n: usize, delimiter: u8) {
    out.extend_from_slice(n.to_string().as_bytes());
    out.push(delimiter);
}
fn text_string(out: &mut Vec<u8>, s: &str) {
    out.push(b':');
    append_decimal(out, s.len(), b':');
    out.extend_from_slice(s.as_bytes());
}
fn write_text(value: &Value, out: &mut Vec<u8>, depth: usize) -> Result<()> {
    guard_depth(depth)?;
    match value {
        Value::Null => out.push(b'_'),
        Value::Bool(true) => out.push(b'+'),
        Value::Bool(false) => out.push(b'-'),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push(b'#');
                out.extend_from_slice(i.to_string().as_bytes());
                out.push(b';');
            } else if n.is_u64() {
                return fail("integer must fit signed 64 bits");
            } else {
                let f = n.as_f64().ok_or_else(|| CodecError("invalid float".to_string()))?;
                if !f.is_finite() { return fail("non-finite float"); }
                out.push(b'^');
                out.extend_from_slice(n.to_string().as_bytes());
                out.push(b';');
            }
        }
        Value::String(s) => {
            if let Some(i) = value_id(s) {
                out.push(b'!');
                append_decimal(out, i, b';');
            } else {
                text_string(out, s);
            }
        }
        Value::Array(items) => {
            guard_count(items.len())?;
            out.push(b'[');
            append_decimal(out, items.len(), b':');
            for item in items { write_text(item, out, depth + 1)?; }
        }
        Value::Object(map) => {
            guard_count(map.len())?;
            out.push(b'{');
            append_decimal(out, map.len(), b':');
            // serde_json::Map is sorted by key by default (no preserve_order).
            for (key, item) in map {
                if let Some(i) = key_id(key) {
                    out.push(b'.');
                    append_decimal(out, i, b';');
                } else {
                    text_string(out, key);
                }
                write_text(item, out, depth + 1)?;
            }
        }
    }
    Ok(())
}
fn write_varint(out: &mut Vec<u8>, mut n: u64) {
    while n >= 128 {
        out.push((n as u8 & 0x7f) | 0x80);
        n >>= 7;
    }
    out.push(n as u8);
}
fn binary_string(out: &mut Vec<u8>, s: &str) {
    write_varint(out, s.len() as u64);
    out.extend_from_slice(s.as_bytes());
}
fn write_binary(value: &Value, out: &mut Vec<u8>, depth: usize) -> Result<()> {
    guard_depth(depth)?;
    match value {
        Value::Null => out.push(0),
        Value::Bool(false) => out.push(1),
        Value::Bool(true) => out.push(2),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                out.push(3);
                write_varint(out, ((i as u64) << 1) ^ ((i >> 63) as u64));
            } else if n.is_u64() {
                return fail("integer must fit signed 64 bits");
            } else {
                let f = n.as_f64().ok_or_else(|| CodecError("invalid float".to_string()))?;
                if !f.is_finite() { return fail("non-finite float"); }
                out.push(4);
                out.extend_from_slice(&f.to_be_bytes());
            }
        }
        Value::String(s) => {
            if let Some(i) = value_id(s) {
                out.push(8);
                write_varint(out, i as u64);
            } else {
                out.push(5);
                binary_string(out, s);
            }
        }
        Value::Array(items) => {
            guard_count(items.len())?;
            out.push(6);
            write_varint(out, items.len() as u64);
            for item in items { write_binary(item, out, depth + 1)?; }
        }
        Value::Object(map) => {
            guard_count(map.len())?;
            out.push(7);
            write_varint(out, map.len() as u64);
            for (key, item) in map {
                if let Some(i) = key_id(key) {
                    out.push(0);
                    write_varint(out, i as u64);
                } else {
                    out.push(1);
                    binary_string(out, key);
                }
                write_binary(item, out, depth + 1)?;
            }
        }
    }
    Ok(())
}

/// Encode a JSON value to UTF-8 NEXO/1. Reversible, not guaranteed token-efficient.
pub fn encode_text(value: &Value) -> Result<String> {
    let mut out = TEXT_MAGIC.to_vec();
    write_text(value, &mut out, 0)?;
    guard_frame(&out)?;
    String::from_utf8(out).map_err(|_| CodecError("unexpected invalid UTF-8".to_string()))
}

/// Encode a JSON value to compact binary NEXO/1.
pub fn encode_binary(value: &Value) -> Result<Vec<u8>> {
    let mut out = BINARY_MAGIC.to_vec();
    write_binary(value, &mut out, 0)?;
    guard_frame(&out)?;
    Ok(out)
}
struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}
impl<'a> Reader<'a> {
    fn new(data: &'a [u8]) -> Result<Self> {
        guard_frame(data)?;
        Ok(Self { data, pos: 0 })
    }
    fn take(&mut self, size: usize) -> Result<&'a [u8]> {
        if size > self.data.len().saturating_sub(self.pos) {
            return fail("truncated frame");
        }
        let slice = &self.data[self.pos..self.pos + size];
        self.pos += size;
        Ok(slice)
    }
    fn byte(&mut self) -> Result<u8> { Ok(self.take(1)?[0]) }
    fn until(&mut self, delimiter: u8) -> Result<&'a [u8]> {
        let start = self.pos;
        while self.pos < self.data.len() && self.data[self.pos] != delimiter {
            self.pos += 1;
            if self.pos - start > 64 { return fail("numeric field too long"); }
        }
        if self.pos == self.data.len() { return fail("unterminated numeric field"); }
        let result = &self.data[start..self.pos];
        self.pos += 1;
        Ok(result)
    }
    fn decimal(&mut self, delimiter: u8) -> Result<usize> {
        let raw = self.until(delimiter)?;
        if raw.is_empty() || !raw.iter().all(u8::is_ascii_digit) {
            return fail("invalid unsigned number");
        }
        std::str::from_utf8(raw).map_err(|_| CodecError("invalid number".to_string()))?
            .parse::<usize>().map_err(|_| CodecError("numeric field overflow".to_string()))
    }
    fn signed(&mut self) -> Result<&'a str> {
        std::str::from_utf8(self.until(b';')?)
            .map_err(|_| CodecError("invalid numeric text".to_string()))
    }
    fn string(&mut self) -> Result<String> {
        let len = self.decimal(b':')?;
        let raw = self.take(len)?;
        let value = std::str::from_utf8(raw)
            .map_err(|_| CodecError("invalid UTF-8".to_string()))?;
        Ok(value.to_owned())
    }
    fn varint(&mut self) -> Result<u64> {
        let mut value = 0u64;
        for i in 0..10 {
            let byte = self.byte()?;
            if i == 9 && byte > 1 { return fail("varint overflow"); }
            value |= ((byte & 0x7f) as u64) << (i * 7);
            if byte < 128 { return Ok(value); }
        }
        fail("varint overflow")
    }
    fn binary_string(&mut self) -> Result<String> {
        let len = usize::try_from(self.varint()?)
            .map_err(|_| CodecError("string length overflow".to_string()))?;
        std::str::from_utf8(self.take(len)?)
            .map(|s| s.to_owned())
            .map_err(|_| CodecError("invalid UTF-8".to_string()))
    }
}
fn count(r: &mut Reader<'_>, text: bool) -> Result<usize> {
    let n = if text {
        r.decimal(b':')?
    } else {
        usize::try_from(r.varint()?).map_err(|_| CodecError("count overflow".to_string()))?
    };
    guard_count(n)?;
    Ok(n)
}
fn read_text(r: &mut Reader<'_>, depth: usize) -> Result<Value> {
    guard_depth(depth)?;
    match r.byte()? {
        b'_' => Ok(Value::Null),
        b'+' => Ok(Value::Bool(true)),
        b'-' => Ok(Value::Bool(false)),
        b'#' => {
            let n = r.signed()?.parse::<i64>()
                .map_err(|_| CodecError("invalid signed integer".to_string()))?;
            Ok(Value::Number(Number::from(n)))
        }
        b'^' => {
            let n = r.signed()?.parse::<f64>()
                .map_err(|_| CodecError("invalid float".to_string()))?;
            let number = Number::from_f64(n)
                .ok_or_else(|| CodecError("non-finite float".to_string()))?;
            Ok(Value::Number(number))
        }
        b':' => Ok(Value::String(r.string()?)),
        b'!' => {
            let i = r.decimal(b';')?;
            let v = VALUES.get(i).ok_or_else(|| CodecError("unknown value code".to_string()))?;
            Ok(Value::String((*v).to_owned()))
        }
        b'[' => {
            let n = count(r, true)?;
            let mut array = Vec::with_capacity(n.min(1024));
            for _ in 0..n { array.push(read_text(r, depth + 1)?); }
            Ok(Value::Array(array))
        }
        b'{' => {
            let n = count(r, true)?;
            let mut map = Map::new();
            for _ in 0..n {
                let key = match r.byte()? {
                    b'.' => {
                        let id = r.decimal(b';')?;
                        KEYS.get(id).ok_or_else(|| CodecError("unknown key code".to_string()))?
                            .to_string()
                    }
                    b':' => r.string()?,
                    _ => return fail("invalid key tag"),
                };
                if map.contains_key(&key) { return fail("duplicate object key"); }
                map.insert(key, read_text(r, depth + 1)?);
            }
            Ok(Value::Object(map))
        }
        _ => fail("invalid text tag"),
    }
}
fn read_binary(r: &mut Reader<'_>, depth: usize) -> Result<Value> {
    guard_depth(depth)?;
    match r.byte()? {
        0 => Ok(Value::Null),
        1 => Ok(Value::Bool(false)),
        2 => Ok(Value::Bool(true)),
        3 => {
            let n = r.varint()?;
            let signed = ((n >> 1) as i64) ^ (-((n & 1) as i64));
            Ok(Value::Number(Number::from(signed)))
        }
        4 => {
            let bytes: [u8; 8] = r.take(8)?.try_into()
                .map_err(|_| CodecError("invalid float bytes".to_string()))?;
            let number = Number::from_f64(f64::from_be_bytes(bytes))
                .ok_or_else(|| CodecError("non-finite float".to_string()))?;
            Ok(Value::Number(number))
        }
        5 => Ok(Value::String(r.binary_string()?)),
        8 => {
            let n = usize::try_from(r.varint()?)
                .map_err(|_| CodecError("value code overflow".to_string()))?;
            Ok(Value::String(VALUES.get(n)
                .ok_or_else(|| CodecError("unknown value code".to_string()))?.to_string()))
        }
        6 => {
            let n = count(r, false)?;
            let mut array = Vec::with_capacity(n.min(1024));
            for _ in 0..n { array.push(read_binary(r, depth + 1)?); }
            Ok(Value::Array(array))
        }
        7 => {
            let n = count(r, false)?;
            let mut map = Map::new();
            for _ in 0..n {
                let key = match r.byte()? {
                    0 => {
                        let idx = usize::try_from(r.varint()?)
                            .map_err(|_| CodecError("key code overflow".to_string()))?;
                        KEYS.get(idx).ok_or_else(|| CodecError("unknown key code".to_string()))?
                            .to_string()
                    }
                    1 => r.binary_string()?,
                    _ => return fail("invalid binary key tag"),
                };
                if map.contains_key(&key) { return fail("duplicate object key"); }
                map.insert(key, read_binary(r, depth + 1)?);
            }
            Ok(Value::Object(map))
        }
        _ => fail("invalid binary tag"),
    }
}

/// Decode exactly one whole text or binary frame, rejecting trailing data.
pub fn decode(data: &[u8]) -> Result<Value> {
    let mut reader = Reader::new(data)?;
    if data.starts_with(TEXT_MAGIC) {
        reader.take(TEXT_MAGIC.len())?;
        let v = read_text(&mut reader, 0)?;
        if reader.pos != data.len() { return fail("trailing bytes"); }
        Ok(v)
    } else if data.starts_with(BINARY_MAGIC) {
        reader.take(BINARY_MAGIC.len())?;
        let v = read_binary(&mut reader, 0)?;
        if reader.pos != data.len() { return fail("trailing bytes"); }
        Ok(v)
    } else {
        fail("unknown NEXO version or header")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn matches_python_golden_text_vector() {
        let data = json!({"type":"result", "task":42, "status":"ok"});
        let encoded = encode_text(&data).unwrap();
        assert_eq!(encoded, "NX1{3:.2;!1;.1;#42;.0;!0;");
        assert_eq!(decode(encoded.as_bytes()).unwrap(), data);
    }
    #[test]
    fn matches_python_golden_binary_vector() {
        let data = json!({"type":"result", "task":42, "status":"ok"});
        let expected = b"NX\x01\x07\x03\x00\x02\x08\x01\x00\x01\x03\x54\x00\x00\x08\x00";
        assert_eq!(encode_binary(&data).unwrap(), expected);
        assert_eq!(decode(expected).unwrap(), data);
    }
    #[test]
    fn roundtrip_nested_and_unicode() {
        let samples = [
            json!(null), json!(true), json!(false),
            json!({"name":"ñ🤖", "files":[{"changed":true}, null, -3]}),
            json!({"status":"pending", "task":-9223372036854775808_i64}),
            json!(1.5), json!(-0.0),
        ];
        for data in samples {
            assert_eq!(decode(encode_text(&data).unwrap().as_bytes()).unwrap(), data);
            assert_eq!(decode(&encode_binary(&data).unwrap()).unwrap(), data);
        }
    }
    #[test]
    fn rejects_invalid_frames() {
        for data in [
            &b"NX1"[..], &b"NX1_!"[..], &b"NX1[100001:"[..], &b"NX1!999;"[..],
            &b"NX\x01\xff"[..], &b"NX\x01\x06\x80"[..],
            &b"NX1{2::1:x_:1:x_"[..],
        ] {
            assert!(decode(data).is_err(), "accepted invalid frame: {data:?}");
        }
    }
    #[test]
    fn signed_integer_limits() {
        let min = json!(i64::MIN);
        let max = json!(i64::MAX);
        for n in [min, max] {
            assert_eq!(decode(encode_binary(&n).unwrap().as_slice()).unwrap(), n);
        }
        assert!(encode_binary(&json!(u64::MAX)).is_err());
    }
}
