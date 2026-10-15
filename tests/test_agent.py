import unittest
import json
from nexo import (
    AGENT_INSTRUCTIONS, AgentChannel, CodecError, compare_peer_formats,
    parse_peer_message, prepare_peer_message,
)


class TestAgent(unittest.TestCase):
    def test_fallback_for_unaware_peer(self):
        data = {"type": "result", "task": 42}
        envelope = prepare_peer_message(data)
        self.assertEqual(envelope["format"], "json")
        self.assertEqual(parse_peer_message(envelope), data)

    def test_capable_peer(self):
        data = {"type": "result", "task": 42}
        envelope = prepare_peer_message(data, peer_supports_nexo=True)
        self.assertEqual(envelope["format"], "nexo/1")
        self.assertEqual(parse_peer_message(envelope), data)

    def test_tokenizer_strategy(self):
        envelope = prepare_peer_message(
            {"x": 1}, peer_supports_nexo=True, tokenizer=list,
        )
        self.assertEqual(envelope["format"], "json")

    def test_invalid_envelopes(self):
        for item in (None, {}, {"format": "wrong", "payload": "ok"},
                     {"format": "json", "payload": "NaN"},
                     {"format": "json", "payload": "[1"}):
            with self.subTest(item=item), self.assertRaises(CodecError):
                parse_peer_message(item)

    def test_channel_facade(self):
        channel = AgentChannel(peer_supports_nexo=True)
        original = {"type": "result", "status": "ok"}
        self.assertEqual(channel.receive(channel.send(original)), original)
        self.assertEqual(AgentChannel().send(original)["format"], "json")
        with self.assertRaises(ValueError):
            channel.explain(original)

    def test_full_envelope_measured_not_payload(self):
        msg = {"status": "ok"}
        report = compare_peer_formats(msg, tokenizer=list)
        plain = json.dumps(msg, sort_keys=True, separators=(",", ":"))
        nexo_frame = prepare_peer_message(msg, peer_supports_nexo=True)
        json_frame = {"format": "json", "payload": plain}
        serialized_nexo = json.dumps(nexo_frame, sort_keys=True, separators=(",", ":"))
        serialized_json = json.dumps(json_frame, sort_keys=True, separators=(",", ":"))
        self.assertEqual(report["json_envelope_tokens"], len(serialized_json))
        self.assertEqual(report["nexo_envelope_tokens"], len(serialized_nexo))
        self.assertEqual(report["tokens_saved"], len(serialized_json)-len(serialized_nexo))
        if report["preferred_format"] == "json":
            self.assertEqual(
                prepare_peer_message(msg, peer_supports_nexo=True, tokenizer=list)["format"],
                "json",
            )

    def test_setup_cost_amortization(self):
        msg = {"type": "result", "task": 42}
        report = compare_peer_formats(msg, tokenizer=list, nexo_setup_tokens=1000)
        self.assertEqual(report["preferred_format"], "json")
        channel = AgentChannel(
            peer_supports_nexo=True, tokenizer=list, nexo_setup_tokens=1000,
        )
        self.assertEqual(channel.send(msg)["format"], "json")
        self.assertEqual(channel.explain(msg), report)

    def test_reject_negative_setup_tokens(self):
        with self.assertRaises(ValueError):
            compare_peer_formats({"x": 1}, list, nexo_setup_tokens=-1)
        with self.assertRaises(ValueError):
            prepare_peer_message({"x": 1}, nexo_setup_tokens=-1)

    def test_json_only_integer_fallback(self):
        message = {"task": 2**70}
        frame = prepare_peer_message(
            message, peer_supports_nexo=True, tokenizer=list,
        )
        self.assertEqual(frame["format"], "json")
        self.assertEqual(parse_peer_message(frame), message)

    def test_instruction(self):
        self.assertIn("Do not ask an LLM", AGENT_INSTRUCTIONS)
