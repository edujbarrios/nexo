"""Bounds-checked binary and UTF-8 text reader."""
from .constants import MAX_FRAME
from .errors import CodecError

class _Reader:
    def __init__(self, raw):
        if len(raw) > MAX_FRAME:
            raise CodecError("frame size limit exceeded")
        self.raw, self.pos = raw, 0

    def take(self, n):
        if n < 0 or n > len(self.raw) - self.pos:
            raise CodecError("truncated frame")
        data = self.raw[self.pos:self.pos + n]
        self.pos += n
        return data

    def byte(self):
        return self.take(1)[0]

    def decimal(self, delimiter):
        start = self.pos
        while self.pos < len(self.raw) and self.raw[self.pos] != delimiter:
            self.pos += 1
            if self.pos - start > 64:
                raise CodecError("numeric field too long")
        if self.pos == len(self.raw):
            raise CodecError("unterminated numeric field")
        raw = self.raw[start:self.pos]
        self.pos += 1
        if not raw or any(b < 48 or b > 57 for b in raw):
            raise CodecError("invalid unsigned number")
        return int(raw)

    def signed(self):
        start = self.pos
        while self.pos < len(self.raw) and self.raw[self.pos] != 59:
            self.pos += 1
            if self.pos - start > 64:
                raise CodecError("numeric field too long")
        if self.pos == len(self.raw):
            raise CodecError("unterminated number")
        raw = self.raw[start:self.pos]
        self.pos += 1
        try:
            return raw.decode("ascii")
        except UnicodeError as exc:
            raise CodecError("non-ASCII number") from exc

    def string(self):
        try:
            return self.take(self.decimal(58)).decode("utf-8")
        except UnicodeError as exc:
            raise CodecError("invalid UTF-8") from exc

    def varint(self):
        n = 0
        for shift in range(0, 70, 7):
            b = self.byte()
            if shift == 63 and b > 1:
                raise CodecError("varint overflow")
            n |= (b & 127) << shift
            if b < 128:
                # V1 varints have a single shortest representation.
                if shift and b == 0:
                    raise CodecError("non-canonical varint")
                return n
        raise CodecError("varint overflow")

    def binary_string(self):
        try:
            return self.take(self.varint()).decode("utf-8")
        except UnicodeError as exc:
            raise CodecError("invalid UTF-8") from exc


