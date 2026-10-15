"""CLI: python -m nexo encode|decode|bench|inspect [--binary]."""
import argparse
import json
import sys

from .codec import CodecError, benchmark, decode, encode, encode_binary


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
    parser = argparse.ArgumentParser(description="NEXO/1 agent message codec")
    parser.add_argument("command", choices=("encode", "decode", "bench", "inspect"))
    parser.add_argument("--binary", action="store_true", help="binary stdin/stdout for codec")
    args = parser.parse_args()
    if args.binary and args.command in ("bench", "inspect"):
        parser.error("--binary is only valid for encode/decode")
    try:
        if args.command == "decode":
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
    except (CodecError, ValueError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print("nexo: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
