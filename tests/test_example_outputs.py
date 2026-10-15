"""Keep README runnable-example stdout descriptions grounded in real scripts."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestExampleStdout(unittest.TestCase):
    def test_documented_example_outputs(self):
        examples = {
            "agent_pair.py": (
                "Transport: {'format': 'nexo/1'",
                "Decoded: {'status': 'ok', 'task': 42, 'type': 'result'}",
            ),
            "attachments.py": (
                "'type': 'image'",
                "'size': 19",
            ),
            "handshake.py": ("Negotiated: nexo/1 Decoded:",),
            "plain_text.py": (
                "text : NX1:50:Hello, agent B. This is plain text, not JSON. 🤖",
                "Channel round-trip: nexo/1",
            ),
            "image_transfer.py": ("Image transferred over a socket: sha256:",),
            "socket_session.py": ("Transport: NXF/1; image: sha256:",),
            "stream_image_file.py": ("Streamed and SHA-256 verified:",),
            "nexo64_images.py": ("Custom binary-to-text frame prefix: NX64/1",),
            "replay_guard.py": (),
        }
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for filename, expected_lines in examples.items():
            with self.subTest(filename=filename):
                self.assertIn(filename, readme)
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "examples" / filename)],
                    cwd=ROOT, capture_output=True, text=True, timeout=12,
                    check=True,
                )
                output = completed.stdout
                for fragment in expected_lines:
                    self.assertIn(fragment, output)
                if filename == "replay_guard.py":
                    self.assertTrue(
                        "Repeated encrypted message: rejected" in output
                        or "Install nexo[crypto]" in output
                    )
