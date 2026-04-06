# Contributing to ai-stack

Thank you for considering contributing to the ai-stack Helm chart.

## Project Overview

This is a **Helm chart** (`ai-stack`) for deploying a comprehensive AI inference
and tooling stack targeting EU-regulated on-premises and hybrid Kubernetes
environments. All source files are Helm templates (Go template + YAML), values
files, and CI workflows.

**Tech stack:** Helm 3 (apiVersion v2), Kubernetes 1.27+ (tested against 1.32), Go templates + Sprig,
GitHub Actions CI (lint, chart-testing, kubeconform, Syft SBOM, Grype CVE scan).

**Components:** Open WebUI, Ollama, Qdrant, Tika, SearXNG, Workbench, Valkey,
Open Terminal, MCPO, LangGraph (with PostgreSQL), ingestion worker,
and optional Authelia OIDC. Each lives under `templates/<component>/`.

**Values profiles:** `lab` (default, single-node) and `prod` (`values-prod.yaml`).
Tiering: T0 = safety/integrity, T1 = operational, T2 = productivity.

## Development Setup

1. Install prerequisites:
   - [Helm](https://helm.sh/docs/intro/install/) 3.12+
   - [helm-docs](https://github.com/norwoodj/helm-docs) (optional, for README generation)
   - [chart-testing (ct)](https://github.com/helm/chart-testing) (optional, for CI-grade linting)
   - [kubeconform](https://github.com/yannh/kubeconform) (optional, for manifest validation)
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

4. Dry-run to verify rendering:

   ```bash
   helm template ai-stack . --debug
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
