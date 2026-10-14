"""Reproducible serialization comparison; install SDK in editable mode first.

Usage:
    python benchmarks/run.py
    python benchmarks/run.py --model gpt-4o
This only counts payloads. Actual production prompt / tool overhead is separate.
"""
import argparse
import json
from pathlib import Path

from nexo import benchmark


def main():
    parser = argparse.ArgumentParser(description="Compare NEXO/1 text with compact JSON")
    parser.add_argument("--model", help="Model name for optional tiktoken measurements")
    args = parser.parse_args()

    tokenizer = None
    tokenizer_version = None
    if args.model:
        try:
            import tiktoken
            from importlib.metadata import version
        except ImportError as exc:
            parser.error("install optional tokenizer: pip install '.[tokens]'")
        tokenizer = tiktoken.encoding_for_model(args.model).encode
        tokenizer_version = version("tiktoken")

    corpus = json.loads((Path(__file__).with_name("corpus.json")).read_text("utf-8"))
    data = [benchmark(message, tokenizer=tokenizer) for message in corpus]
    summary = {
        "codec": "nexo/1",
        "baseline": "compact-json",
        "sample_count": len(data),
        "tokenizer_model": args.model,
        "tokenizer_package_version": tokenizer_version,
        "note": "Payload-only; excludes peer envelope, tool calls, instructions, images.",
        "json_bytes_total": sum(row["json_bytes"] for row in data),
        "nexo_bytes_total": sum(row["nexo_bytes"] for row in data),
        "json_tokens_total": (
            sum(row["json_tokens"] for row in data) if tokenizer else None
        ),
        "nexo_tokens_total": (
            sum(row["nexo_tokens"] for row in data) if tokenizer else None
        ),
        "individual_results": data,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
