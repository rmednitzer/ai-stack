#!/usr/bin/env python3
"""
Sync sbom.cdx.json and zarf.yaml to the image references in values.yaml.

values.yaml is the single source of truth for image refs (ADR-001). The image
tag is the single source of truth for both version and digest — when Renovate
pin-digests an image, it appends @sha256:<hex> to the tag string, so
`tag: "0.30.4@sha256:..."` carries both. There is no separate `digest:` field
to drift out of sync.

This script reads every {repository, tag} mapping in values.yaml, parses the
optional @sha256:<hex> suffix from the tag, and rewrites the matching
component in sbom.cdx.json (version, purl, SHA-256 hash) and the matching
entry in zarf.yaml (repo:tag — the tag already carries the digest when pinned).

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
    """Walk values.yaml for every {repository, tag} mapping.

    The tag is the single source of truth: when Renovate pin-digests an image
    it appends @sha256:<hex> to the tag (e.g. `0.30.4@sha256:7a3f...`). We
    return the FULL tag string verbatim and a derived `digest` parsed from the
    @sha256:<hex> suffix (or `""` when the tag is not digest-pinned).
    """
    if out is None:
        out = []
    if isinstance(node, dict):
        repo = node.get("repository")
        tag = node.get("tag")
        if isinstance(repo, str) and isinstance(tag, (str, int, float)):
            tag_s = str(tag)
            if "@" in tag_s:
                _, suffix = tag_s.split("@", 1)
                digest = suffix if suffix.startswith(DIGEST_PREFIX) else ""
            else:
                digest = ""
            out.append({
                "repository": repo,
                "tag": tag_s,
                "digest": digest,
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


def rewrite_purl(purl: str, new_tag: str, new_digest_hex: str) -> str:
    """Rewrite a pkg:docker purl to the spec form for the new tag/digest.

    The purl spec allows exactly ONE '@' separator (name@version); the digest
    belongs in the `checksum` qualifier, not appended as a second '@'. So a
    values.yaml tag `0.30.4@sha256:<hex>` becomes
    `pkg:docker/<name>@0.30.4?checksum=sha256:<hex>`. Pre-existing qualifiers
    (e.g. repository_url) are preserved; qualifiers are emitted sorted by key
    per the purl canonical form. Also normalises the legacy double-'@' purls
    this repo carried before 2.12.0 (anything after the first '@' up to '?' is
    treated as the old version and replaced wholesale).
    """
    m = re.match(r"^(pkg:docker/[^@?]+)@([^?]+)(?:\?(.*))?$", purl)
    if not m:
        return purl
    quals: dict[str, str] = {}
    for part in (m.group(3) or "").split("&"):
        if part:
            k, _, v = part.partition("=")
            quals[k] = v
    if new_digest_hex:
        quals["checksum"] = f"{DIGEST_PREFIX}{new_digest_hex}"
    else:
        quals.pop("checksum", None)
    version = new_tag.split("@", 1)[0]
    qstr = "&".join(f"{k}={quals[k]}" for k in sorted(quals))
    return f"{m.group(1)}@{version}" + (f"?{qstr}" if qstr else "")


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
            comp["purl"] = rewrite_purl(comp["purl"], img["tag"], digest_hex(img["digest"]))

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


_ZARF_IMAGE_LINE = re.compile(
    # Leading whitespace, "- ", repository, ":", a tag (no @, no whitespace),
    # then ANY remaining "@"-prefixed suffix (well-formed digest, malformed
    # digest, or a previously-doubled "@sha256:...@sha256:..." from an earlier
    # buggy sync) is captured into `rest` and discarded — the rewrite always
    # emits at most one "@sha256:<hex>" so the sbom-validate parity regex
    # (which permits a single optional digest) keeps matching.
    r"^(?P<lead>\s+-\s+)(?P<repo>[A-Za-z0-9_.\-/]+):(?P<tag>[^@\s]+)(?P<rest>@\S*)?(?P<trail>\s*)$"
)


def update_zarf(text: str, images: list[dict[str, str]]) -> str:
    """Rewrite every `- <repo>:<tag>[@sha256:<hex>]` line for repos in values.yaml.

    Line-level editing, not YAML round-trip: zarf.yaml carries `# Component`
    comments and a yaml-language-server schema pragma we must not lose. The
    values.yaml tag already carries the @sha256:<hex> suffix when pinned, so
    we emit `repo:{tag}` directly — no separate digest field, no
    split-and-re-append. Any existing "@..." suffix on a matched line is
    dropped before the tag is written, so re-runs cannot accumulate digests.
    """
    lines = text.splitlines(keepends=True)
    by_repo: dict[str, dict[str, str]] = {img["repository"]: img for img in images}
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        # Keep trailing newline separate so we can reattach.
        nl = line[len(stripped):]
        m = _ZARF_IMAGE_LINE.match(stripped)
        if not m:
            continue
        repo = m.group("repo")
        img = by_repo.get(repo)
        if img is None:
            continue
        new_ref = f"{repo}:{img['tag']}"
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
