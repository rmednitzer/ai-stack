# Enterprise Readiness Evaluation — ai-stack

**Date:** 2026-03-17
**Chart version:** 1.0.0 | **appVersion:** 2026.1

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
| Secret auto-generation | 64-byte keys for Qdrant, SearXNG, Workbench, Open Terminal, MCPO |
| Service account isolation | Per-component, `automountServiceAccountToken: false` |
| Read-only root filesystem | Qdrant, Valkey, Tika, SearXNG, OTel Collector |
| Telemetry opt-out | `DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY: false` |
| Ingress rate limiting | Envoy Gateway rate-limit annotations in prod |
| Ollama root exception | Documented via `assurance.platform/security-exception` annotation |

### 2. Regulatory Compliance — Excellent

- Explicit framework alignment: **NIS2**, **GDPR**, **AI Act**
- PII redaction in telemetry pipeline (email, SSN, credit card patterns)
- Governance-as-code annotations (`assurance.platform/*`) on all resources
- Control reference traceability (CTL-006, CTL-009, POL-003)
- Tier classification system (T0–T3) with clear boundary labels

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
- **Dependabot** for GitHub Actions dependency management; container image versions managed manually
- **Pod Disruption Budgets** for stateful components (Ollama, Qdrant)
- **Topology spread constraints** in prod profile for HA
- **HPA autoscaling** for stateless components (Open WebUI, Tika, Pipelines)
- **Backup CronJobs** for Qdrant snapshots and Ollama model data
- CI pipeline: Helm lint → chart-testing → kubeconform schema validation
- Chart version 1.0.0 with semver compliance

### 5. Architecture

- Clear microservice boundaries with tier-based classification
- Stateful/stateless separation with appropriate deployment strategies
  (Recreate for stateful, RollingUpdate for stateless)
- Internal-only services (ClusterIP) with ingress controller integration
- Opt-in components (Workbench, Open Terminal, MCPO) reduce default attack surface
- All images pinned to versioned tags
- CycloneDX 1.6 SBOM ([sbom.cdx.json](sbom.cdx.json)) with full license and dependency graph
- License compliance matrix ([LICENSE_COMPLIANCE.md](LICENSE_COMPLIANCE.md)) with copyleft analysis
- SBOM validation in CI (schema + component count cross-check)

### 6. Disaster Recovery

- Qdrant snapshot-based backup via CronJob with configurable schedule
- Ollama model manifest and blob backup via CronJob
- Backup PVC with `helm.sh/resource-policy: keep` annotation
- Configurable retention (default: 7 Qdrant snapshots, 3 Ollama backups)

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
| Image digests | Container image versions pinned in values.yaml | Review Dependabot PRs for GitHub Actions; manually track container image updates |
| Velero integration | Not included | Pair backup CronJobs with Velero for full cluster DR |
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
| Disaster Recovery | Addressed (snapshot + model backup CronJobs) |
| Supply Chain Security | Excellent (versioned tags + Dependabot + CycloneDX SBOM + license compliance) |
| Scalability | Good (HPA autoscaling for stateless components) |
| Operational Maturity | Strong |

**Bottom line:** This stack is enterprise-grade for regulated deployments. All
critical gaps from the initial evaluation have been addressed: image pinning,
backup/restore, autoscaling, rate limiting, and Helm test coverage. The remaining
items are architectural decisions (Qdrant distributed mode, multi-tenancy) that
depend on specific deployment requirements rather than chart deficiencies.
