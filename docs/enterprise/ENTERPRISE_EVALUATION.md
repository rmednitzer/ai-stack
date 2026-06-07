# Enterprise Readiness Evaluation — ai-stack

**Date:** 2026-06-07
**Chart version:** 2.11.0 | **appVersion:** 2026.5

---

## Executive Summary

The ai-stack is **enterprise-ready for regulated, moderate-to-large-scale
deployments**, particularly in EU-regulated environments. It demonstrates strong
alignment with governance, security, observability, and operational requirements.

**Overall rating: Enterprise-ready**

---

## Strengths

### 1. Security Posture — Strong

| Control | Status |
|---------|--------|
| PSA restricted baseline | Enforced (`runAsNonRoot`, `drop: ALL`, `seccompProfile: RuntimeDefault`) |
| NetworkPolicy default-deny | Per-component ingress + egress allowlists |
| Secret auto-generation | Keys for Open WebUI, Qdrant, SearXNG, Open Terminal, MCPO, LangGraph, Pydantic AI, PostgreSQL, and Authelia (stable across upgrades; external secret stores supported) |
| Service account isolation | Per-component, `automountServiceAccountToken: false` |
| Read-only root filesystem | Qdrant, Valkey, Tika, SearXNG, OTel Collector |
| Telemetry opt-out | `DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY: false` |
| Ingress rate limiting | Envoy Gateway rate-limit annotations in prod |
| Ollama root exception | Documented via `assurance.platform/security-exception` annotation |

### 2. Regulatory Compliance — Excellent

- Explicit framework alignment: **NIS2**, **GDPR**, **AI Act**
- PII **and credential** redaction in telemetry pipeline (email, SSN, credit-card, plus bearer tokens, JWTs, PEM private keys, and provider API-key shapes)
- Governance-as-code annotations (`assurance.platform/*`) on all resources
- Control reference traceability (CTL-001, CTL-002, POL-001) — defined in [docs/governance/CONTROLS.md](../governance/CONTROLS.md)
- Tier classification system (T0–T2) with clear boundary labels

### 3. Observability — Production-Grade

- OpenTelemetry Collector (T0, non-negotiable tier) with full pipeline:
  receivers → batch processing → memory limiting → K8s metadata → PII redaction → export
- Prometheus ServiceMonitor support for all components (enabled in prod)
- Health probes (startup, liveness, readiness) on every service
- GenAI semantic convention enrichment for AI-specific telemetry
- Helm test hooks with both TCP and HTTP health endpoint validation

### 4. Deployment & Operations

- **Helm 3.12+** with dual profiles (lab/prod) — clean separation of concerns
- **ArgoCD** integration with manual sync for change-control compliance
- **Renovate** (`helm-values` manager, `pinDigests: true`) for digest-pinned container image bumps; **Dependabot** for GitHub Actions — SBOM/Zarf kept in lockstep per ADR-001/002
- **Pod Disruption Budgets** for single-replica/stateful components (Ollama, Qdrant, SearXNG, Valkey, Authelia, standalone PostgreSQL)
- **Topology spread constraints** in prod profile for HA
- **HPA autoscaling** for stateless components (Open WebUI, Tika)
- **Disaster recovery** via external tooling (Velero + CSI volume snapshots, CNPG barman for PostgreSQL)
- CI pipeline: Helm lint → chart-testing → kubeconform schema validation → kube-linter policy lint → SBOM tag/digest parity
- Chart version 2.11.0 with semver compliance

### 5. Architecture

- Clear microservice boundaries with tier-based classification
- Stateful/stateless separation with appropriate deployment strategies
  (Recreate for stateful, RollingUpdate for stateless)
- Internal-only services (ClusterIP) with ingress controller integration
- Opt-in components (Open Terminal, MCPO) reduce default attack surface
- All images pinned by digest (tag + `@sha256:…`), per ADR-002
- CycloneDX 1.6 SBOM ([sbom.cdx.json](../../sbom.cdx.json)) with full license and dependency graph
- License compliance matrix ([LICENSE_COMPLIANCE.md](../compliance/LICENSE_COMPLIANCE.md)) with copyleft analysis
- SBOM validation in CI (schema + component count cross-check)

### 6. Disaster Recovery

- PVCs annotated `helm.sh/resource-policy: keep` so persistent data survives `helm uninstall`
- Backup/restore is **external** by design (no built-in snapshot scheduler): Velero + CSI volume snapshots for PVC-backed data (Qdrant, Ollama models, Open WebUI), and CloudNativePG Barman object-store backups for PostgreSQL in `cnpg` mode — see [HOWTO.md §10](../../HOWTO.md#10-postgresql-modes)

---

## Remaining Considerations

### Architectural (require design decisions, not chart fixes)

| Area | Notes |
|------|-------|
| **Qdrant distributed mode** | For true HA with replication consensus, deploy Qdrant in distributed mode using its official operator. This chart provides single-instance with snapshot backup as the baseline. |
| **Multi-tenancy** | Single-namespace deployment. For multi-tenant isolation, use namespace-per-tenant with separate Helm releases and RBAC boundaries. |
| **ReadWriteOnce PVCs** | Stateful components (Qdrant, Ollama, Open WebUI) use RWO PVCs. Multi-replica for these requires external databases (PostgreSQL for Open WebUI) or shared storage (ReadWriteMany). |
| **Ollama runs as root** | Upstream requirement for GPU access. Documented with security exception annotation. Monitor upstream for rootless support. |

### Operational

| Area | Status | Recommendation |
|------|--------|----------------|
| Image digests | All images digest-pinned in values.yaml (ADR-002) | Renovate raises digest-pinned image bumps; Dependabot covers GitHub Actions; sync SBOM + Zarf in the same PR (ADR-001) |
| Velero integration | Not included | Use Velero with CSI volume snapshots for full cluster DR |
| External secret manager | Supported but optional | Use ESO or Vault CSI for production secret rotation |
| WAF | Not included | Deploy upstream WAF (ModSecurity, Coraza) for deep packet inspection |

---

## Verdict

| Dimension | Rating |
|-----------|--------|
| Security | Strong |
| Compliance / Governance | Excellent |
| Observability | Production-grade |
| High Availability | Good (HPA for stateless; stateful needs operator for full HA) |
| Disaster Recovery | Good (PVC snapshots; external DR tooling recommended) |
| Supply Chain Security | Excellent (digest-pinned images, Renovate + Dependabot, CycloneDX SBOM with parity CI, license compliance) |
| Scalability | Good (HPA autoscaling for stateless components) |
| Operational Maturity | Strong |

**Bottom line:** This stack is enterprise-grade for regulated deployments. All
critical gaps from the initial evaluation have been addressed: image pinning,
backup/restore, autoscaling, rate limiting, and Helm test coverage. The remaining
items are architectural decisions (Qdrant distributed mode, multi-tenancy) that
depend on specific deployment requirements rather than chart deficiencies.
