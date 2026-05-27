# ADR-002 — Image Digest Pinning Policy

- **Status:** Accepted
- **Date:** 2026-05-27
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.2.0 (unreleased; post-PR #108)
- **Supersedes:** none

---

## Context

Image references in `values.yaml` use tag-only pinning (e.g.
`qdrant/qdrant:v1.18.1`). Tags are mutable in most container registries: a
tag like `v1.18.1` can be re-pushed by the upstream maintainer to point at a
different manifest, or returned by a registry mirror with a stale cache.
This makes the deployed image identity non-deterministic relative to the
chart manifest.

ADR-001 §Future-work and several upstream best practices (SLSA Source
Track L2+, CIS Software Supply Chain Security 1.6.5, NIST SP 800-161 SI-5)
recommend pinning images by manifest digest in addition to tag.

The chart already supports this pattern for one image, `openTerminal`,
where `values.yaml` has both `tag:` and `digest:` fields and the template
uses a conditional (`@digest` if set, else `:tag`). This ADR extends the
pattern to all 14 chart images.

## Threat model addressed

- **Mutable-tag substitution.** Upstream maintainer (or a registry
  compromise) re-publishes a tag with malicious content. Tag-only pinning
  pulls the new manifest on next image pull; digest-pinning rejects it.
- **Registry-mirror staleness.** A cache returns an older manifest than
  intended. Lower severity, but digest-pinning makes the discrepancy
  observable.
- **Audit-trail strengthening.** Each release's deployed image identity
  becomes verifiable post-hoc by comparing the digest to the SBOM and to
  the registry.

Threats out of scope:

- Compromise of the SHA-256 hashing primitive.
- Compromise of the chart repository itself. Tracked separately via the
  Sigstore build-provenance attestations already produced by the release
  workflow.

## Decision

1. **Every chart-deployed image carries both `tag:` and `digest:` in
   `values.yaml`.** `digest:` is the SHA-256 manifest digest
   (`sha256:...`) of the multi-arch manifest list (or single-arch manifest
   where multi-arch is not published). `digest:` is the primary pin;
   `tag:` remains as a human-readable label and as a fallback when
   `digest:` is empty.

2. **Templates resolve image refs via the conditional pattern**: render
   `repo@digest` if `digest` is non-empty, otherwise `repo:tag`. This is
   the same pattern already used by `openTerminal` and is applied
   uniformly to all 13 other component templates by this PR.

3. **Renovate manages `tag` and `digest` together.** The `helm-values`
   manager has `"pinDigests": true` so digest updates flow alongside tag
   updates. The existing `matchUpdateTypes: [minor, patch, pin, digest]`
   rule already permits digest as an update type.

4. **Downstream artifacts (SBOM, Zarf, license-compliance matrix) carry
   the digest alongside the version string**, per ADR-001 §Decision[1].
   - SBOM: CycloneDX `hashes` array with `{alg: "SHA-256", content: <hex>}`
     per component.
   - Zarf: `repo:tag@sha256:...` syntax in `images:` lists.
   - License matrix: a digest column joins the existing per-image rows.

5. **Drift discipline from ADR-001 §Decision[1] applies.** When Renovate
   (or any maintainer) updates a digest, SBOM, Zarf, and docs must move
   with it. The CI parity step landed in PR #108 (commit `a70a022`)
   already enforces tag parity across the three files; extending it to
   compare digests as well is recorded as a follow-up.

## Initial digest values

Captured 2026-05-27 via registry-native HTTP HEAD against each image's
public manifest endpoint (anonymous tokens; multi-arch manifest list
where the index `mediaType` was `application/vnd.oci.image.index.v1+json`
or `application/vnd.docker.distribution.manifest.list.v2+json`, otherwise
single-arch manifest digest).

| Component | Image | Tag | Digest (SHA-256) |
|-----------|-------|-----|------------------|
| Open WebUI | `ghcr.io/open-webui/open-webui` | `v0.9.5` | `sha256:e045bde3b004cc7f8c319412345eb56c87ea6ac57031534a31ca37ad5424beb3` |
| Ollama | `ollama/ollama` | `0.24.0` | `sha256:a6149234667efc71d37766d61c1a16f24c33e4cd7a0bf4125c44a7e47e2419c4` |
| Qdrant | `qdrant/qdrant` | `v1.18.1` | `sha256:45f8e3ddc2570a4d029877e1b5ec1045c19b3852b4e22a55c7f43b05aea0ca89` |
| Tika | `apache/tika` | `3.3.0.0` | `sha256:2a565f1ea1290bdcb74a7d35957d16a989ed44ef98790dcdcc28121d728fa583` |
| SearXNG | `searxng/searxng` | `2026.5.26-0037d43d8` | `sha256:1a9d21346437a41ddfc2286968026dddece1d4d0721625cffa2c3b00bb2f9cf3` |
| Valkey | `valkey/valkey` | `9.1.0` | `sha256:4963247afc4cd33c7d3b2d2816b9f7f8eeebab148d29056c2ca4d7cbc966f2d9` |
| OTel Collector | `otel/opentelemetry-collector-contrib` | `0.153.0` | `sha256:93aad750175cbf1a973ae1c5886c3371f4d800f61be25cdd26870b8441ffe9fa` |
| LangGraph Server | `docker.io/langchain/langgraph-server` | `0.8-py3.12` | `sha256:8fe3a982cd378c7ff82f623f557ee0abd4d322ddaba1e7e3317ce895c6735613` |
| PostgreSQL | `docker.io/library/postgres` | `18-alpine` | `sha256:96d56f7f57c6aacd1fcb908bc83b345ec5f83231ee486dd66a1baadce274db88` |
| PyTorch Notebook | `quay.io/jupyter/pytorch-notebook` | `cuda12-python-3.13` | `sha256:ad080f315dfc2e0730b8aec02330405a8fb90d42ccb1965a2bf3a4128e27dc78` |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | `0.11.34` | `sha256:5e040fe357ce4fbd3d5e59c40247dd32172fa10c51c22ded3a7843e739d06a0e` |
| MCPO | `ghcr.io/open-webui/mcpo` | `0.0.20` | _unresolved (see below)_ |
| Authelia | `ghcr.io/authelia/authelia` | `4.39.20` | `sha256:1b363e9279e742397966333f364e0876ae02bf5c876de73e83af6d48c57ff51b` |
| Python (ingestion worker) | `python` | `3.14-slim` | `sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97` |

### MCPO digest unresolved (out-of-scope finding)

While populating this ADR, the `ghcr.io/open-webui/mcpo` registry was
inspected. It does **not** publish a `0.0.20` tag. The available tags are
all of the form `git-<sha>`, plus `latest`, `dev`, and `main`. The
chart's existing reference `ghcr.io/open-webui/mcpo:0.0.20` is therefore
a stale pin that will produce `ImagePullBackOff` when `mcpo.enabled` is
set to `true`. The default `mcpo.enabled: false` has masked this.

This is out of scope for ADR-002. It is recorded here so the finding is
not lost, and should be addressed in a separate PR. Possible paths:

- (a) Pin to a `git-<sha>` tag with a known release correspondence.
- (b) Build the image locally from the upstream `open-webui/mcpo` source
  and publish to a private registry.
- (c) Document `mcpo.enabled: true` as requiring a user-supplied image
  override.

Until the mcpo tag is resolved, the chart's `mcpo.image.digest` remains
empty and the template falls back to the (broken) tag, preserving the
pre-existing behaviour rather than masking the bug.

## Consequences

**Positive**

- Deployed image identity is deterministic across rebuilds, registry
  caches, and air-gap mirrors.
- SLSA Source Track L2 evidence strengthens (verifiable image identity
  in the build-provenance attestation that the release workflow already
  produces).
- Tag-substitution attempts are detectable at image pull time (kubelet's
  container runtime fails the pull on digest mismatch).

**Negative / accepted trade-offs**

- More state to keep in sync per bump: every image bump now needs a
  digest refresh alongside the tag refresh. Renovate's `pinDigests: true`
  automates the bot side; ad-hoc maintainer bumps need explicit care.
- Multi-arch manifest digests change whenever any single-arch manifest
  changes, so even no-op rebuilds rotate the digest. This produces more
  Renovate PRs than tag-only pinning would.
- Initial population requires registry pulls, which Docker Hub
  anonymous-rate-limits. Mitigation: registry-native HTTP HEAD with
  per-registry anonymous tokens (used to populate this ADR; not bound by
  the Docker CLI's accumulated rate counter).

**Operational**

- Renovate configuration extended (`renovate.json5`): `pinDigests: true`
  added to the `helm-values` manager. Existing `matchUpdateTypes` rule
  already permits digest updates.
- CI parity step from PR #108 currently compares tag strings only.
  Extending it to compare digests is a follow-up; not blocking for this
  ADR.
- The `image-tag parity` CI step continues to function: it ignores the
  new `digest:` field and only compares the tag strings, which remain
  in lockstep across `values.yaml`, `sbom.cdx.json`, and `zarf.yaml`.

## Related artifacts

- `Chart.yaml` — chart `version: 2.2.0`, `appVersion: 2026.4`.
- `values.yaml` — image declarations with both `tag` and `digest`.
- `sbom.cdx.json` — CycloneDX 1.6 SBOM with per-component `hashes` array.
- `zarf.yaml` — air-gap package manifest with `repo:tag@sha256:...`
  digest references.
- `renovate.json5` — `pinDigests: true` on the `helm-values` manager.
- `docs/architecture/ADR-001-component-version-management.md` — atomic
  cross-artifact sync discipline (extended in spirit by this ADR).
- 13 component templates (everything except `openTerminal`, which
  already had the digest-conditional pattern).
