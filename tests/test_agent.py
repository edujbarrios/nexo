import unittest
from nexo import AGENT_INSTRUCTIONS, CodecError, parse_peer_message, prepare_peer_message


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

    def test_instruction(self):
        self.assertIn("Do not ask an LLM", AGENT_INSTRUCTIONS)
