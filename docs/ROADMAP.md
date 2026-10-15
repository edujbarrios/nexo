# Roadmap

NEXO remains experimental; items below are not promises or release claims.

## Implemented source

- NEXO/1 text and binary serializers in Rust and Python.
- Explicit version headers, deterministic dictionaries and bounded parsers.
- Python agent facade with capability negotiation and optional token-cost
  strategy; function-tool schemas; local SHA-256 attachment adapter.
- Optional PyO3 adapter source code and independently installable SDK.
- Persistent local on-disk attachment storage with SHA-256 verification.
- Shared cross-language binary/text conformance fixture.
- Explicit JSON capability handshake and safe fallback in the agent SDK.

## Next validation milestones

1. Green Rust and Python CI with cross-language golden vectors. A dedicated
   cross-language randomized parity job is now included, pending CI validation.
2. Python/Rust behavioral and numerical parity tests for complex values,
   including exact Python `bytes` returns from PyO3 bindings.
3. ✅ Build a separate native wheel in CI and add an opt-in local throughput
   benchmark against stdlib JSON and the Python NEXO reference codec.
   Deployment performance and real-world benefits remain unverified.
4. ✅ Initial optional JSON/NEXO/TOON benchmark harness, including
   round-trip verification, envelope measurements and negative results.
5. Collect **real** anonymized agent communication corpora (only with
   permission); rerun model-specific tokenizers and publish results.
6. Include actual orchestration instructions, provider/tool framing and
   runtime billing in end-to-end token cost claims.
7. ✅ Add shared adversarial wire fixtures, strict varint decoding and
   seeded byte-mutation tests. Next: libFuzzer/cargo-fuzz coverage and a
   secure remote blob-store adapter.
8. Consider version-negotiated custom schema dictionaries if results justify.

## Non-goals for v1

Opaque model-internal tokens, guaranteed savings for arbitrary messages,
compressing image token billing, or teaching every LLM a new grammar.
