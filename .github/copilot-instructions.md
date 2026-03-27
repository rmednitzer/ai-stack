# Copilot Instructions for ai-stack

## Project Overview

This is a **Helm chart** (`ai-stack`) for deploying a comprehensive AI inference
and tooling stack targeting EU-regulated on-premises and hybrid Kubernetes
environments. It is NOT a typical application codebase — all source files are
Helm templates (Go template + YAML), values files, and CI workflows.

## Tech Stack

- **Helm 3** (chart type: `application`, apiVersion: v2)
- **Kubernetes 1.32+** manifests (Deployments, Services, ConfigMaps, Secrets,
  NetworkPolicies, ServiceMonitors, PVCs, ServiceAccounts)
- **Go templates** via Helm's `_helpers.tpl` and Sprig function library
- **GitHub Actions** for CI (lint, chart-testing, kubeconform, Syft SBOM, Grype CVE scan)

## Components

The chart deploys these components (each gated by an `enabled` flag in `values.yaml`):
Open WebUI, Ollama, Qdrant, Apache Tika, SearXNG, Workbench, Valkey,
Open WebUI Pipelines, Open Terminal, MCPO, LangGraph (with PostgreSQL),
async ingestion worker, and optional Authelia OIDC provider.

Each component lives under `templates/<component>/` with its own Deployment,
Service, NetworkPolicy, ServiceAccount, and optional PVC/ConfigMap/Secret.

## Key Conventions

### Naming and Labels

- Use `ai-stack.componentName` helpers from `templates/_helpers.tpl` for all
  resource names and selectors.
- All resources carry standard Helm labels (`app.kubernetes.io/*`) plus
  governance annotations (`assurance.platform/tier`, `assurance.platform/boundary`).

### Security (Non-Negotiable)

- **Pod Security Admission (PSA) restricted baseline**: `runAsNonRoot: true`,
  `allowPrivilegeEscalation: false`, `capabilities: { drop: [ALL] }`,
  `seccompProfile: { type: RuntimeDefault }`, `readOnlyRootFilesystem` where possible.
- **Dedicated ServiceAccount** per component with `automountServiceAccountToken: false`.
- **NetworkPolicy** with default-deny; explicit ingress/egress rules per component.
- **No plaintext secrets** in values or templates — use auto-generated secrets
  or `existingSecret` references.

### Values Structure

- Values documented with `# --` comment annotations (for helm-docs).
- Two profiles: `lab` (default, single-node) and `prod` (`values-prod.yaml` overlay).
- Tiering: T0 = safety/integrity, T1 = operational, T2 = productivity, T3 = exploratory.

### Conditional Deployment

Every component is gated behind `<component>.enabled` (boolean). Templates use
`{{- if .Values.<component>.enabled }}` guards.

## Development Workflow

```bash
# Lint
helm lint .
helm lint . -f values.yaml -f values-prod.yaml

# Render templates
helm template ai-stack . --debug

# Validate against K8s schemas
helm template ai-stack . | kubeconform -strict -summary -skip CustomResourceDefinition,ServiceMonitor

# Chart-testing
ct lint --config ct.yaml --charts .
```

## When Generating or Modifying Code

1. **Templates**: Write valid Go-template YAML. Indent with 2 spaces. Use
   `{{- ... }}` (trim whitespace) consistently.
2. **values.yaml**: Document every new key with `# --` annotation. Place it in
   the correct component section.
3. **Security**: Always include `securityContext`, `serviceAccountName`, and
   `networkPolicy` configuration for new components.
4. **SemVer**: Bump `Chart.yaml` version — PATCH for fixes, MINOR for new
   features, MAJOR for breaking changes.
5. **SBOM**: If adding/removing an image, update `sbom.cdx.json` to keep the
   component count in sync with `values.yaml`.

## Do NOT

- Add images without security contexts or NetworkPolicy rules.
- Hardcode secrets, passwords, or credentials in templates or values.
- Skip the `enabled` flag pattern for new components.
- Introduce CRDs without documenting them and adding kubeconform skip rules.
