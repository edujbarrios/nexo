"""Reproducible payload AND serialized-envelope comparisons.

Runs with stdlib only for JSON and NEXO. Optional TOON and tokenizer support:

    python benchmarks/run.py
    python benchmarks/run.py --toon
    python benchmarks/run.py --toon --model gpt-4o

Neither output contains real API billable input/output costs, hidden chat
framing or vision billing. Always report negative and unsupported comparisons.
"""
import argparse
from importlib.metadata import version
import json
from pathlib import Path

from nexo import benchmark, compare_peer_formats


def _compact_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tokens(value, tokenizer):
    return len(tokenizer(value)) if tokenizer is not None else None


def compare_corpus(corpus, tokenizer=None, toon=None, nexo_setup_tokens=0):
    """Compare text representations with strict round-trip checks.

    'toon' is an injected module/object with .dumps and .loads methods;
    deliberately optional so the core package stays dependency free.
    """
    if type(nexo_setup_tokens) is not int or nexo_setup_tokens < 0:
        raise ValueError("nexo_setup_tokens must be nonnegative")
    results = []
    toon_supported = 0
    for index, obj in enumerate(corpus):
        baseline = benchmark(obj, tokenizer=tokenizer)
        envelope = (
            compare_peer_formats(
                obj, tokenizer, nexo_setup_tokens=nexo_setup_tokens,
            ) if tokenizer is not None else None
        )
        row = {
            "sample_index": index,
            "json_bytes": baseline["json_bytes"],
            "nexo_text_bytes": baseline["nexo_bytes"],
            "nexo_binary_bytes": len(__import__("nexo").encode_binary(obj)),
            "json_payload_tokens": baseline["json_tokens"],
            "nexo_payload_tokens": baseline["nexo_tokens"],
            "envelope": envelope,
        }
        if toon is not None:
            try:
                encoded = toon.dumps(obj)
                restored = toon.loads(encoded)
                if restored != obj:
                    raise ValueError("TOON round-trip did not preserve JSON value")
                if not isinstance(encoded, str):
                    raise TypeError("TOON encoder did not return text")
            except (ValueError, TypeError, OverflowError) as exc:
                row["toon"] = {"supported": False, "error": type(exc).__name__}
            else:
                toon_supported += 1
                full = _compact_json({"format": "toon", "payload": encoded})
                row["toon"] = {
                    "supported": True,
                    "bytes": len(encoded.encode("utf-8")),
                    "payload_tokens": _tokens(encoded, tokenizer),
                    "envelope_tokens": _tokens(full, tokenizer),
                }
        results.append(row)

    summary = {
        "sample_count": len(results),
        "tokenizer_enabled": tokenizer is not None,
        "toon_enabled": toon is not None,
        "toon_supported": toon_supported if toon is not None else None,
        "json_bytes_total": sum(row["json_bytes"] for row in results),
        "nexo_text_bytes_total": sum(row["nexo_text_bytes"] for row in results),
        "nexo_binary_bytes_total": sum(row["nexo_binary_bytes"] for row in results),
        "json_payload_tokens_total": (
            sum(row["json_payload_tokens"] for row in results)
            if tokenizer is not None else None
        ),
        "nexo_payload_tokens_total": (
            sum(row["nexo_payload_tokens"] for row in results)
            if tokenizer is not None else None
        ),
        "json_envelope_tokens_total": (
            sum(row["envelope"]["json_envelope_tokens"] for row in results)
            if tokenizer is not None else None
        ),
        "nexo_envelope_effective_tokens_total": (
            sum(row["envelope"]["nexo_effective_tokens"] for row in results)
            if tokenizer is not None else None
        ),
        "toon_bytes_total_supported_only": (
            sum(row["toon"]["bytes"] for row in results if row["toon"]["supported"])
            if toon is not None else None
        ),
        "toon_envelope_tokens_total_supported_only": (
            sum(row["toon"]["envelope_tokens"] for row in results
                if row["toon"]["supported"])
            if toon is not None and tokenizer is not None else None
        ),
        "json_bytes_total_on_toon_supported_samples": (
            sum(row["json_bytes"] for row in results if row["toon"]["supported"])
            if toon is not None else None
        ),
        "results": results,
        "limitations": (
            "The corpus is synthetic; JSON and NEXO are valid for all samples. "
            "TOON comparisons are only meaningful on supported samples. "
            "Token counts are model-tokenizer estimates for payloads or a "
            "serialized envelope, excluding tools, provider frames, actual "
            "model responses, and extra instruction tokens beyond any manually "
            "supplied NEXO setup cost. Binary bytes are NOT LLM tokens."
        ),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Compare NEXO/1 text and binary, compact JSON and optional TOON",
    )
    parser.add_argument("--model", help="Optional tiktoken model name, e.g. gpt-4o")
    parser.add_argument("--toon", action="store_true", help="Compare official toon-format")
    parser.add_argument(
        "--nexo-setup-tokens", type=int, default=0,
        help="Extra instruction tokens per message (requires --model)",
    )
    args = parser.parse_args()
    if args.nexo_setup_tokens < 0:
        parser.error("--nexo-setup-tokens must be nonnegative")
    if args.nexo_setup_tokens and not args.model:
        parser.error("--nexo-setup-tokens requires --model")

    tokenizer, tokenizer_version, toon, toon_version = None, None, None, None
    if args.model:
        try:
            import tiktoken
        except ImportError:
            parser.error("install optional tokenizers with pip install '.[tokens]'")
        tokenizer = tiktoken.encoding_for_model(args.model).encode
        tokenizer_version = version("tiktoken")
    if args.toon:
        try:
            import toon_format
        except ImportError:
            parser.error("install optional TOON benchmark: pip install toon-format")
        toon = toon_format
        toon_version = version("toon-format")

    corpus_path = Path(__file__).with_name("corpus.json")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    summary = compare_corpus(
        corpus, tokenizer=tokenizer, toon=toon,
        nexo_setup_tokens=args.nexo_setup_tokens,
    )
    summary["tokenizer_model"] = args.model
    summary["tokenizer_version"] = tokenizer_version
    summary["toon_version"] = toon_version
    summary["nexo_setup_tokens_per_message"] = args.nexo_setup_tokens
    summary["corpus"] = str(corpus_path.name)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
