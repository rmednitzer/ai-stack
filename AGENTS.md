# AGENTS.md

This repository is developed with AI assistance. This file is the operating
spec and repo map for any coding/ops agent (or human) working in `ai-stack`.
It is tool-agnostic; [`CLAUDE.md`](CLAUDE.md) adds a Claude-specific
collaboration overlay, and [`CONTRIBUTING.md`](CONTRIBUTING.md) covers human
contributor setup and the PR process.

## 1) Mission

`ai-stack` is a **single Helm chart** that deploys a governed AI inference and
tooling stack (Open WebUI, Ollama, Qdrant, Tika, SearXNG, Valkey, optional
MCPO, Open Terminal, LangGraph/Pydantic AI, PostgreSQL, Authelia, OTel) for
**EU-regulated on-premises / hybrid Kubernetes**. The design priorities are:

1. **Governance-as-code** — controls trace to template annotations and a
   regulatory basis (`docs/governance/CONTROLS.md`).
2. **Secure by default** — PSA `restricted`, default-deny NetworkPolicy,
   per-component identity, digest-pinned images.
3. **Supply-chain integrity** — `values.yaml` is the source of truth; the SBOM,
   Zarf package, and version-bearing docs stay in lockstep with it.
4. **Operational clarity** — honest `SECURITY.md` threat model and
   `LIMITATIONS.md`; everything renders and is unit-tested.

There is **no application source** here beyond the small payloads in `files/`
(e.g. the Pydantic AI reference app, ingestion worker). The deliverable is the
chart.

## 2) Non-negotiable operating principles

1. **`values.yaml` is the single source of truth** (ADR-001). When you change an
   image `tag`/`digest`, sync `sbom.cdx.json` **and** `zarf.yaml` in the **same
   PR** — CI enforces tag/digest parity across all three.
2. **Pin images by digest** (ADR-002); never use `:latest` or a floating tag
   without a `digest:`.
3. **Never hardcode secrets.** Use the `ai-stack.persistentSecret` helper or an
   `existingSecret` reference. Auto-generated keys must stay stable across
   `helm upgrade`.
4. **Preserve the security defaults.** Every workload keeps `runAsNonRoot`,
   `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`,
   `automountServiceAccountToken: false`, a dedicated ServiceAccount, and a
   default-deny NetworkPolicy with a least-privilege allowlist. Document any
   justified exception in `.kube-linter.yaml` with an annotation.
5. **Every component is opt-in/-out via `.Values.<component>.enabled`** and the
   chart must render with all optional components disabled.
6. **Governance metadata is mandatory** on every workload: the
   `assurance.platform/tier` (T0/T1/T2) and `assurance.platform/boundary`
   **labels**, plus the `assurance.platform/control-refs` **annotation** (an
   annotation, not a label — its value is a comma-separated list, which is not a
   valid label value). Each `tier`/`boundary` value and every `control-refs` id
   must exist in `docs/governance/CONTROLS.md`.
7. **Assert security claims as tests.** Any security-relevant template change
   gets a `helm-unittest` assertion in `tests/`.
8. **Version bumps are a documentation event.** See §6.

## 3) Repo / technical map

| Path | What it is |
|------|------------|
| `Chart.yaml` | Chart metadata; `version` (semver) + `appVersion`; governance annotations |
| `values.yaml` | Source of truth; fully `# --`-commented; ~1200 lines |
| `values-prod.yaml` | Production overlay (HA, autoscaling, CNPG, otel on) |
| `values.schema.json` | JSON Schema (top-level + per-component `enabled`; typo-catching, not exhaustive) |
| `templates/<component>/` | Per-component manifests (deployment, service, …) |
| `templates/common/` | Shared resources: `networkpolicies.yaml`, `serviceaccounts.yaml`, `secrets.yaml` |
| `templates/_helpers.tpl` | Named templates: `restrictedSecurityContext`, `persistentSecret`, `componentName`, `netpolEgress`, `otelEnv`, `openTerminalCorsOrigins`, ingress/httpRoute, postgres helpers |
| `templates/tests/connection-test.yaml` | `helm test` connectivity hook (runtime) |
| `tests/` | **helm-unittest** suites (template assertions); excluded from the packaged chart |
| `files/` | In-image payloads (Pydantic AI app, ingestion worker) |
| `docs/architecture/` | ADRs (`ADR-NNN-*.md`) + `REFERENCE.md` |
| `docs/governance/CONTROLS.md` | Authoritative CTL/POL registry → regulatory basis |
| `docs/compliance/` | DPIA/DSAR/ROPA/incident/EU-compliance docs |
| `docs/components/` | One doc per component |
| `SECURITY.md` | Threat model + reporting + control list |
| `LIMITATIONS.md` | Per-component scope boundaries (state / implication / tracking) |
| `zarf.yaml` | Air-gap package definition (versions mirror `Chart.yaml`) |
| `sbom.cdx.json` | CycloneDX SBOM (one component per image; digest-pinned) |
| `Makefile` | `lint`, `lint-prod`, `template`, `template-prod`, `unittest`, `test`, `check-links` |

## Component naming

Components follow one naming rule, so the values API stays stable as
implementations evolve:

- **Values key — camelCase, lowercase first letter** (Helm convention; hyphens
  break value paths). Name a component by its **generic role/category** when a
  recognised industry term exists (`aiGateway`, `externalAPIs`,
  `ingestionWorker`) so the implementation can change without a breaking rename;
  name it by the **upstream project** only when the component *is* that specific
  software (`ollama`, `qdrant`, `authelia`, `openwebui`).
