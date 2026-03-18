# ai-stack

Comprehensive AI inference and tooling stack for EU-regulated on-premises and hybrid platform operations, deployed as a single Helm chart.

Includes [Open WebUI](https://github.com/open-webui/open-webui), [Ollama](https://ollama.com/) (CPU-only), [Qdrant](https://qdrant.tech/), [Apache Tika](https://tika.apache.org/), [SearXNG](https://docs.searxng.org/), [Valkey](https://valkey.io/), [Open WebUI Pipelines](https://github.com/open-webui/pipelines), [Open Terminal](https://github.com/open-webui/open-terminal), [MCPO](https://github.com/open-webui/mcpo), [Authelia](https://www.authelia.com/) for OIDC/SSO/MFA, and an [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) with PII redaction.

Optimized for VMware Tanzu v1.30.10 with [Contour](https://projectcontour.io/) ingress, [ArgoCD](https://argo-cd.readthedocs.io/) v3.3.2, and [Veeam K10 (Kasten)](https://www.kasten.io/) backup. Designed for governance-as-code environments with PSA restricted baseline, NetworkPolicy default-deny, and OpenTelemetry instrumentation hooks.

## Architecture

```mermaid
graph TD
  Ingress --> Authelia["Authelia (T0, opt-in OIDC)"]
  Ingress --> OpenWebUI["Open WebUI (T1)"]

  Authelia --> Valkey["Valkey (T2)"]
  Authelia -.->|OIDC| OpenWebUI

  OpenWebUI --> Ollama["Ollama (T1)"]
  OpenWebUI --> Qdrant["Qdrant (T1)"]
  OpenWebUI --> Tika["Tika (T2)"]
  OpenWebUI --> SearXNG["SearXNG (T2)"]
  OpenWebUI --> Valkey
  OpenWebUI --> Pipelines["Pipelines (T1)"]

  OpenWebUI --> OpenTerminal["Open Terminal (T2, opt-in)"]
  OpenWebUI --> MCPO["MCPO (T2, opt-in)"]
  OpenWebUI --> ExternalAPIs["External APIs (T1, opt-in)"]

  OTel["OTel Collector (T0)"]

  style OTel stroke-dasharray: 5 5
  style Authelia stroke-dasharray: 5 5
  style OpenTerminal stroke-dasharray: 5 5
  style MCPO stroke-dasharray: 5 5
  style ExternalAPIs stroke-dasharray: 5 5
```

### Component Tiers

Tiering follows the platform-assurance stack-bom classification:

| Tier | Meaning | Components |
|------|---------|------------|
| T0 | Safety / Integrity | OTel Collector, Authelia |
| T1 | Operational | Open WebUI, Ollama, Qdrant, Pipelines |
| T2 | Productivity | Tika, SearXNG, Valkey, Open Terminal, MCPO |

### Default Images

| Component | Image | Version |
|-----------|-------|---------|
| Open WebUI | `ghcr.io/open-webui/open-webui` | v0.8.10 |
| Ollama | `ollama/ollama` | 0.18.1 |
| Qdrant | `qdrant/qdrant` | v1.17.1 |
| Tika | `apache/tika` | 3.2.3.0 |
| SearXNG | `searxng/searxng` | 2026.3.16 |
| Valkey | `valkey/valkey` | 8.1 |
| Pipelines | `ghcr.io/open-webui/pipelines` | 0.1.2 |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | 0.11.20 |
| MCPO | `ghcr.io/open-webui/mcpo` | 0.2.0 |
| Authelia | `ghcr.io/authelia/authelia` | 4.39 |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 0.147.0 |

## Prerequisites

- Kubernetes 1.30+
- Helm 3.12+
- A StorageClass for PersistentVolumeClaims (or use `emptyDir` for lab)
- Contour ingress controller
- (Optional) Veeam K10 (Kasten) for application-aware backup and disaster recovery
- (Optional) Prometheus Operator CRDs for ServiceMonitor resources
- (Optional) cert-manager for automated TLS certificate provisioning

## Quick Start

```bash
# Install with lab defaults
helm install ai-stack . -n ai-stack --create-namespace

# Production overlay
helm install ai-stack . -n ai-stack --create-namespace \
  -f values.yaml -f values-prod.yaml
```

Pull your first models:

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull llama3.2
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull nomic-embed-text
```

Access Open WebUI:

```bash
kubectl port-forward -n ai-stack svc/ai-stack-openwebui 8080:8080
# Open http://localhost:8080
```

## Configuration

The chart ships two value files:

| File | Purpose |
|------|---------|
| `values.yaml` | Full reference with all defaults (lab profile) |
| `values-prod.yaml` | Production overlay — HA, TLS ingress, stricter resources, OTel, backups |

### Global Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.profile` | Deployment profile (`lab` or `prod`) | `lab` |
| `global.namespace` | Target namespace | `ai-stack` |
| `global.imagePullPolicy` | Image pull policy | `IfNotPresent` |
| `global.storageClass` | Storage class for all PVCs | `""` (cluster default) |
| `global.podSecurityStandard` | PSA enforcement level | `restricted` |
| `global.networkPolicy.enabled` | Deploy default-deny NetworkPolicies | `true` |
| `global.otel.enabled` | Deploy OTel Collector and inject env vars | `false` |
| `global.otel.endpoint` | OTLP endpoint | `http://otel-collector....:4317` |
| `global.serviceMonitor.enabled` | Create Prometheus ServiceMonitor CRDs | `false` |
| `global.backup.enabled` | Create a Veeam K10 Policy CR for stateful data | `false` |
| `global.backup.frequency` | K10 backup frequency | `@daily` |

### Component Toggles

Every component can be individually enabled or disabled:

```yaml
openwebui:
  enabled: true     # Primary UI (default: true)
ollama:
  enabled: true     # LLM inference (default: true)
qdrant:
  enabled: true     # Vector DB for RAG (default: true)
tika:
  enabled: true     # Document extraction (default: true)
searxng:
  enabled: true     # Web search (default: true)
pipelines:
  enabled: true     # Function pipelines (default: true)
valkey:
  enabled: true     # Session cache (default: true)
openTerminal:
  enabled: false    # Sandboxed terminal for AI agents (opt-in)
mcpo:
  enabled: false    # MCP-to-OpenAPI proxy (opt-in)
authelia:
  enabled: false    # OIDC identity provider for SSO/MFA (opt-in)
```

### Secrets

The chart auto-generates secrets on first install for:

- **Qdrant API key** (`qdrant-secret`)
- **SearXNG secret key** (`searxng-secret`)
- **Open Terminal API key** (`open-terminal-secret`)
- **MCPO API key** (`mcpo-secret`)
- **Authelia secrets** (`authelia-secret`) — JWT secret, session secret, storage encryption key, OIDC client secret

Secrets are annotated with `helm.sh/resource-policy: keep` so they survive `helm upgrade`. To use an external secret manager (e.g., ESO or Vault), set the corresponding value:

```yaml
qdrant:
  apiKey: "your-external-key"
searxng:
  secretKey: "your-external-key"
openTerminal:
  apiKey: "your-external-key"
mcpo:
  apiKey: "your-external-key"
```

### Ingress

```yaml
openwebui:
  ingress:
    enabled: true
    className: "contour"
    hosts:
      - host: ai.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: ai-tls
        hosts:
          - ai.example.com
```

### External Inference APIs

Add cloud-hosted LLM providers (OpenAI, Azure OpenAI, Anthropic, Gemini, Mistral, etc.) alongside local Ollama inference:

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: openai
      baseUrl: "https://api.openai.com/v1"
      apiKey: "sk-..."
    - name: gemini
      baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai"
      apiKey: "AIza..."
```

API keys are stored in Kubernetes Secrets. For production, use an external secret manager:

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: openai
      baseUrl: "https://api.openai.com/v1"
      existingSecret:
        name: "my-openai-secret"
        key: "api-key"
```

When enabled, Open WebUI users can select external models from the model picker alongside locally-served Ollama models. HTTPS egress (port 443) is automatically added to the Open WebUI NetworkPolicy.

### Authelia (SSO / OIDC)

Enable Authelia as an OpenID Connect identity provider for Open WebUI. When enabled, Open WebUI is automatically configured as an OIDC client (`OAUTH_*` environment variables are injected). Authelia uses Valkey for session storage (when available) and SQLite as its storage backend.

```yaml
authelia:
  enabled: true
  domain: "example.local"
  defaultPolicy: "one_factor"  # or "two_factor" for MFA
  oidc:
    clientId: "openwebui"
    issuerUrl: "https://auth.example.local"
  ingress:
    enabled: true
    className: "contour"
    hosts:
      - host: auth.example.local
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: auth-tls
        hosts:
          - auth.example.local
```

Users are managed via a file-based backend (`users_database.yml`). Override by mounting a custom ConfigMap or configure LDAP. Generate password hashes with `authelia crypto hash generate argon2`.

### OpenTelemetry

When `global.otel.enabled=true`, the chart:

1. Deploys an OTel Collector with OTLP receivers, GenAI semantic conventions, and PII redaction
2. Injects `OTEL_*` environment variables into all component pods
3. Optionally creates ServiceMonitor resources for Prometheus scraping

### Backups

When `global.backup.enabled=true`, the chart creates a Veeam K10 (Kasten) Policy custom resource that provides application-aware backup and disaster recovery for all stateful components (Qdrant snapshots, Ollama model blobs, Valkey data). The Policy CR is configured with the schedule set by `global.backup.frequency` (default: `@daily`). K10 handles snapshot orchestration, retention, and optional off-cluster export — no in-chart CronJobs are required.

## Security

This chart is designed for regulated environments:

- **Network isolation**: Default-deny ingress and egress with per-component allowlists
- **Pod Security**: PSA restricted baseline — `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, capabilities `drop: [ALL]`
- **Read-only root filesystem**: Enforced for Qdrant, Valkey, Tika, SearXNG, OTel Collector
- **Identity isolation**: Per-component ServiceAccounts with `automountServiceAccountToken: false`
- **Secret management**: Auto-generated 64-byte credentials with support for external secret stores
- **PII redaction**: OTel Collector strips email addresses, SSNs, and credit card numbers from telemetry (GDPR Art 5(1)(c))
- **Telemetry opt-out**: `DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY=false` set by default
- **Rate limiting**: Contour rate-limit annotations in production profile
- **Ollama root exception**: Upstream model management requirement; documented with `assurance.platform/security-exception` annotation

## Governance and Compliance

The chart aligns with the platform-assurance governance framework:

| Control | Description | Implementation |
|---------|-------------|----------------|
| CTL-0006 | Observability | OTel Collector, ServiceMonitors |
| CTL-0009 | AI gateway policy | NetworkPolicy, tier labels, boundary annotations |
| POL-03 | Least-privilege | Per-component ServiceAccounts, no automount |
| GDPR Art 5(1)(c) | Data minimisation | PII redaction in OTel pipeline |
| NIS2 | Network security | Default-deny NetworkPolicies |
| AI Act | Risk classification | Tier and boundary labeling |

All pods carry `assurance.platform/*` annotations for evidence pipeline integration and audit traceability.

## SBOM and License Compliance

The chart includes a machine-readable Software Bill of Materials and license compliance documentation:

| File | Format | Purpose |
|------|--------|---------|
| [sbom.cdx.json](sbom.cdx.json) | CycloneDX 1.6 JSON | Machine-readable SBOM with all container images, licenses, purls, and dependency graph |
| [LICENSE_COMPLIANCE.md](LICENSE_COMPLIANCE.md) | Markdown | Human-readable license matrix, copyleft analysis, and enterprise compliance checklist |

All default-enabled components use permissive licenses (MIT, Apache-2.0, BSD-3-Clause). Notable exceptions:

- **SearXNG** (AGPL-3.0): Low risk when using the upstream container unmodified. See compliance doc for details.

The SBOM is validated in CI against the CycloneDX 1.6 schema and cross-checked against `values.yaml` to ensure completeness. Deep per-image SBOMs are generated via Syft and uploaded as CI artifacts.

## CI Pipeline

The GitHub Actions workflow (`lint.yaml`) runs on every PR and push to `main`:

| Job | What it does |
|-----|--------------|
| **helm-lint** | `helm lint` and `helm template` for both lab and prod profiles |
| **chart-testing** | `ct lint` with chart-testing for standards compliance |
| **sbom-validate** | Validates `sbom.cdx.json` against CycloneDX 1.6 schema; cross-checks component count against `values.yaml` |
| **syft-sbom** | Generates deep per-image SBOMs via Syft, validates them, and uploads as artifacts |
| **cve-scan** | Scans all container images for CVEs using Grype; fails on critical vulnerabilities |
| **kubeconform** | Validates rendered manifests against Kubernetes JSON schemas (lab + prod profiles) |

## GitOps / ArgoCD

Pre-built ArgoCD Application manifests are provided in `argocd/`:

| File | Profile | Notes |
|------|---------|-------|
| `argocd/application-lab.yaml` | Lab | Auto-sync disabled — suitable for development |
| `argocd/application-prod.yaml` | Production | Manual sync — change-control compliance |

## Dependency Management

GitHub Actions versions are managed by [Dependabot](https://docs.github.com/en/code-security/dependabot). Container image versions in `values.yaml` are managed manually. Configuration is in `.github/dependabot.yml`.

## Verification

After installation, verify the deployment:

```bash
# Check all pods are running
kubectl get pods -n ai-stack

# Verify NetworkPolicies are applied
kubectl get networkpolicies -n ai-stack

# Check secrets were generated
kubectl get secrets -n ai-stack

# Verify ServiceAccounts
kubectl get serviceaccounts -n ai-stack

# Check PodDisruptionBudgets
kubectl get pdb -n ai-stack

# Run Helm tests
helm test ai-stack -n ai-stack
```

## Development

```bash
# Lint the chart
helm lint .

# Lint with production values
helm lint . -f values.yaml -f values-prod.yaml

# Template rendering check
helm template ai-stack . --debug

# Dry-run install
helm install ai-stack . --dry-run --debug -n ai-stack

# Chart-testing
ct lint --config ct.yaml --charts .
```

See [HOWTO.md](HOWTO.md) for a comprehensive task-oriented guide covering installation, day-1 setup, RAG configuration, scaling, backup/restore, EU compliance, and troubleshooting.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on pull requests, security contexts, and governance labels.

## EU Compliance

The chart ships with templates and guidance for EU-regulated deployments:

| Document | Purpose |
|----------|---------|
| [EU_COMPLIANCE_CHECK.md](EU_COMPLIANCE_CHECK.md) | Gap analysis against GDPR, AI Act, NIS2, CRA, ePrivacy |
| [SECURITY.md](SECURITY.md) | Coordinated vulnerability disclosure (CVD) policy |
| [docs/compliance/DPIA_TEMPLATE.md](docs/compliance/DPIA_TEMPLATE.md) | Data Protection Impact Assessment template (GDPR Art. 35 + AI Act Art. 27) |
| [docs/compliance/ROPA_TEMPLATE.md](docs/compliance/ROPA_TEMPLATE.md) | Records of Processing Activities template (GDPR Art. 30) |
| [docs/compliance/INCIDENT_RESPONSE.md](docs/compliance/INCIDENT_RESPONSE.md) | Incident response playbook (GDPR Art. 33/34, NIS2 Art. 23, AI Act Art. 73) |
| [docs/compliance/DSAR_PROCEDURES.md](docs/compliance/DSAR_PROCEDURES.md) | Data subject rights procedures (GDPR Art. 15–22) |
| [docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) | Data retention, DPA guidance, encryption, content marking, training |

AI Act Art. 50(1) transparency is implemented via a configurable `WEBUI_BANNER_TEXT` environment variable that informs users they are interacting with an AI system.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Maintainers

| Name | Email |
|------|-------|
| Roman Mednitzer | r.mednitzer@outlook.com |
