//! NEXO/1 deterministic, versioned serialization of JSON-compatible values.
//! Machine transport favors bytes; text favors compatibility with agent tool results.
//! Token savings depend on model tokenizers and MUST be benchmarked independently.

use serde_json::Value;


mod constants;
mod error;
mod reader;
mod text;
mod binary;

pub use constants::{KEYS, VALUES, MAX_DEPTH, MAX_ITEMS, MAX_FRAME};
pub use error::{CodecError, Result};
pub use text::encode_text;
pub use binary::encode_binary;
use constants::{TEXT_MAGIC, BINARY_MAGIC};
use error::fail;
use reader::Reader;
use text::read_text;
use binary::read_binary;

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
