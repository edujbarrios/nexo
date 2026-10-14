//! Error and resource-limit policy shared by all decoders.
use std::{error::Error, fmt};
use crate::constants::{MAX_DEPTH, MAX_ITEMS, MAX_FRAME};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CodecError(pub String);
impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl Error for CodecError {}

pub type Result<T> = std::result::Result<T, CodecError>;
pub(crate) fn fail<T>(message: &str) -> Result<T> {
    Err(CodecError(message.to_string()))
}
pub(crate) fn guard_depth(depth: usize) -> Result<()> {
    if depth > MAX_DEPTH { fail("nesting limit exceeded") } else { Ok(()) }
}
pub(crate) fn guard_count(count: usize) -> Result<()> {
    if count > MAX_ITEMS { fail("container item limit exceeded") } else { Ok(()) }
}
pub(crate) fn guard_frame(data: &[u8]) -> Result<()> {
    if data.len() > MAX_FRAME { fail("frame size limit exceeded") } else { Ok(()) }
}
