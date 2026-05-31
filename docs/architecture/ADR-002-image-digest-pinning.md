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
   already enforces tag parity across the three files; a companion
   digest-parity step now enforces digest lockstep as well (see
   Consequences → Operational).

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
| Tika | `apache/tika` | `3.3.1.0` | `sha256:90b7fa1dc018434075fce9e1d9b88b1e3d0ea6979d0cf86e116c79a8073ae973` |
| SearXNG | `searxng/searxng` | `2026.5.31-300695de5` | `sha256:75e85884da87a717655d6313421c8fb42aede84219b06873311179ae830ab396` |
| Valkey | `valkey/valkey` | `9.1.0` | `sha256:4963247afc4cd33c7d3b2d2816b9f7f8eeebab148d29056c2ca4d7cbc966f2d9` |
| OTel Collector | `otel/opentelemetry-collector-contrib` | `0.153.0` | `sha256:93aad750175cbf1a973ae1c5886c3371f4d800f61be25cdd26870b8441ffe9fa` |
| LangGraph Server | `docker.io/langchain/langgraph-server` | `0.9-py3.12` | `sha256:916a50e069663b244e56370691db97d04d8aa1c0add2057653f924f51724a2ce` |
| PostgreSQL | `docker.io/library/postgres` | `18-alpine` | `sha256:96d56f7f57c6aacd1fcb908bc83b345ec5f83231ee486dd66a1baadce274db88` |
| PyTorch Notebook | `quay.io/jupyter/pytorch-notebook` | `cuda12-python-3.13` | `sha256:ad080f315dfc2e0730b8aec02330405a8fb90d42ccb1965a2bf3a4128e27dc78` |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | `0.11.34` | `sha256:5e040fe357ce4fbd3d5e59c40247dd32172fa10c51c22ded3a7843e739d06a0e` |
| MCPO | `ghcr.io/open-webui/mcpo` | `main` | `sha256:1e82c9555c19e50b80745705f32b47a2647589f35279527b5118ecd3a71bd467` |
| Authelia | `ghcr.io/authelia/authelia` | `4.39.20` | `sha256:1b363e9279e742397966333f364e0876ae02bf5c876de73e83af6d48c57ff51b` |
| Python (ingestion worker) | `python` | `3.14-slim` | `sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97` |
| Pydantic AI (uv base) | `ghcr.io/astral-sh/uv` | `python3.13-trixie-slim` | `sha256:6181d17d152967488408b4ced7b2930cc91c2b39adb7af6fb339965afce3404e` |

> This table is kept in lockstep with `values.yaml` per ADR-001 and CI digest
> parity. Rows added or updated since the 2026-05-27 acceptance snapshot include
> the Pydantic AI `uv` base image (added in v2.4.0, 2026-05-31) and the
> Tika/SearXNG/LangGraph/MCPO bumps — the chart now pins **15** images.

### MCPO digest resolved (2026-05-31, post-acceptance)

The `0.0.20` reference originally recorded here never existed upstream:
`ghcr.io/open-webui/mcpo` publishes no semver container tags, only
per-commit `git-<sha>` tags plus `latest`/`dev`/`main` (where `latest`
and `main` resolve to one identical manifest). The stale pin produced
`ImagePullBackOff` whenever `mcpo.enabled: true`; the default
`mcpo.enabled: false` masked it.

Resolution (a follow-up PR adapting option (a) above): the chart now
tracks the `main` channel pinned by **immutable digest** —

```
ghcr.io/open-webui/mcpo:main@sha256:1e82c9555c19e50b80745705f32b47a2647589f35279527b5118ecd3a71bd467
```

The digest makes pulls deterministic regardless of tag mutation, and
Renovate's `pinDigests` refreshes it as `main` advances. The MCPO row in
the table above now carries this digest, and `values.yaml`, `sbom.cdx.json`,
and `zarf.yaml` were updated in lockstep — so **all chart images are
digest-pinned with no exceptions**, which in turn lets the CI parity step
enforce digest parity (see Consequences → Operational).

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
- CI parity step from PR #108 originally compared tag strings only. A
  digest-parity step has since been added to `lint.yaml`: it extracts the
  `image.digest` from `values.yaml`, the `hashes[].content` from
  `sbom.cdx.json`, and the `@sha256:` suffix from `zarf.yaml`, and fails on
  any per-component mismatch or missing digest. This became enforceable once
  MCPO was digest-pinned (see "MCPO digest resolved" above), so there are no
  allow-listed exceptions.
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
