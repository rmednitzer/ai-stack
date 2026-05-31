#!/usr/bin/env python3
"""Offline markdown link + anchor checker for the ai-stack docs.

Validates every relative link in every tracked ``*.md`` file:

* the target file exists, and
* any ``#fragment`` resolves to a heading in the target file, using GitHub's
  heading-slug algorithm (lowercase; drop characters that are not
  alphanumeric, space or hyphen; replace each remaining space with a hyphen —
  note this preserves the double hyphens GitHub produces around removed
  punctuation such as ``—``/``/``/``+``).

External links (http/https/mailto/tel) are intentionally not fetched, so the
check is deterministic and network-free. Exits non-zero (and prints every
offender) when a relative link or anchor is broken.

Usage:  python3 .github/scripts/check_md_links.py [root]
"""
from __future__ import annotations

import re
import sys
import pathlib

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.M)
EXTERNAL = ("http://", "https://", "mailto:", "tel:")


def slug(heading: str) -> str:
    """Reproduce GitHub's heading -> anchor slug."""
    kept = "".join(c for c in heading.strip().lower() if c.isalnum() or c in " -")
    return kept.strip().replace(" ", "-")


def heading_slugs(text: str) -> set[str]:
    """All anchor slugs GitHub generates for a file's headings.

    GitHub disambiguates repeated headings by appending ``-1``, ``-2`, … to the
    second and later occurrences of an identical slug (the first stays bare), so
    e.g. three ``### Changed`` headings yield ``changed``, ``changed-1``,
    ``changed-2``. We reproduce that so links to a later duplicate section are
    not falsely flagged as broken.
    """
    seen: dict[str, int] = {}
    out: set[str] = set()
    for m in HEADING_RE.finditer(text):
        base = slug(m.group(1))
        n = seen.get(base, 0)
        out.add(base if n == 0 else f"{base}-{n}")
        seen[base] = n + 1
    return out


def main(root: str = ".") -> int:
    base = pathlib.Path(root)
    mds = [p for p in base.rglob("*.md") if ".git" not in p.parts]
    headings: dict[pathlib.Path, set[str]] = {}
    for p in mds:
        text = p.read_text(encoding="utf-8", errors="replace")
        headings[p.resolve()] = heading_slugs(text)

    broken: list[tuple[str, str, str]] = []
    for p in mds:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(EXTERNAL):
                continue
            path, _, anchor = target.partition("#")
            anchor = anchor.lower()
            if path == "":  # same-file anchor
                if anchor and anchor not in headings[p.resolve()]:
                    broken.append((str(p), target, "anchor not found in this file"))
                continue
            resolved = (p.parent / path).resolve()
            if not resolved.exists():
                broken.append((str(p), target, "target file missing"))
            elif anchor and resolved in headings and anchor not in headings[resolved]:
                broken.append((str(p), target, "anchor not found in target"))

    if broken:
        print(f"::error::{len(broken)} broken markdown link(s) found:")
        for f, t, why in broken:
            print(f"  {f}: {t}  -> {why}")
        return 1
    print(f"OK: all relative links and #anchors resolve across {len(mds)} markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
