# Measured benchmarks: NEXO/1, JSON, and TOON

This document records **observations**, not guaranteed improvements.
NEXO has two distinct goals: reducing serialized transport bytes and reducing
LLM context tokens. The same representation need not achieve both.

## First tokenizer-based baseline: 15 October 2026

Reproducible synthetic messages from `benchmarks/corpus.json` (9 samples).
The GitHub Actions [validation run](https://github.com/edujbarrios/nexo/actions/runs/38715020814)
uses:

- Python benchmark: `python benchmarks/run.py --toon --model gpt-4o`
- Model tokenizer: `gpt-4o` via `tiktoken 0.14.0`
- TOON implementation: `toon-format 1.1.0`
- Protocol: NEXO/1, with no extra amortized setup tokens
- All 9 inputs were successfully round-tripped by TOON; JSON and NEXO
  reference encoders were also verified for reversibility.

### Observed totals

| Measure across 9 messages | Compact JSON | NEXO Text | NEXO Binary | TOON |
|---|---:|---:|---:|---:|
| Raw payload bytes | 3,043 | 1,928 | 1,420 | 1,895 |
| Tokenized payload | 862 | 1,231 | N/A | Not reported here |
| Tokenized serialized format/payload envelope | 1,014 | 1,330 | N/A | 756 |

**NEXO Text saved about 36.6% of payload bytes but used about 42.8% more
payload tokens than compact JSON in this sample.** With envelopes, NEXO Text
used about 31.2% more tokenizer tokens than JSON. TOON used fewer envelope
tokens than both for these messages. This is evidence *against* making a
universal NEXO text-token savings claim.

NEXO Binary reduced payload bytes by about 53.3% against compact JSON, but
binary bytes are not directly meaningful as LLM tokenizer input. The native
Rust representation is intended for transport; text remains a separate
optimization problem.

### Interpretation

- **Transport:** binary framing saves bytes for repeated structured fields.
- **Model context:** NEXO's short punctuation-heavy text grammar is currently
  less favorable to the tested tokenizer for this synthetic distribution.
- **Selection:** with a supplied tokenizer, `AgentChannel` measures the
  entire serialized envelope and selects compact JSON whenever NEXO is not
  strictly cheaper, including any explicitly passed setup-token overhead.
- **Alternatives:** TOON is an independent optional baseline, not a dependency
  or runtime transport format automatically negotiated by NEXO/1.

### Limitations and next experiments

This corpus is synthetic and small. It is **not** a real conversation, a
representative production dataset, or an estimate of provider bills. The local
tokenizer does not include hidden provider framing, repeated prompt
instructions, tool schemas, model responses, context caching, or image-token
billing. The benchmark does not measure network transfer latency or image
reasoning. It does not establish that TOON is always superior.

Next, collect appropriately authorized and anonymized agent traffic with
documented workload distributions, then test different model tokenizers,
instruction amortization and compression profiles. An improved NEXO text
grammar or schema dictionary would require a **new negotiated wire version**,
not a silent change to NEXO/1.

Reproduce:

```bash
python -m pip install -e ".[tokens]"
python -m pip install toon-format
python benchmarks/run.py --toon --model gpt-4o
python benchmarks/speed.py --iterations 1000 --repeats 5
```

The last command measures **local codec throughput**, not model token usage.
Future runs may differ if the tokenizer, TOON version or corpus changes.
