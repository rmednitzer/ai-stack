#!/usr/bin/env python3
"""Regression tests for .github/scripts/sync_image_artifacts.py.

Run directly: `python3 .github/scripts/test_sync_image_artifacts.py`. No pytest
dependency: the script's CI step already installs PyYAML and nothing else, so
this module sticks to the standard library + the modules the script imports.

The tag is the single source of truth: values.yaml carries `tag` as the full
string (version, optionally `@sha256:<hex>`), and there is NO separate
`digest:` field. Fixtures here mirror that model.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_image_artifacts import collect_values_images, update_zarf  # noqa: E402

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


class CollectValuesImages(unittest.TestCase):
    def test_parses_digest_from_tag(self) -> None:
        """A tag with @sha256:<hex> yields digest="sha256:<hex>" and the full
        tag string is preserved verbatim."""
        doc = {
            "ollama": {
                "image": {
                    "repository": "ollama/ollama",
                    "tag": f"0.30.4@sha256:{DIGEST_A}",
                }
            }
        }
        images = collect_values_images(doc)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["repository"], "ollama/ollama")
        self.assertEqual(images[0]["tag"], f"0.30.4@sha256:{DIGEST_A}")
        self.assertEqual(images[0]["digest"], f"sha256:{DIGEST_A}")

    def test_unpinned_tag_has_empty_digest(self) -> None:
        """A tag without @sha256 yields an empty digest, and the tag is kept
        as-is."""
        doc = {
            "x": {
                "image": {
                    "repository": "library/foo",
                    "tag": "1.2.3",
                }
            }
        }
        images = collect_values_images(doc)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["tag"], "1.2.3")
        self.assertEqual(images[0]["digest"], "")

    def test_no_separate_digest_field_is_read(self) -> None:
        """Any stray `digest:` key in values.yaml is ignored — the tag is
        authoritative. This is the regression the refactor introduces: the
        old code drifted because a separate digest field existed; the new
        code derives digest solely from the tag."""
        doc = {
            "x": {
                "image": {
                    "repository": "ollama/ollama",
                    "tag": f"0.30.4@sha256:{DIGEST_A}",
                    # Pretend a stale digest field is still present.
                    "digest": f"sha256:{DIGEST_B}",
                }
            }
        }
        images = collect_values_images(doc)
        self.assertEqual(images[0]["digest"], f"sha256:{DIGEST_A}")


class UpdateZarfRegression(unittest.TestCase):
    def test_replaces_existing_digest_with_new_one(self) -> None:
        """A line with digest A must end up with digest B — never both. The
        new digest comes from the tag string, not a separate field."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [
            {
                "repository": "ollama/ollama",
                "tag": f"0.24.0@sha256:{DIGEST_B}",
                "digest": f"sha256:{DIGEST_B}",
            }
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
                "tag": f"python3.13-trixie-slim@sha256:{DIGEST_B}",
                "digest": f"sha256:{DIGEST_B}",
            }
        ]
        out = update_zarf(doubled, images)
        self.assertEqual(out.count("@sha256:"), 1, f"still doubled: {out!r}")
        self.assertIn(DIGEST_B, out)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_adds_digest_when_line_had_none(self) -> None:
        """A digest-less line picks up exactly one @sha256:<hex> when the
        values.yaml tag is digest-pinned."""
        text = "      - ollama/ollama:0.24.0\n"
        images = [
            {
                "repository": "ollama/ollama",
                "tag": f"0.24.0@sha256:{DIGEST_A}",
                "digest": f"sha256:{DIGEST_A}",
            }
        ]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 1)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_strips_digest_when_values_tag_is_unpinned(self) -> None:
        """If the values.yaml tag has no @sha256:, the rewritten line must
        not retain the stale digest — the validator (which allows zero or one
        digest) must still accept it."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [{"repository": "ollama/ollama", "tag": "0.24.0", "digest": ""}]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 0)
        self.assertRegex(out.rstrip("\n"), VALIDATOR)

    def test_idempotent_when_already_synced(self) -> None:
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}\n"
        images = [
            {
                "repository": "ollama/ollama",
                "tag": f"0.24.0@sha256:{DIGEST_A}",
                "digest": f"sha256:{DIGEST_A}",
            }
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
            {
                "repository": "ollama/ollama",
                "tag": f"0.25.0@sha256:{DIGEST_B}",
                "digest": f"sha256:{DIGEST_B}",
            }
        ]
        out = update_zarf(text, images)
        self.assertIn("# Ollama", out)
        self.assertIn("# Standalone other image we do not manage", out)
        self.assertIn("      - other/image:1.2.3\n", out)
        for line in _image_lines(out):
            self.assertRegex(line, VALIDATOR)

    def test_writes_single_digest_from_tag(self) -> None:
        """End-to-end: the tag string carries the digest, the zarf line gets
        exactly one @sha256:<hex>, no doubling."""
        text = f"      - ollama/ollama:0.24.0@sha256:{DIGEST_A}"
        images = [
            {
                "repository": "ollama/ollama",
                "tag": f"0.25.0@sha256:{DIGEST_B}",
                "digest": f"sha256:{DIGEST_B}",
            }
        ]
        out = update_zarf(text, images)
        self.assertEqual(out.count("@sha256:"), 1, f"doubled digest in: {out!r}")
        self.assertRegex(out, VALIDATOR)
        self.assertEqual(out.strip(), f"- ollama/ollama:0.25.0@sha256:{DIGEST_B}")


if __name__ == "__main__":
    unittest.main()
