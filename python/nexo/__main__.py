"""CLI: NEXO/1 data/text codec and NXI/1 image transport."""
import argparse
import json
from pathlib import Path
import sys

from .codec import CodecError, benchmark, decode, encode, encode_binary
from .plaintext import decode_text, encode_text
from .nexo64 import encode_nexo64, decode_nexo64, seal_nexo64, open_nexo64
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
            "encode64", "decode64", "seal64", "open64",
        ),
    )
    parser.add_argument("--binary", action="store_true", help="binary NEXO/1 frame")
    parser.add_argument("--opaque", action="store_true",
                        help="base64url display of binary plain text, NOT encryption")
    parser.add_argument("--mime", default="image/png", help="MIME type for send-image")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK,
                        help="image transport chunk size in bytes")
    parser.add_argument(
        "--encoding", choices=("base64", "nexo64", "encrypted"),
        default="base64", help="text encoding of image packets (send-image)",
    )
    parser.add_argument(
        "--key-file", help="path to a private 32-byte AES-256-GCM key file",
    )
    args = parser.parse_args()
    if args.encoding != "base64" and args.command != "send-image":
        parser.error("--encoding is only valid for send-image")
    if args.key_file and args.command not in (
        "send-image", "receive-image", "seal64", "open64",
    ):
        parser.error("--key-file is only valid for encrypted image or NEXO64 operations")
    if args.command in ("seal64", "open64") and not args.key_file:
        parser.error("seal64 and open64 require --key-file")
    if args.command == "send-image":
        if (args.encoding == "encrypted") != bool(args.key_file):
            parser.error("--encoding encrypted requires --key-file, and keys require encrypted mode")

    if args.binary and args.command not in ("encode", "decode", "encode-text", "decode-text"):
        parser.error("--binary is only valid for encode/decode and encode-text/decode-text")
    if args.opaque and args.command != "encode-text":
        parser.error("--opaque is only valid for encode-text")
    if args.binary and args.opaque:
        parser.error("--binary and --opaque are mutually exclusive")
    try:
        key = Path(args.key_file).read_bytes() if args.key_file else None
        if key is not None and len(key) != 32:
            raise ValueError("--key-file must contain exactly 32 raw bytes")
        if args.command == "encode64":
            data = sys.stdin.buffer.read(DEFAULT_MAX_BYTES + 1)
            if len(data) > DEFAULT_MAX_BYTES:
                raise CodecError("binary data exceeds configured limit")
            sys.stdout.write(encode_nexo64(data))
        elif args.command == "decode64":
            frame = sys.stdin.read().rstrip("\r\n")
            sys.stdout.buffer.write(decode_nexo64(frame))
        elif args.command == "seal64":
            data = sys.stdin.buffer.read(DEFAULT_MAX_BYTES + 1)
            if len(data) > DEFAULT_MAX_BYTES:
                raise CodecError("binary data exceeds configured limit")
            sys.stdout.write(seal_nexo64(data, key))
        elif args.command == "open64":
            frame = sys.stdin.read().rstrip("\r\n")
            sys.stdout.buffer.write(open_nexo64(frame, key))
        elif args.command == "send-image":
            data = sys.stdin.buffer.read(DEFAULT_MAX_BYTES + 1)
            if len(data) > DEFAULT_MAX_BYTES:
                raise CodecError("image exceeds configured limit")
            for packet in send_image(
                data, mime=args.mime, chunk_size=args.chunk_size,
                text={"base64": True, "nexo64": "nexo64",
                      "encrypted": "encrypted"}[args.encoding], key=key,
            ):
                sys.stdout.write(packet + "\n")
        elif args.command == "receive-image":
            packet_lines = (line.rstrip("\r\n") for line in sys.stdin)
            result = receive_image(packet_lines, key=key)
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
    except (CodecError, ValueError, TypeError, UnicodeError, RecursionError,
            ImportError, OSError) as exc:
        print("nexo: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
