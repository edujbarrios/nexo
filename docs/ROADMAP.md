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
- Plain-text NEXO/1 string API, CLI and explicitly non-encrypted opaque display.
- NXI/1 image/file transmission with chunking, SHA-256 validation and explicit
  capability negotiation, plus socket and text-only transport examples.
- NXF/1 bounded socket framing and TLS-verified client with combined agent
  text/message/image session (host authorization and server deployment external).
- Directional capability checks for send and receive, malformed-frame and
  duplicate-key rejection tests on local sockets.
- Streaming file-source / disk-sink NXI/1 adapters to avoid loading the
  entire image into RAM; atomic publication after SHA-256 verification.
- NEXO64/1 custom 64-symbol image-to-text alphabet with strict canonical
  decoding, bounded frames, CRC32, and existing NXI/1 compatibility.
- Optional NXE64/1 authenticated AES-256-GCM image-frame encryption,
  randomized nonces, key/associated-data checks, and downgrade refusal.
- Optional bounded per-process `ReplayGuard` for authenticated NXE64 messages,
  with fail-closed limits and cross-transfer reuse; no distributed guarantee.
- README explains NEXO's purpose and tradeoffs and records CI-verified
  outputs of the runnable examples.

## Next validation milestones

1. ✅ Rust and Python CI with shared golden vectors and a randomized
   cross-language parity job; regression builds still run on every PR.
2. ✅ Frozen Python/Rust behavioral and numerical parity tests, including
   exact `bytes` returns from the PyO3 binary interface; expand coverage
   as the protocol evolves.
3. ✅ Build a separate native wheel in CI and add an opt-in local throughput
   benchmark against stdlib JSON and the Python NEXO reference codec.
   Deployment performance and real-world benefits remain unverified.
4. ✅ Initial optional JSON/NEXO/TOON benchmark harness, including
   round-trip verification, envelope measurements and negative results.
5. ✅ Capture a reproducible tokenizer-specific baseline on the 9-message
   synthetic corpus in [benchmark results](BENCHMARKS.md). NEXO/1 Text
   currently loses tokenizer tokens against compact JSON in this test.
6. Collect **real** anonymized agent communication corpora (only with
   permission); rerun model-specific tokenizers and publish results.
7. Include actual orchestration instructions, provider/tool framing and
   runtime billing in end-to-end token cost claims.
8. ✅ Add shared adversarial wire fixtures, strict varint decoding and
   seeded byte-mutation tests. Added NXI/1 malformed/duplicate/truncated
   media-packet coverage. Next: libFuzzer/cargo-fuzz coverage and a
   server-side authenticated transport integration and resumable transfers
   (streaming-to-disk memory bounds are now supported).
9. ✅ Add opt-in, bounded local replay detection for decrypted NXE64 messages
   and chunked transfers. Still needed: **durable/distributed** replay-state
   persistence, authenticated key provisioning, rotation, peer authorization,
   and an independent security review before production deployment.
10. Study a tokenizer-oriented NEXO/2 text grammar or custom schema
   dictionaries **only** if independent measurements justify a version bump.

## Non-goals for v1

Opaque model-internal tokens, guaranteed savings for arbitrary messages,
compressing image token billing, or teaching every LLM a new grammar.

## Packaging and distribution milestones

- [x] Prepare named pure-Python distribution `nexo-agent-protocol` without
  changing the import path, maintaining the custom restrictive license.
- [x] Build wheel and sdist in CI, validate with Twine, test clean
  installation, and confirm the sdist builds a working wheel.
- [x] Automatically build and publish **new, unpublished** versions to
  PyPI when SDK/package changes merge to `main`, with version-specific
  registry checks, fail-closed network behavior and OIDC.
- [x] Keep an optional manual PyPI/TestPyPI workflow for explicit retries
  and dry runs, with no GitHub Release or tag requirement.
- [x] Add live PyPI/Python badge URLs to README; they update automatically
  after publication without a bot commit.
- [ ] Verify maintainer-controlled PyPI/TestPyPI Trusted Publishers and
  GitHub environment approvals for publishing from branch `main`.
- [ ] Publish the initial `0.1.0` wheel/sdist and verify it on PyPI;
  document any outstanding OIDC/environment authorization failure.
- [ ] Separately validate cross-platform native wheels for `nexo-native`,
  including distribution ownership, before automating its publication.
