"""Benchmarks must be reversible and compare like-for-like samples."""
import json
import unittest

from benchmarks.run import compare_corpus


class FakeToon:
    @staticmethod
    def dumps(value):
        return "fake:" + json.dumps(value, sort_keys=True)

    @staticmethod
    def loads(value):
        return json.loads(value[5:])


class BrokenToon:
    @staticmethod
    def dumps(value):
        return "not-reversible"

    @staticmethod
    def loads(value):
        return {"unexpected": True}


class TestBenchmark(unittest.TestCase):
    def test_baseline_has_no_invented_token_counts(self):
        report = compare_corpus([{"task": 42}, {"status": "ok"}])
        self.assertEqual(report["sample_count"], 2)
        self.assertIsNone(report["nexo_payload_tokens_total"])
        self.assertIsNone(report["toon_bytes_total_supported_only"])
        self.assertGreater(report["nexo_binary_bytes_total"], 0)

    def test_tokenizer_compares_full_envelope(self):
        report = compare_corpus([{"task": 42}], tokenizer=list, nexo_setup_tokens=4)
        row = report["results"][0]
        self.assertIsNotNone(row["envelope"])
        self.assertEqual(
            row["envelope"]["nexo_effective_tokens"],
            row["envelope"]["nexo_envelope_tokens"] + 4,
        )

    def test_toon_is_independently_roundtrip_verified(self):
        report = compare_corpus([{"task": 42}], tokenizer=list, toon=FakeToon)
        self.assertEqual(report["toon_supported"], 1)
        self.assertTrue(report["results"][0]["toon"]["supported"])
        self.assertIsInstance(report["toon_envelope_tokens_total_supported_only"], int)

    def test_invalid_toon_does_not_count_as_savings(self):
        report = compare_corpus([{"task": 42}], toon=BrokenToon)
        self.assertEqual(report["toon_supported"], 0)
        self.assertFalse(report["results"][0]["toon"]["supported"])
        self.assertEqual(report["toon_bytes_total_supported_only"], 0)
        self.assertIsNone(report["toon_envelope_tokens_total_supported_only"])

    def test_invalid_extra_instruction_tokens_rejected(self):
        with self.assertRaises(ValueError):
            compare_corpus([{"task": 42}], nexo_setup_tokens=-1)
