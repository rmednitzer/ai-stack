# Enterprise Readiness Evaluation — ai-stack

**Date:** 2026-03-17
**Chart version:** 0.1.0 | **appVersion:** 2026.1

---

## Executive Summary

The ai-stack is **well-suited for enterprise deployments**, particularly in
EU-regulated environments. It demonstrates strong alignment with governance,
security, and observability requirements expected of production infrastructure.
Several areas warrant attention before large-scale rollout.

**Overall rating: Enterprise-ready with caveats** (see Gaps below).

---

## Strengths

### 1. Security Posture — Strong

| Control | Status |
|---------|--------|
| PSA restricted baseline | Enforced (`runAsNonRoot`, `drop: ALL`, `seccompProfile: RuntimeDefault`) |
| NetworkPolicy default-deny | Per-component ingress + egress allowlists |
| Secret auto-generation | 64-byte keys for Qdrant, SearXNG, Workbench, Open Terminal, MCPO |
| Service account isolation | Per-component, `automountServiceAccountToken: false` |
| Read-only root filesystem | Qdrant, Valkey, Tika, SearXNG |
| Telemetry opt-out | `DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`, `ANONYMIZED_TELEMETRY: false` |

### 2. Regulatory Compliance — Excellent

- Explicit framework alignment: **NIS2**, **GDPR**, **AI Act**
- PII redaction in telemetry pipeline (email, SSN, credit card patterns)
- Governance-as-code annotations (`assurance.platform/*`) on all resources
- Control reference traceability (CTL-0006, CTL-0009, POL-03)
- Tier classification system (T0–T3) with clear boundary labels

### 3. Observability — Production-Grade

- OpenTelemetry Collector (T0, non-negotiable tier) with full pipeline:
  receivers → batch processing → memory limiting → K8s metadata → PII redaction → export
- Prometheus ServiceMonitor support for all components
- Health probes (startup, liveness, readiness) on every service
- GenAI semantic convention enrichment for AI-specific telemetry

### 4. Deployment & Operations

- **Helm 3.12+** with dual profiles (lab/prod) — clean separation of concerns
- **ArgoCD** integration with manual sync for change-control compliance
- **Renovate** dependency management grouped by tier
- **Pod Disruption Budgets** for stateful components (Ollama, Qdrant)
- **Topology spread constraints** in prod profile for HA
- CI pipeline: Helm lint → chart-testing → kubeconform schema validation

### 5. Architecture

- Clear microservice boundaries with tier-based classification
- Stateful/stateless separation with appropriate deployment strategies
  (Recreate for stateful, RollingUpdate for stateless)
- Internal-only services (ClusterIP) with ingress controller integration
- Opt-in components (Workbench, Open Terminal, MCPO) reduce default attack surface

---

## Gaps & Risks

### High Priority

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **No HA for Qdrant** | Single replica in prod; vector DB is a SPOF | Migrate to Qdrant distributed mode or add replica support with consensus |
| **No backup/restore strategy** | Data loss risk for Ollama models, Qdrant vectors, Open WebUI state | Implement Velero or CSI snapshot-based backups; document RPO/RTO targets |
| **Image tags, not digests, in prod** | Supply chain risk; mutable tags can change | Pin all prod images to `@sha256:` digests (noted in values-prod.yaml but not enforced) |
| **Some images use `latest`/`main` tags** | Open Terminal (`latest`), Pipelines (`main`), MCPO (`main`) — non-deterministic | Pin to versioned releases or digests |

### Medium Priority

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| **No RBAC policies** | Chart creates ServiceAccounts but no Roles/RoleBindings | Add least-privilege RBAC if any component needs K8s API access |
| **Ollama runs as root** | Breaks PSA restricted purity; wider blast radius | Track upstream support for rootless Ollama |
| **No HPA / autoscaling** | Manual replica management; no load-based scaling | Add HPA for stateless components (Open WebUI, Pipelines, Tika) |
| **No rate limiting at ingress** | DoS exposure on the AI inference endpoint | Configure rate limiting in Envoy Gateway or add WAF |
| **ReadWriteOnce PVCs** | Blocks multi-replica scaling for stateful components | Evaluate ReadWriteMany or object storage for shared state |
| **No multi-tenancy** | Single-namespace deployment; no tenant isolation | If multi-tenant use is planned, add namespace-per-tenant or RBAC boundaries |

### Low Priority

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| Chart version 0.1.0 | Pre-1.0 signals instability to enterprise consumers | Adopt semver and publish a changelog |
| No Helm test hooks | Post-install validation is manual | Add `helm test` templates for smoke testing |
| SearXNG `secret_key` FIXME in prod | Potential misconfiguration if not overridden | Add validation or default-generation like other secrets |

---

## Verdict

| Dimension | Rating |
|-----------|--------|
| Security | Strong |
| Compliance / Governance | Excellent |
| Observability | Production-grade |
| High Availability | Needs work |
| Disaster Recovery | Not addressed |
| Supply Chain Security | Partially addressed |
| Scalability | Basic (manual) |
| Operational Maturity | Good |

**Bottom line:** This stack is enterprise-grade for **regulated, moderate-scale
deployments** (e.g., internal AI platform for a mid-to-large organization). The
governance, security, and observability foundations are ahead of most open-source
AI stacks. The primary gaps — HA for stateful services, backup/restore, image
pinning, and autoscaling — are standard hardening steps that should be addressed
before production rollout at scale.
