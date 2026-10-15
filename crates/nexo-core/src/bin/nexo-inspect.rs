//! Developer-facing interoperability probe: JSON stdin -> NEXO text and binary hex.
//! This tool is for CI and diagnosis, not a streaming transport endpoint.
use serde_json::{json, Value};
use std::io::{self, Read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().take(8 * 1024 * 1024).read_to_string(&mut input)?;
    let value: Value = serde_json::from_str(&input)?;
    let encoded_text = nexo_core::encode_text(&value)?;
    let encoded_binary = nexo_core::encode_binary(&value)?;
    let binary_hex: String = encoded_binary
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();

    let response = json!({
        "format": "nexo/1",
        "text": encoded_text,
        "binary_hex": binary_hex,
        "roundtrip_text": nexo_core::decode(encoded_text.as_bytes())? == value,
        "roundtrip_binary": nexo_core::decode(&encoded_binary)? == value,
    });
    println!("{}", serde_json::to_string(&response)?);
    Ok(())
}
