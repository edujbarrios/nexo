# Roadmap

NEXO remains experimental; items below are not promises or release claims.

## Implemented source

- NEXO/1 text and binary serializers in Rust and Python.
- Explicit version headers, deterministic dictionaries and bounded parsers.
- Python agent facade with capability negotiation and optional token-cost
  strategy; function-tool schemas; local SHA-256 attachment adapter.
- Optional PyO3 adapter source code and independently installable SDK.

## Next validation milestones

1. Green Rust and Python CI with cross-language golden vectors.
2. Python/Rust behavioral and numerical parity tests for complex values.
3. Build an optional native wheel and benchmark the speed against stdlib.
4. Compare NEXO, compact JSON, TOON and alternatives on **real** agent
   message corpora with model-specific tokenizers.
5. Include actual orchestration instructions, transport envelope and tool
   call overhead in all end-to-end token cost claims.
6. Add fuzzer, randomized conformance tests, hostile input limits and a
   shared authenticated blob-store interface.
7. Consider version-negotiated custom schema dictionaries if results justify.

## Non-goals for v1

Opaque model-internal tokens, guaranteed savings for arbitrary messages,
compressing image token billing, or teaching every LLM a new grammar.
