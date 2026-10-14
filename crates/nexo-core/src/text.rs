//! Human-transportable NEXO/1 codec, UTF-8 length framed.
use serde_json::{Map, Number, Value};
use crate::constants::{TEXT_MAGIC, KEYS, VALUES, key_id, value_id};
use crate::error::{Result, CodecError, fail, guard_count, guard_depth, guard_frame};
use crate::reader::{Reader, count};

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
/// Encode a JSON value to UTF-8 NEXO/1. Reversible, not guaranteed token-efficient.
pub fn encode_text(value: &Value) -> Result<String> {
    let mut out = TEXT_MAGIC.to_vec();
    write_text(value, &mut out, 0)?;
    guard_frame(&out)?;
    String::from_utf8(out).map_err(|_| CodecError("unexpected invalid UTF-8".to_string()))
}

pub(crate) fn read_text(r: &mut Reader<'_>, depth: usize) -> Result<Value> {
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
