"""CLI: python -m nexo encode|decode|bench [--binary]."""
import argparse
import json
import sys

from .codec import CodecError, benchmark, decode, encode, encode_binary


def main():
    parser = argparse.ArgumentParser(description="NEXO/1 agent message codec")
    parser.add_argument("command", choices=("encode", "decode", "bench"))
    parser.add_argument("--binary", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "decode":
            raw = sys.stdin.buffer.read() if args.binary else sys.stdin.read()
            print(json.dumps(decode(raw), sort_keys=True, ensure_ascii=False))
        else:
            value = json.load(sys.stdin)
            if args.command == "bench":
                print(json.dumps(benchmark(value), indent=2))
            elif args.binary:
                sys.stdout.buffer.write(encode_binary(value))
            else:
                print(encode(value))
        return 0
    except (CodecError, UnicodeError, json.JSONDecodeError) as exc:
        print("nexo: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
