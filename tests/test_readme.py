"""Keep the NEXO wire explanation discoverable and truthful for new users."""
from pathlib import Path

from nexo import decode, encode, encode_binary

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_explains_encoding_before_installation():
    text = README.read_text(encoding="utf-8")
    assert text.index("## ¿Qué es NEXO y cómo funciona?") < text.index("## Installation")
    assert "not encryption" in text
    assert "bytes ≠ tokens" in text


def test_intro_example_exact_lengths():
    message = {"status": "ok", "task": 42, "type": "result"}
    text = encode(message)
    binary = encode_binary(message)
    assert text == "NX1{3:.2;!1;.1;#42;.0;!0;"
    assert len(text.encode("utf-8")) == 25
    assert len(binary) == 17
    assert decode(text) == decode(binary) == message
