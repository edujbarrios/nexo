"""CLI: NEXO/1 data/text codec and NXI/1 image transport."""
import argparse
import json
import sys

from .codec import CodecError, benchmark, decode, encode, encode_binary
from .plaintext import decode_text, encode_text
from .transfer import (
    DEFAULT_CHUNK, DEFAULT_MAX_BYTES, receive_image, send_image,
)


def _inspection(value):
    """Payload-only codec inspection; not a model-token measurement."""
    normal = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    text = encode(value)
    binary = encode_binary(value)
    return {
        "protocol": "nexo/1",
        "json_bytes": len(normal.encode("utf-8")),
        "nexo_text_bytes": len(text.encode("utf-8")),
        "nexo_binary_bytes": len(binary),
        "nexo_text": text,
        "nexo_binary_hex": binary.hex(),
        "decoded_equal": decode(text) == value and decode(binary) == value,
        "note": "Byte lengths are not model token counts.",
    }


def main():
    parser = argparse.ArgumentParser(description="NEXO/1 messages and NXI/1 image transfers")
    parser.add_argument(
        "command", choices=(
            "encode", "decode", "bench", "inspect", "encode-text",
            "decode-text", "send-image", "receive-image",
        ),
    )
    parser.add_argument("--binary", action="store_true", help="binary NEXO/1 frame")
    parser.add_argument("--opaque", action="store_true",
                        help="base64url display of binary plain text, NOT encryption")
    parser.add_argument("--mime", default="image/png", help="MIME type for send-image")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK,
                        help="image transport chunk size in bytes")
    args = parser.parse_args()
    if args.binary and args.command not in ("encode", "decode", "encode-text", "decode-text"):
        parser.error("--binary is only valid for encode/decode and encode-text/decode-text")
    if args.opaque and args.command != "encode-text":
        parser.error("--opaque is only valid for encode-text")
    if args.binary and args.opaque:
        parser.error("--binary and --opaque are mutually exclusive")
    try:
        if args.command == "send-image":
            data = sys.stdin.buffer.read(DEFAULT_MAX_BYTES + 1)
            if len(data) > DEFAULT_MAX_BYTES:
                raise CodecError("image exceeds configured limit")
            for packet in send_image(
                data, mime=args.mime, chunk_size=args.chunk_size, text=True,
            ):
                sys.stdout.write(packet + "\n")
        elif args.command == "receive-image":
            packet_lines = (line.rstrip("\r\n") for line in sys.stdin)
            result = receive_image(packet_lines)
            sys.stdout.buffer.write(result.data)
        elif args.command == "encode-text":
            source = sys.stdin.read()
            mode = "opaque" if args.opaque else "binary" if args.binary else "text"
            frame = encode_text(source, mode=mode)
            if isinstance(frame, bytes):
                sys.stdout.buffer.write(frame)
            else:
                sys.stdout.write(frame)
        elif args.command == "decode-text":
            wire = sys.stdin.buffer.read() if args.binary else sys.stdin.read()
            sys.stdout.write(decode_text(wire))
        elif args.command == "decode":
            wire = sys.stdin.buffer.read() if args.binary else sys.stdin.read()
            print(json.dumps(decode(wire), sort_keys=True, ensure_ascii=False))
        else:
            value = json.load(sys.stdin)
            if args.command == "bench":
                print(json.dumps(benchmark(value), indent=2))
            elif args.command == "inspect":
                print(json.dumps(_inspection(value), indent=2, ensure_ascii=False))
            elif args.binary:
                sys.stdout.buffer.write(encode_binary(value))
            else:
                print(encode(value))
        return 0
    except (CodecError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        print("nexo: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
