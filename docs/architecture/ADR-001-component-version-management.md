# ADR-001 — Component Version Management and SBOM/Zarf Sync Discipline

- **Status:** Accepted
- **Date:** 2026-05-24
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.2.0 (`appVersion` 2026.4)
- **Supersedes:** none (first ADR for this repository)

---

## Context

The ai-stack chart pins every component image to an explicit tag across three
artifacts:

1. **`values.yaml`** — operational source of truth consumed by the rendered Helm
   templates.
2. **`sbom.cdx.json`** — CycloneDX 1.6 Software Bill of Materials, used for
   supply-chain attestation and the CI `sbom-validate` job.
3. **`zarf.yaml`** — air-gap package manifest listing the exact image references
   that the build job mirrors into the offline tarball.

These artifacts must agree. If they diverge, the deployed chart and the
attested SBOM/Zarf bundle describe different software, which breaks supply-chain
guarantees and downstream evidence (DPIA, ROPA, license-matrix, CycloneDX
attestations).

History shows this is a recurring failure mode:

- `CHANGELOG.md` v2.1.0 — _"Fixed MCPO image tag from 0.2.0 to 0.0.20", "Fixed
  SBOM Python ingestion-worker version from 3.13-slim to 3.12-slim", "Fixed SBOM
  Valkey version from 8.1 to 8.1.6 to match values.yaml pinned version"_.
- `CHANGELOG.md` v2.1.1 — _"Synced zarf.yaml Ollama image from 0.20.2 to 0.20.5
  to match values.yaml", "Synced SBOM and zarf.yaml PostgreSQL version from
  17-alpine to 18-alpine to match values.yaml"_.
- `CHANGELOG.md` v2.2.0 — _"SBOM drift fixed — sbom.cdx.json was lagging behind
  values.yaml for five components"_ and _"Zarf package drift fixed — zarf.yaml
  had the same five stale image references"_.

A 2026-05-24 codebase index found the same class of drift had reappeared
between v2.2.0 ship date (2026-04-29) and 2026-05-24.

## Audit findings (2026-05-24)

### 1. SBOM and Zarf drift against `values.yaml`

Both `sbom.cdx.json` and `zarf.yaml` were lagging `values.yaml` on the same five
components. All five are resynced in this commit.

| Component | values.yaml | sbom.cdx.json (was) | zarf.yaml (was) | Action |
|-----------|-------------|---------------------|-----------------|--------|
| Open WebUI | `v0.9.5` | `v0.9.2` | `v0.9.2` | SBOM + Zarf bumped to `v0.9.5` |
| Ollama | `0.24.0` | `0.23.1` | `0.23.1` | SBOM + Zarf bumped to `0.24.0` |
| Qdrant | `v1.18.0` | `v1.17.1` | `v1.17.1` | SBOM + Zarf bumped to `v1.18.0` |
| Valkey | `9.1.0` | `8.1.6` | `8.1.6` | SBOM + Zarf bumped to `9.1.0` |
| OTel Collector | `0.152.0` | `0.151.0` | `0.151.0` | SBOM + Zarf bumped to `0.152.0` |

The SBOM `metadata.timestamp` and `serialNumber` were refreshed to mark the
re-issue.

### 2. Documentation drift

Stale image and chart-version references were corrected in:

| File | Drift type | Fix |
|------|-----------|-----|
| `HOWTO.md` §1.3 air-gap example | `v0.8.10` / `0.18.2` / `0.18.0` | bumped to `v0.9.5` / `0.24.0` |
| `docs/compliance/LICENSE_COMPLIANCE.md` | 12 stale image versions and chart version `2.0.0` from 2026-03-26 | full table resynced; header updated to chart `2.2.0`, reviewed `2026-05-24` |
| `docs/compliance/EU_COMPLIANCE_CHECK.md` header | chart `2.0.0` / `appVersion 2026.1` | bumped to `2.2.0` / `2026.4`; date marked `2026-05-24 (re-validated)` |
| `docs/enterprise/ENTERPRISE_EVALUATION.md` header + body | chart `2.0.0` / `appVersion 2026.1` | bumped to `2.2.0` / `2026.4` |
| `docs/governance/CONTROLS.md` footer | registry version `2.0` | bumped to `2.2` to track `Chart.yaml` |
| `docs/components/tika.md` | upstream-docs URL pinned to `3.1.1` whilst image is `3.3.0.0` | updated URL to `3.3.0` |

### 3. Upstream validation (informational — no value bumped)

Each declared tag was verified against its upstream registry/release feed. All
declared tags exist; four are slightly behind the latest upstream patch:

| Component | Declared | Latest upstream | Lag | Notes |
|-----------|----------|-----------------|-----|-------|
| Open WebUI | `v0.9.5` | `v0.9.5` | none | released 2026-05-10 |
| Ollama | `0.24.0` | `0.24.0` | none | released 2026-05-14 |
| Qdrant | `v1.18.0` | `v1.18.1` | 1 patch | upstream patch on 2026-05-22 |
| Apache Tika | `3.3.0.0` | `3.3.0.0` | none | 4-segment versioning is current for 3.x |
| SearXNG | `2026.4.11-9e08a6771` | `2026.5.23-323ce7600` | ~6 weeks | continuously released; downstream consumers usually pin |
| Valkey | `9.1.0` | `9.1.0` | none | released 2026-05-19 |
| Authelia | `4.39` (floating) | `v4.39.19` exact | n/a | floating `4.39` alias resolves to current 4.39.x patch |
| Jupyter PyTorch Notebook | `cuda12-python-3.13` | same | none | multi-arch manifest current |
| Open Terminal | `0.11.34` | `0.11.34` | none | released 2026-04-08 |
| MCPO | `0.0.20` | `0.0.20` | none | released 2026-02-27 |
| LangGraph Server | `0.8-py3.12` (floating) | `0.8.7-py3.12` | n/a | floating alias for latest 0.8.x |
| PostgreSQL | `18-alpine` | `18-alpine` (PG 18.4) | none | 18 is current stable |
| CloudNativePG Postgres | `16` | `16` LTS-supported | informational | PG 16 still LTS; consider 17/18 in a future PR |
| Python (ingestion worker) | `3.14-slim` | `3.14-slim` (3.14.5) | none | current |
| OTel Collector | `0.152.0` | `0.152.1` | 1 patch | upstream patch on 2026-05-20 |

