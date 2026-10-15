# NEXO software architecture

This is a **ports-and-adapters** design with small, explicit boundaries rather
than a complex object hierarchy. Keep dependencies pointing inwards.

```text
nexo/
├── crates/
│   ├── nexo-core/src/
│   │   ├── lib.rs             public Rust facade / contract tests
│   │   ├── text.rs            text grammar
│   │   ├── binary.rs          binary grammar
│   │   ├── reader.rs          bounds-checked parser
│   │   ├── constants.rs       immutable protocol dictionaries
│   │   └── error.rs           validation and resource limits
│   └── nexo-python/src/      optional PyO3 Rust-Python adapter
├── python/nexo/
│   ├── __init__.py            stable package facade
│   ├── codec.py               stable public codec facade
│   ├── _wire/                 internal reference codec submodules
│   ├── agent.py               capability and token-cost strategy
│   ├── native.py              optional accelerator adapter
│   ├── tools.py               framework-agnostic function tools
│   ├── attachments.py         shared manifest/integrity logic + memory store
│   ├── filesystem.py          persistent local blob adapter
│   └── __main__.py            CLI adapter
├── bindings/                  separate optional maturin build
├── tests/                     Python black-box and golden tests
├── examples/                  independent runnable examples
└── docs/                      reference documentation
```

## Patterns and responsibilities

**Facade:** `nexo.encode`, `decode` and `Codec` hide wire decisions.
**Strategy:** `prepare_peer_message` chooses compact JSON or NEXO according
to peer capability and the provided tokenizer's results. It does not pretend
that fewer bytes always means fewer model tokens.
**Adapter:** native, tool and blob integrations isolate external concerns.
**Dependency inversion:** tokenizers are injected callables, not hard-coded
model SDKs or imports. The core is deterministic, standalone and offline.
**Fail closed:** invalid headers, trailing bytes, dangerous recursion,
oversized frames and invalid types raise errors.

## Dependency rules

1. Wire encode/decode must not call an LLM, access the network or depend
   on any orchestration framework.
2. Optional integrations must not be required by basic `pip install`.
3. The agent-facing facade must not leak Rust-specific types.
4. Protocol changes must update Rust, Python and parity fixtures together.
5. Public releases require CI to pass on both language implementations.

This remains **experimental**: cross-language parity beyond the golden
fixtures, complete token-cost savings, and performance improvements are not
yet established.
