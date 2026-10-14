//! Binary NEXO/1 codec with varints and zigzag signed integers.
use serde_json::{Map, Number, Value};
use crate::constants::{BINARY_MAGIC, KEYS, VALUES, key_id, value_id};
use crate::error::{Result, CodecError, fail, guard_count, guard_depth, guard_frame};
use crate::reader::{Reader, count};

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

/// Encode a JSON value to compact binary NEXO/1.
pub fn encode_binary(value: &Value) -> Result<Vec<u8>> {
    let mut out = BINARY_MAGIC.to_vec();
    write_binary(value, &mut out, 0)?;
    guard_frame(&out)?;
    Ok(out)
}
pub(crate) fn read_binary(r: &mut Reader<'_>, depth: usize) -> Result<Value> {
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

