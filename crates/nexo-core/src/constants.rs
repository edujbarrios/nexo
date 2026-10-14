//! Frozen NEXO/1 vocabularies and version identifiers.

pub const MAX_FRAME: usize = 8 * 1024 * 1024;
pub const MAX_DEPTH: usize = 64;
pub const MAX_ITEMS: usize = 100_000;
pub(crate) const TEXT_MAGIC: &[u8] = b"NX1";
pub(crate) const BINARY_MAGIC: &[u8] = b"NX\x01";

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


pub(crate) fn key_id(name: &str) -> Option<usize> {
    KEYS.iter().position(|item| *item == name)
}
pub(crate) fn value_id(name: &str) -> Option<usize> {
    VALUES.iter().position(|item| *item == name)
}
