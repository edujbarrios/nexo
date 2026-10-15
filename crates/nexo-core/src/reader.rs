//! Bounds-checked byte reader; no unchecked indexing of untrusted frames.
use crate::error::{Result, CodecError, fail, guard_frame, guard_count};

pub(crate) struct Reader<'a> {
    data: &'a [u8],
    pub(crate) pos: usize,
}
impl<'a> Reader<'a> {
    pub(crate) fn new(data: &'a [u8]) -> Result<Self> {
        guard_frame(data)?;
        Ok(Self { data, pos: 0 })
    }
    pub(crate) fn take(&mut self, size: usize) -> Result<&'a [u8]> {
        if size > self.data.len().saturating_sub(self.pos) {
            return fail("truncated frame");
        }
        let slice = &self.data[self.pos..self.pos + size];
        self.pos += size;
        Ok(slice)
    }
    pub(crate) fn byte(&mut self) -> Result<u8> { Ok(self.take(1)?[0]) }
    pub(crate) fn until(&mut self, delimiter: u8) -> Result<&'a [u8]> {
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
    pub(crate) fn decimal(&mut self, delimiter: u8) -> Result<usize> {
        let raw = self.until(delimiter)?;
        if raw.is_empty() || !raw.iter().all(u8::is_ascii_digit) {
            return fail("invalid unsigned number");
        }
        std::str::from_utf8(raw).map_err(|_| CodecError("invalid number".to_string()))?
            .parse::<usize>().map_err(|_| CodecError("numeric field overflow".to_string()))
    }
    pub(crate) fn signed(&mut self) -> Result<&'a str> {
        std::str::from_utf8(self.until(b';')?)
            .map_err(|_| CodecError("invalid numeric text".to_string()))
    }
    pub(crate) fn string(&mut self) -> Result<String> {
        let len = self.decimal(b':')?;
        let raw = self.take(len)?;
        let value = std::str::from_utf8(raw)
            .map_err(|_| CodecError("invalid UTF-8".to_string()))?;
        Ok(value.to_owned())
    }
    pub(crate) fn varint(&mut self) -> Result<u64> {
        let mut value = 0u64;
        for i in 0..10 {
            let byte = self.byte()?;
            if i == 9 && byte > 1 { return fail("varint overflow"); }
            value |= ((byte & 0x7f) as u64) << (i * 7);
            if byte < 128 {
                // Reject redundant high-order zero groups: one integer, one wire form.
                if i > 0 && byte == 0 { return fail("non-canonical varint"); }
                return Ok(value);
            }
        }
        fail("varint overflow")
    }
    pub(crate) fn binary_string(&mut self) -> Result<String> {
        let len = usize::try_from(self.varint()?)
            .map_err(|_| CodecError("string length overflow".to_string()))?;
        std::str::from_utf8(self.take(len)?)
            .map(|s| s.to_owned())
            .map_err(|_| CodecError("invalid UTF-8".to_string()))
    }
}
pub(crate) fn count(r: &mut Reader<'_>, text: bool) -> Result<usize> {
    let n = if text {
        r.decimal(b':')?
    } else {
        usize::try_from(r.varint()?).map_err(|_| CodecError("count overflow".to_string()))?
    };
    guard_count(n)?;
    Ok(n)
}