- **Resource id — kebab-case** of the same term, used for `componentName`, the
  `templates/<id>/` directory, the `ai-stack.governanceMap` key, and the
  `app.kubernetes.io/name` selector (e.g. `ai-gateway`).
- The concrete implementation/image is documented in `docs/components/<id>.md`
  and `sbom.cdx.json` — **not** encoded in the values key. Example: the
  `aiGateway` component is implemented by Envoy AI Gateway (ADR-006); swapping
  the gateway would not change the chart's values surface.

## 4) Required change workflow

1. Read the impacted template(s), `values.yaml`, and `_helpers.tpl`.
2. Make minimal, surgical changes; reuse existing helpers.
3. Render and gate locally:
   ```
   helm lint . && helm lint . -f values.yaml -f values-prod.yaml
   helm template ai-stack . >/dev/null                       # lab
   helm template ai-stack . -f values.yaml -f values-prod.yaml >/dev/null
   helm unittest .                                            # tests/
   make check-links                                           # if docs changed
   ```
   (`kube-linter` and `kubeconform` also run in CI; run locally if available.)
4. Add/adjust `tests/` assertions for any security-relevant change.
5. Update `CHANGELOG.md` (Keep a Changelog + semver) and the relevant
   `docs/components/*` / `SECURITY.md` / `LIMITATIONS.md`.
6. If you bumped `Chart.yaml`, complete §6 before opening the PR.

## 5) CI gates (`.github/workflows/`)

- **lint.yaml** — `helm-lint`, `helm-unittest`, `chart-testing` (`ct lint`),
  `kubeconform`, `kube-linter`, `sbom-validate` (CycloneDX 1.6 schema +
  package-version parity with `Chart.yaml` + image tag/digest parity across
  `values.yaml` ↔ `sbom.cdx.json` ↔ `zarf.yaml`),
  `zarf-lint`; `syft-sbom` + `cve-scan` (Grype) on merge to `main`.
- **docs.yaml** — `markdown-links` (offline relative-link + `#anchor` checker).
- **release.yaml** — tag-gated OCI push + SLSA build provenance.
- CodeQL runs via repo **default setup** (Python in `files/`, Actions workflows).

A green PR means all of the above pass; the `sbom-validate` parity job is the
one most often tripped by an unsynced image change (see §2.1).

## 6) Version-bump checklist (ADR-001 discipline)

A `Chart.yaml` `version:` bump is **not done** until these are synced in the
same PR (parity is partly CI-enforced, partly not — do all of them):

- `CHANGELOG.md` — new dated section (Added/Changed/Fixed/Security).
- `README.md` — the Helm-chart version badge.
- `zarf.yaml` — `metadata.version`, every local-chart `version:` entry, and the
  deploy-filename comment (`zarf dev lint` only schema-checks, so it will **not**
  catch a stale version here).
- `sbom.cdx.json` — `metadata.component.version` (and `metadata.timestamp`); the
  `sbom-validate` CI job now fails if this drifts from `Chart.yaml` `version:`.
- Version-bearing docs: `docs/enterprise/ENTERPRISE_EVALUATION.md`,
  `docs/governance/CONTROLS.md` (footer), `docs/compliance/LICENSE_COMPLIANCE.md`,
  `docs/compliance/EU_COMPLIANCE_CHECK.md`.
- If image tags changed: `sbom.cdx.json` + `zarf.yaml` image entries + the
  `LICENSE_COMPLIANCE.md` image table.

ADR "Chart version at acceptance" lines are **historical** — never rewrite them.

## 7) When to write an ADR

Add `docs/architecture/ADR-NNN-<slug>.md` (record `Status`, `Date`, deciders,
`Chart version at acceptance`) for any cross-cutting decision: a new component,
a default-behavior change, an image-management/supply-chain change, a security
posture change, or a new exposure/auth pattern. Routine value tweaks and
additive opt-in flags do not need an ADR.

## 8) Security posture

PSA `restricted` + default-deny NetworkPolicy + per-component identity are the
baseline. The model-driven components (MCPO, Open Terminal) are the sharp edge:
treat model/RAG/web input as attacker-influenced (prompt injection → excessive
agency). See `SECURITY.md` (Threat model) and `LIMITATIONS.md`. Untrusted
code-execution wants a hardened `runtimeClassName` (gVisor/Kata); OTel redaction
must keep stripping PII **and** secret/token shapes before export.

## 9) Definition of done

1. `helm lint` (lab + prod), `helm template` (lab / prod / all-optional), and
   `helm unittest .` are green; `kube-linter` / `kubeconform` pass in CI.
2. `tests/` covers any new security-relevant behavior.
3. Version-bearing artifacts are synced (§6) when the chart version changed.
4. `CHANGELOG.md` and the affected docs reflect the change.
5. No security default or governance annotation was weakened unintentionally.

## 10) Trusted references

- Helm: <https://helm.sh/docs/> · Pod Security Standards:
  <https://kubernetes.io/docs/concepts/security/pod-security-standards/>
- NSA/CISA Kubernetes Hardening Guide
- OWASP LLM Top 10 (excessive agency): <https://genai.owasp.org/>
- Model Context Protocol: <https://modelcontextprotocol.io>
- Keep a Changelog: <https://keepachangelog.com/> · SemVer: <https://semver.org/>
