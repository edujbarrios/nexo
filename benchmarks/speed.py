"""Reproducible local codec throughput benchmarks; never infer LLM token savings.

Usage:
    python benchmarks/speed.py --iterations 1000 --repeats 5

The native backend is reported only if the optional nexo-native extension is
installed. Each backend is checked for reversible round trips before timing.
Results are environment-dependent, not universal performance guarantees.
"""
import argparse
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from nexo import decode, encode, encode_binary, native


def _compact_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def _timed(fn, values, iterations, repeats):
    times = []
    for _ in range(repeats):
        start = perf_counter()
        for _ in range(iterations):
            for value in values:
                fn(value)
        times.append(perf_counter() - start)
    elapsed = median(times)
    operations = iterations * len(values)
    return {
        "median_seconds": round(elapsed, 6),
        "operations": operations,
        "operations_per_second": round(operations / elapsed, 1) if elapsed else None,
    }


def compare_throughput(messages, *, iterations=500, repeats=3):
    """Measure serialization and parsing throughput on the local machine.

    Input messages must be valid NEXO/1 values. Any incompatible or
    non-reversible backend raises an error rather than producing a misleading
    performance number.
    """
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    if type(iterations) is not int or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")

    backends = {
        "stdlib-json-text": (_compact_json, json.loads),
        "python-nexo-text": (encode, decode),
        "python-nexo-binary": (encode_binary, decode),
    }
    if native.available():
        backends["rust-nexo-text"] = (native.encode, native.decode)
        backends["rust-nexo-binary"] = (native.encode_binary, native.decode)

    output = {}
    for name, (encoder, decoder) in backends.items():
        frames = [encoder(message) for message in messages]
        for expected, frame in zip(messages, frames):
            if decoder(frame) != expected:
                raise ValueError(name + ": roundtrip mismatch")
        output[name] = {
            "encode": _timed(encoder, messages, iterations, repeats),
            "decode": _timed(decoder, frames, iterations, repeats),
        }

    return {
        "sample_count": len(messages),
        "iterations": iterations,
        "repeats": repeats,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "native_installed": native.available(),
        "results": output,
        "limitations": (
            "Local wall-clock timings for a synthetic corpus. Includes Python "
            "call overhead and machine load; does not measure model tokens, "
            "network transfer, framing, or end-to-end agent latency."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark NEXO codec throughput")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    corpus = json.loads(
        Path(__file__).with_name("corpus.json").read_text(encoding="utf-8"),
    )
    report = compare_throughput(
        corpus, iterations=args.iterations, repeats=args.repeats,
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
