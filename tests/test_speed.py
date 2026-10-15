"""Local throughput benchmark contracts; do not assert performance thresholds."""
import unittest

from benchmarks.speed import compare_throughput


class TestThroughput(unittest.TestCase):
    def test_reference_codecs_and_json_roundtrip(self):
        report = compare_throughput(
            [{"status": "ok", "task": 42}, [1, None, "ñ🤖"]],
            iterations=2, repeats=2,
        )
        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["iterations"], 2)
        for name in ("stdlib-json-text", "python-nexo-text", "python-nexo-binary"):
            self.assertIn(name, report["results"])
            for operation in ("encode", "decode"):
                metric = report["results"][name][operation]
                self.assertEqual(metric["operations"], 4)
                self.assertGreaterEqual(metric["median_seconds"], 0)

    def test_bad_arguments(self):
        for kwargs in (
            {"messages": []},
            {"messages": [{}], "iterations": 0},
            {"messages": [{}], "repeats": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                compare_throughput(**kwargs)
