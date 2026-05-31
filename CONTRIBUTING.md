# Contributing to ai-stack

Thank you for considering contributing to the ai-stack Helm chart.

> **AI agents & automation:** see [`AGENTS.md`](AGENTS.md) for the operating
> spec and repo map, and [`CLAUDE.md`](CLAUDE.md) for the Claude-specific
> collaboration overlay. This file covers human contributor setup and the PR
> process; the conventions in all three are kept consistent.

## Project Overview

This is a **Helm chart** (`ai-stack`) for deploying a comprehensive AI inference
and tooling stack targeting EU-regulated on-premises and hybrid Kubernetes
environments. All source files are Helm templates (Go template + YAML), values
files, and CI workflows.

**Tech stack:** Helm 3 (apiVersion v2), Kubernetes 1.27+ (tested against 1.32), Go templates + Sprig,
GitHub Actions CI (helm lint, chart-testing, kubeconform, kube-linter, Syft SBOM,
Grype CVE scan, SBOM tag/digest parity, and `zarf dev lint`).

**Components:** Open WebUI, Ollama, Qdrant, Tika, SearXNG, Valkey,
Open Terminal, MCPO, LangGraph or Pydantic AI (agentic; with PostgreSQL), an
ingestion worker, optional Authelia OIDC, and an OpenTelemetry Collector. Each
lives under `templates/<component>/` (shared resources under `templates/common/`).

**Values profiles:** `lab` (default, single-node) and `prod` (`values-prod.yaml`).
Tiering: T0 = safety/integrity, T1 = operational, T2 = productivity.

## Development Setup

1. Install prerequisites:
   - [Helm](https://helm.sh/docs/intro/install/) 3.12+
   - [helm-docs](https://github.com/norwoodj/helm-docs) (optional, for README generation)
   - [chart-testing (ct)](https://github.com/helm/chart-testing) (optional, for CI-grade linting)
   - [kubeconform](https://github.com/yannh/kubeconform) (optional, for manifest validation)
   - [helm-unittest](https://github.com/helm-unittest/helm-unittest) (optional, for `make unittest`: `helm plugin install https://github.com/helm-unittest/helm-unittest`)
   - [kubectl](https://kubernetes.io/docs/tasks/tools/) with access to a test cluster

2. Clone the repository:

   ```bash
   git clone https://github.com/rmednitzer/ai-stack.git
   cd ai-stack
   ```

3. Lint your changes:

   ```bash
   helm lint .
   helm lint . -f values.yaml -f values-prod.yaml
   ```

Or use the convenience targets:

```bash
make lint
make lint-prod
```

4. Dry-run to verify rendering:

   ```bash
   helm template ai-stack . --debug
   ```


You can also render with make targets:

```bash
make template
make template-prod
```

5. Validate rendered manifests against Kubernetes schemas:

   ```bash
   helm template ai-stack . | kubeconform -strict -summary -skip CustomResourceDefinition,ServiceMonitor
   helm template ai-stack . -f values.yaml -f values-prod.yaml | kubeconform -strict -summary -skip CustomResourceDefinition,ServiceMonitor
   ```

6. Run chart-testing for full CI-equivalent linting:

   ```bash
   ct lint --config ct.yaml --charts .
   ```

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes, ensuring:
   - `helm lint .` passes with no errors or warnings.
   - `helm template ai-stack . --debug` renders without errors.
   - All new values are documented in `values.yaml` with `# --` comment annotations.
   - Security contexts follow the PSA restricted baseline (non-root, read-only FS where possible, drop all capabilities).
   - NetworkPolicy rules are added for any new component.
   - Any image change is synced to `sbom.cdx.json`, `zarf.yaml`, and the license/ADR-002 tables in the **same** commit (see "Supply-chain sync discipline" below).
3. Update `Chart.yaml` version following [SemVer](https://semver.org/):
   - **PATCH** (`1.0.x`): Bug fixes, security updates, documentation improvements, image tag bumps
   - **MINOR** (`1.x.0`): Backward-compatible additions (new optional component, new configurable value)
   - **MAJOR** (`x.0.0`): Breaking changes (renamed values, dropped Kubernetes version support, removed component)
4. Open a pull request using the PR template, with a clear description of the change and testing steps performed.

## Guidelines

- **Security first**: Every new component must have a dedicated ServiceAccount, NetworkPolicy rules, and appropriate securityContext.
- **Conditional deployment**: All components must be gated behind an `enabled` flag.
- **Consistent naming**: Use `ai-stack.componentName` helper for all resource names.
- **Governance labels**: Apply `assurance.platform/tier` and `assurance.platform/boundary` annotations to all new deployments.
- **No hardcoded secrets**: Use auto-generated secrets or external secret store references.

## Supply-chain sync discipline (ADR-001 / ADR-002)

`values.yaml` is the single source of truth for image references. When you change
any image `repository`/`tag`/`digest`, update the downstream artifacts in the
**same PR** so they stay in lockstep:

- `sbom.cdx.json` — component `version`, `purl`, and `hashes[].content` (the digest, hex without the `sha256:` prefix)
- `zarf.yaml` — the `repo:tag@sha256:...` image entry
- `docs/compliance/LICENSE_COMPLIANCE.md` and `docs/architecture/ADR-002-image-digest-pinning.md` — the image tables
- the version-bearing doc headers (README badges, compliance/enterprise/governance docs) when `Chart.yaml` `version` changes

Renovate (`renovate.json5`) bumps `values.yaml` tags **and** digests together; the
maintainer still syncs the downstream artifacts. CI enforces it via the
`sbom-validate` job (component count + tag/digest parity across the three files).

## CI gates

Every PR runs [`.github/workflows/lint.yaml`](.github/workflows/lint.yaml):

| Gate | Checks |
|------|--------|
| `helm-lint` / `chart-testing` | `helm lint` + `helm template` (lab & prod), `ct lint` |
| `helm-unittest` | template unit tests asserting security invariants (`tests/`, run `make unittest`) |
| `kubeconform` | rendered manifests vs Kubernetes JSON schemas |
| `kube-linter` | policy lint of rendered manifests (config: `.kube-linter.yaml`) |
| `sbom-validate` | CycloneDX 1.6 schema + tag/digest parity (values ↔ sbom ↔ zarf) |
| `zarf-lint` | `zarf dev lint` of `zarf.yaml` |
| `syft-sbom` / `cve-scan` | deep per-image SBOMs + CVE scan (on merge to `main`) |

Run the fast ones locally before pushing where practical: `helm lint`,
`kubeconform`, `kube-linter`, and `zarf dev lint`.
