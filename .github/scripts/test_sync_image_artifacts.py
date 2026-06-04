#!/usr/bin/env python3
"""Regression tests for .github/scripts/sync_image_artifacts.py.

Run directly: `python3 .github/scripts/test_sync_image_artifacts.py`. No pytest
dependency: the script's CI step already installs PyYAML and nothing else, so
this module sticks to the standard library + the modules the script imports.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_image_artifacts import update_zarf  # noqa: E402

# Mirrors the parity-check regex in .github/workflows/lint.yaml's
# `Verify image-tag parity ...` step. The script's output MUST match this
# (single optional `@sha256:<64 hex>`) for every rewritten image line.
VALIDATOR = re.compile(
    r"^\s+-\s+([A-Za-z0-9_.\-/]+):([A-Za-z0-9_.\-]+)(?:@sha256:[a-f0-9]{64})?\s*$"
)

DIGEST_A = "a6149234667efc71d37766d61c1a16f24c33e4cd7a0bf4125c44a7e47e2419c4"
DIGEST_B = "6181d17d152967488408b4ced7b2930cc91c2b39adb7af6fb339965afce3404e"


def _image_lines(text: str) -> list[str]:
    """All lines that look like a Zarf component `images:` entry — `- repo:tag`
    with no whitespace between the colon and the tag (so `- name: ai-stack`
    style mapping entries are excluded)."""
    return [
        line
        for line in text.splitlines()
        if re.match(r"^\s+-\s+[A-Za-z0-9_.\-/]+:[A-Za-z0-9_.\-]", line)
    ]


class UpdateZarfRegression(unittest.TestCase):
    def test_replaces_existing_digest_with_new_one(self) -> None:
        """A line with digest A must end up with digest B — never both."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [
            {"repository": "ollama/ollama", "tag": "0.24.0", "digest": f"sha256:{DIGEST_B}"}
        ]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 1, f"doubled digest in: {out!r}")
        self.assertIn(DIGEST_B, out)
        self.assertNotIn(DIGEST_A, out)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_fixes_previously_doubled_digest_line(self) -> None:
        """A line already carrying two @sha256 suffixes (the reported bug
        output) must be normalised back to a single digest."""
        doubled = (
            f"      - ghcr.io/astral-sh/uv:python3.13-trixie-slim"
            f"@sha256:{DIGEST_A}@sha256:{DIGEST_A}\n"
        )
        images = [
            {
                "repository": "ghcr.io/astral-sh/uv",
                "tag": "python3.13-trixie-slim",
                "digest": f"sha256:{DIGEST_B}",
            }
        ]
        out = update_zarf(doubled, images)
        self.assertEqual(out.count("@sha256:"), 1, f"still doubled: {out!r}")
        self.assertIn(DIGEST_B, out)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_adds_digest_when_line_had_none(self) -> None:
        """A digest-less line picks up exactly one @sha256:<hex>."""
        text = "      - ollama/ollama:0.24.0\n"
        images = [
            {"repository": "ollama/ollama", "tag": "0.24.0", "digest": f"sha256:{DIGEST_A}"}
        ]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 1)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_strips_digest_when_values_has_no_digest(self) -> None:
        """If values.yaml has no digest, the rewritten line must not retain
        the stale one — and the validator (which allows zero or one digest)
        must still accept it."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [{"repository": "ollama/ollama", "tag": "0.24.0", "digest": ""}]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 0)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_idempotent_when_already_synced(self) -> None:
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [
            {"repository": "ollama/ollama", "tag": "0.24.0", "digest": f"sha256:{DIGEST_A}"}
        ]
        self.assertEqual(update_zarf(text, images), text)

    def test_preserves_comments_and_unmatched_lines(self) -> None:
        text = (
            "components:\n"
            "  - name: ai-stack\n"
            "    images:\n"
            "      # Ollama\n"
            f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
            "      # Standalone other image we do not manage\n"
            "      - other/image:1.2.3\n"
        )
        images = [
            {"repository": "ollama/ollama", "tag": "0.25.0", "digest": f"sha256:{DIGEST_B}"}
        ]
        out = update_zarf(text, images)
        self.assertIn("# Ollama", out)
        self.assertIn("# Standalone other image we do not manage", out)
        self.assertIn("      - other/image:1.2.3\n", out)
        for line in _image_lines(out):
            self.assertRegex(line, VALIDATOR)



    def test_strips_digest_carried_in_values_tag(self) -> None:
        """collect_values_images yields a tag WITH the digest attached (e.g.
        0.24.0@sha256:...); the rewrite must strip it, not re-append, so the
        line never doubles. This is the real-world case the earlier fix missed."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}"
        images = [
            {
                "repository": "ollama/ollama",
                "tag": f"0.24.0@sha256:{DIGEST_A}",
                "digest": f"sha256:{DIGEST_A}",
            }
        ]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 1, f"doubled digest in: {out!r}")
        self.assertRegex(out, VALIDATOR)
        self.assertEqual(out.strip(), f"- ollama/ollama:0.24.0@sha256:{DIGEST_A}")
if __name__ == "__main__":
    unittest.main()