The four patch-behind tags (`qdrant v1.18.1`, `searxng 2026.5.23-323ce7600`,
`otel-collector 0.152.1`, exact `authelia v4.39.19` pinning) are **not** bumped
in this commit; tracking them separately keeps drift correction and upstream
chasing on different cadences.

## Decision

1. **`values.yaml` remains the single source of truth** for image references.
   `sbom.cdx.json` and `zarf.yaml` are downstream artifacts that **must** be
   regenerated/edited in the same PR that changes `values.yaml`. CI already
   enforces the SBOM side via `sbom-validate`; the Zarf side is checked at
   release time.

2. **Documentation that names an image version is treated as code, not prose.**
   Specifically: `LICENSE_COMPLIANCE.md`, `EU_COMPLIANCE_CHECK.md`,
   `ENTERPRISE_EVALUATION.md`, and the air-gap example in `HOWTO.md §1.3` must
   be refreshed whenever a tag in `values.yaml` changes. Component pages under
   `docs/components/` intentionally avoid hardcoding tags ("see `values.yaml`
   for pinned tag") and remain the preferred pattern for new docs.

3. **Upstream-patch lag is acknowledged but not auto-applied.** Image-tag
   updates are bot-driven but split across two managers:
   [`renovate.json5`](../../renovate.json5) (`enabledManagers: ["helm-values"]`)
   bumps `values.yaml` and `values-prod.yaml`;
   [`.github/dependabot.yml`](../../.github/dependabot.yml) handles
   `github-actions` and `docker` (Dockerfile / docker-compose) ecosystems
   only. **Neither bot updates `sbom.cdx.json` or `zarf.yaml`** — these
   downstream artifacts are the source of the recurring drift documented in
   the Context above. Audit-mode lag is recorded in this ADR rather than
   acted upon automatically so that downstream syncs remain explicit,
   reviewable changes.

4. **Future ADRs** are numbered sequentially in `docs/architecture/` and use the
   `ADR-NNN-short-slug.md` filename pattern. This file is the template.

## Consequences

**Positive**

- `sbom.cdx.json`, `zarf.yaml`, and the four version-bearing markdown files now
  match the operational `values.yaml`.
- The repeated drift pattern is now described in a single canonical place and
  is reviewable as a unit of evidence (supply-chain attestation, license
  compliance, EU evidence pack).
- The chart's documented upstream-validation procedure can be re-run on demand
  by following the table in §3.

**Negative / accepted trade-offs**

- Manual sync remains a possible failure mode — and the **primary** failure
  mode, because Renovate's `helm-values` manager bumps `values.yaml` on its
  own schedule but does not touch the downstream artifacts. Mitigation: the
  SBOM CI job already checks component count; the natural follow-up is to
  extend `sbom-validate` (and add a `zarf-validate` step) to compare each
  component's `version` / image-tag string against the corresponding
  `values.yaml` field, failing the build on drift. That extension is out of
  scope for this ADR — file a follow-up if the next audit finds drift again.
  - **Status update (2026-05-27):** The next audit (this branch) found drift
    again: PR #107 bumped `values.yaml` to `qdrant v1.18.1` while leaving
    `sbom.cdx.json` and `zarf.yaml` at `v1.18.0`. The follow-up CI
    enforcement is now implemented as a new step
    "Verify image-tag parity across values.yaml, sbom.cdx.json, zarf.yaml"
    inside the `sbom-validate` job of `.github/workflows/lint.yaml`. It
    validates per-component version equality across all three files,
    detects basename collisions, missing components, and internal
    SBOM purl-vs-version desync. The Zarf side is covered by the same
    step rather than a separate job, since the comparison runs purely on
    repo files (no Docker pulls).
- Patch-level lag (currently four components) is documented but not closed.
  Mitigation: a future PR can bump these once tested against the chart's
  smoke-test suite (`helm test`) and the kubeconform / chart-testing CI jobs.

## Related artifacts

- [`Chart.yaml`](../../Chart.yaml) — chart `version: 2.2.0`, `appVersion: 2026.4`
- [`values.yaml`](../../values.yaml) — image tag declarations (source of truth)
- [`sbom.cdx.json`](../../sbom.cdx.json) — CycloneDX 1.6 SBOM
- [`zarf.yaml`](../../zarf.yaml) — air-gap package manifest
- [`docs/compliance/LICENSE_COMPLIANCE.md`](../compliance/LICENSE_COMPLIANCE.md) — license matrix
- [`docs/architecture/REFERENCE.md`](REFERENCE.md) — reference architecture
- [`CHANGELOG.md`](../../CHANGELOG.md) — release history (drift fixes in 2.1.0, 2.1.1, 2.2.0)
