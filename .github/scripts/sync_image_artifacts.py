#!/usr/bin/env python3
"""
Sync sbom.cdx.json and zarf.yaml to the image references in values.yaml.

values.yaml is the single source of truth for image refs (ADR-001). This
script reads every {repository, tag, digest} mapping in values.yaml and
rewrites the matching component in sbom.cdx.json (version, purl, SHA-256
hash) and the matching entry in zarf.yaml (repo:tag@sha256:<hex>), so the
sbom-validate parity job in CI is satisfied without manual edits.

Component identity is basename(repository): ghcr.io/open-webui/open-webui
matches the SBOM component whose `name` (or, failing that, `bom-ref`) is
`open-webui`, exactly as the existing sbom-validate parity check does.

Modes:
    default  rewrites artifacts in place when they drift; idempotent.
    --check  exits non-zero on drift without writing.

Always preserved untouched:
    - metadata.component.version in the SBOM (chart-artifact version,
      governed by the Chart.yaml bump checklist, AGENTS.md §6).
    - Curated SBOM fields: description, licenses, properties,
      externalReferences, bom-ref, type, name, dependencies.
    - Comments and structure of zarf.yaml (line-level replacement, not a
      YAML round-trip).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VALUES = REPO_ROOT / "values.yaml"
SBOM = REPO_ROOT / "sbom.cdx.json"
ZARF = REPO_ROOT / "zarf.yaml"

DIGEST_PREFIX = "sha256:"
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")


def basename(repo: str) -> str:
    return repo.rsplit("/", 1)[-1] if "/" in repo else repo


def collect_values_images(node: Any, out: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    """Walk values.yaml for every {repository, tag} mapping (digest optional)."""
    if out is None:
        out = []
    if isinstance(node, dict):
        repo = node.get("repository")
        tag = node.get("tag")
        if isinstance(repo, str) and isinstance(tag, (str, int, float)):
            out.append({
                "repository": repo,
                "tag": str(tag),
                "digest": str(node.get("digest", "") or ""),
            })
        for v in node.values():
            collect_values_images(v, out)
    elif isinstance(node, list):
        for it in node:
            collect_values_images(it, out)
    return out


def digest_hex(digest: str) -> str:
    """Return the hex portion of a sha256:<hex> digest, or '' if absent."""
    if not digest:
        return ""
    if digest.startswith(DIGEST_PREFIX):
        return digest[len(DIGEST_PREFIX):]
    return digest


def rewrite_purl(purl: str, new_tag: str) -> str:
    """Replace the version after '@' in a pkg:docker purl, preserving path and query."""
    m = re.match(r"^(pkg:docker/[^@?]+)@([^?]+)(\?.*)?$", purl)
    if not m:
        return purl
    return f"{m.group(1)}@{new_tag}{m.group(3) or ''}"


def update_sbom(bom: dict[str, Any], images: list[dict[str, str]]) -> tuple[dict[str, Any], list[str]]:
    """Return a new SBOM with components rewritten to match values.yaml; collect issues."""
    issues: list[str] = []
    by_name: dict[str, int] = {}
    by_ref: dict[str, int] = {}
    for i, c in enumerate(bom.get("components", [])):
        if isinstance(c.get("name"), str):
            by_name.setdefault(c["name"], i)
        if isinstance(c.get("bom-ref"), str):
            by_ref.setdefault(c["bom-ref"], i)

    components = bom["components"]
    for img in images:
        identity = basename(img["repository"])
        idx = by_name.get(identity, by_ref.get(identity))
        if idx is None:
            issues.append(
                f"values.yaml image {img['repository']!r} (identity {identity!r}) "
                f"has no matching SBOM component (by name or bom-ref)"
            )
            continue

        comp = components[idx]
        comp["version"] = img["tag"]
        if isinstance(comp.get("purl"), str):
            comp["purl"] = rewrite_purl(comp["purl"], img["tag"])

        hex_ = digest_hex(img["digest"])
        if hex_:
            if not SHA256_HEX.match(hex_):
                issues.append(
                    f"values.yaml image {img['repository']!r} digest {img['digest']!r} "
                    f"is not a 64-hex sha256"
                )
            hashes = comp.get("hashes")
            if not isinstance(hashes, list):
                hashes = []
                comp["hashes"] = hashes
            replaced = False
            for h in hashes:
                if isinstance(h, dict) and h.get("alg") == "SHA-256":
                    h["content"] = hex_
                    replaced = True
                    break
            if not replaced:
                hashes.append({"alg": "SHA-256", "content": hex_})
        else:
            # values.yaml has no digest pin: leave any existing SBOM hash alone.
            pass

    return bom, issues


def update_zarf(text: str, images: list[dict[str, str]]) -> str:
    """Rewrite every `- <repo>:<tag>[@sha256:<hex>]` line for repos in values.yaml.

    Line-level editing, not YAML round-trip: zarf.yaml carries `# Component`
    comments and a yaml-language-server schema pragma we must not lose.
    """
    lines = text.splitlines(keepends=True)
    # Pre-build per-repo replacements.
    by_repo: dict[str, dict[str, str]] = {img["repository"]: img for img in images}
    # Match: leading whitespace, "- ", repository, ":", a tag (no @, no whitespace),
    # optional @sha256:<hex>, optional trailing whitespace.
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        # Keep trailing newline separate so we can reattach.
        nl = line[len(stripped):]
        m = re.match(
            r"^(?P<lead>\s+-\s+)(?P<repo>[A-Za-z0-9_.\-/]+):(?P<tag>[^@\s]+)(?P<digest>@sha256:[a-f0-9]{64})?(?P<trail>\s*)$",
            stripped,
        )
        if not m:
            continue
        repo = m.group("repo")
        img = by_repo.get(repo)
        if img is None:
            continue
        tag = img["tag"]
        hex_ = digest_hex(img["digest"])
        if hex_:
            new_ref = f"{repo}:{tag}@sha256:{hex_}"
        else:
            new_ref = f"{repo}:{tag}"
        new_line = f"{m.group('lead')}{new_ref}{m.group('trail')}{nl}"
        lines[i] = new_line
    return "".join(lines)


def write_if_changed(path: Path, new_text: str, dry_run: bool) -> bool:
    """Write file when content differs; return True if a write would happen."""
    old_text = path.read_text(encoding="utf-8")
    if new_text == old_text:
        return False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero on drift without writing.",
    )
    args = ap.parse_args(argv)

    with VALUES.open(encoding="utf-8") as f:
        values_doc = yaml.safe_load(f)
    images = collect_values_images(values_doc)
    if not images:
        print("::error::No image blocks found in values.yaml — refusing to wipe artifacts.", file=sys.stderr)
        return 2

    sbom_old_text = SBOM.read_text(encoding="utf-8")
    bom = json.loads(sbom_old_text)
    bom, issues = update_sbom(bom, images)
    for msg in issues:
        print(f"::error::{msg}", file=sys.stderr)
    if issues:
        return 2
    sbom_new_text = json.dumps(bom, indent=2, ensure_ascii=False) + "\n"

    zarf_old_text = ZARF.read_text(encoding="utf-8")
    zarf_new_text = update_zarf(zarf_old_text, images)

    sbom_changed = sbom_new_text != sbom_old_text
    zarf_changed = zarf_new_text != zarf_old_text

    if not (sbom_changed or zarf_changed):
        print(f"in sync: {len(images)} image(s) already consistent across values.yaml, sbom.cdx.json, zarf.yaml")
        return 0

    if args.check:
        if sbom_changed:
            print("::error::sbom.cdx.json is out of sync with values.yaml. Run .github/scripts/sync_image_artifacts.py.", file=sys.stderr)
        if zarf_changed:
            print("::error::zarf.yaml is out of sync with values.yaml. Run .github/scripts/sync_image_artifacts.py.", file=sys.stderr)
        return 1

    if sbom_changed:
        write_if_changed(SBOM, sbom_new_text, dry_run=False)
        print(f"updated: {SBOM.relative_to(REPO_ROOT)}")
    if zarf_changed:
        write_if_changed(ZARF, zarf_new_text, dry_run=False)
        print(f"updated: {ZARF.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
