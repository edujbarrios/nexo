"""Capability handshake preserves safe JSON fallback."""
import unittest
from nexo import AgentChannel, advertise_capabilities, peer_supports_nexo


class TestNegotiation(unittest.TestCase):
    def test_explicit_handshake(self):
        offer = advertise_capabilities()
        channel = AgentChannel.from_peer_capabilities(offer)
        message = {"type": "request", "task": 7}
        self.assertEqual(channel.send(message)["format"], "nexo/1")
        self.assertEqual(channel.receive(channel.send(message)), message)

    def test_disable(self):
        offer = advertise_capabilities(allow_nexo=False)
        self.assertFalse(peer_supports_nexo(offer))
        self.assertEqual(AgentChannel.from_peer_capabilities(offer).send({})["format"], "json")

    def test_malformed_or_unknown_version(self):
        invalid = (
            None, {},
            {"protocol": "other/1", "formats": ["json", "nexo/1"]},
            {"protocol": "nexo-capabilities/1", "formats": "json,nexo/1",
             "max_frame_bytes": 8388608},
            {"protocol": "nexo-capabilities/1", "formats": ["json", "nexo/1"],
             "max_frame_bytes": 1024},
            {"protocol": "nexo-capabilities/1", "formats": ["json", 1],
             "max_frame_bytes": 8388608},
        )
        for offer in invalid:
            with self.subTest(offer=offer):
                self.assertFalse(peer_supports_nexo(offer))
                self.assertEqual(
                    AgentChannel.from_peer_capabilities(offer).send({})["format"], "json",
                )

    def test_boolean_only(self):
        with self.assertRaises(TypeError):
            advertise_capabilities(allow_nexo=1)
