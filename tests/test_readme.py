"""Keep the README's English introduction clear and byte counts reproducible."""
from pathlib import Path

from nexo import decode, encode, encode_binary

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_explains_encoding_before_installation():
    text = README.read_text(encoding="utf-8")
    assert text.index("## What is NEXO?") < text.index("## Installation")
    assert "Encoding is not encryption." in text
    assert "Byte savings are not LLM token savings" in text
    assert "docs/PROTOCOL.md" in text


def test_readme_uses_english_prose():
    text = README.read_text(encoding="utf-8")
    for old_spanish_text in (
        "¿Qué es NEXO",
        "Cuando dos agentes",
        "Representación del ejemplo",
        "¿Qué significan",
        "Importante: bytes",
    ):
        assert old_spanish_text not in text


def test_intro_example_exact_lengths():
    message = {"status": "ok", "task": 42, "type": "result"}
    text = encode(message)
    binary = encode_binary(message)
    assert text == "NX1{3:.2;!1;.1;#42;.0;!0;"
    assert len(text.encode("utf-8")) == 25
    assert len(binary) == 17
    assert decode(text) == decode(binary) == message

def test_readme_explains_why_nexo_exists_and_reports_actual_outputs():
    text = README.read_text(encoding="utf-8")
    protocol = text.index("## What is NEXO?")
    library = text.index("## The Python library: designed for AI agents")
    motivation = text.index("## Why this repository exists")
    installation = text.index("## Installation")
    assert protocol < library < motivation < installation
    assert "built for applications that host AI agents" in text
    assert "https://img.shields.io/pypi/v/nexo-agent-protocol" in text
    assert "https://pypi.org/project/nexo-agent-protocol/" in text
    assert "python -m pip install nexo-agent-protocol" in text
    assert "### Where NEXO stands out" in text
    assert "NEXO Text consumed more tokens than JSON" in text
    assert "## Runnable examples and their outputs" in text
    assert "NX1{3:.2;!1;.1;#42;.0;!0;" in text
    assert "38731051914" in text
    assert "replay_guard.py" in text


def test_readme_agent_example_is_reversible():
    from nexo import AgentChannel, advertise_capabilities
    sender = AgentChannel.from_peer_capabilities(advertise_capabilities())
    receiver = AgentChannel.from_peer_capabilities(advertise_capabilities())
    data = {"type": "result", "task": 42, "status": "ok"}
    wire = sender.send(data)
    assert wire == {"format": "nexo/1", "payload": "NX1{3:.2;!1;.1;#42;.0;!0;"}
    assert receiver.receive(wire) == data
