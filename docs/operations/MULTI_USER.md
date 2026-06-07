# Multi-User Operations — isolation, cost, and audit retention

**Chart version:** 2.11.0 · **Last reviewed:** 2026-06-07

ai-stack is designed to serve **many users from one deployment**. This guide
covers the three concerns that a single-user lab does not exercise: **tenant
isolation**, **cost control**, and **audit retention**. For the baseline security
posture see [`SECURITY_BASELINE.md`](../SECURITY_BASELINE.md); for task-oriented
setup see [`HOWTO.md`](../../HOWTO.md).

> The chart already makes Open WebUI horizontally scalable out of the box (shared
> PostgreSQL for state, Valkey for sessions/websockets, a stable
> `WEBUI_SECRET_KEY` across replicas). The work below is what you add *around*
> that to run it safely for a user population.

---

## 1. Identity: one front door, per-user accounts

Enable **Authelia** (`authelia.enabled=true`) so every user authenticates via OIDC
(optionally MFA with `defaultPolicy: two_factor`). The chart auto-wires Open WebUI
as the OIDC client. The identity chain you are building:

```
Authelia (OIDC + groups) → Open WebUI (role/group mapping) → model & tool access → OTel audit trail
```

- **MUST**: keep `openwebui.env.WEBUI_AUTH: "true"` (the default). Never run a
  multi-user deployment with auth disabled.
- **SHOULD**: set `DEFAULT_USER_ROLE` to `pending` so new SSO users require admin
  approval before they can use models.

---

## 2. Per-user / per-group model & tool access

Open WebUI has **built-in role and group management** that can be driven from the
Authelia OIDC token, so you can scope which users reach which models and tools.
Configure the claims in Authelia and the matching controls under `openwebui.env`
(authoritative names/semantics are in Open WebUI's environment-variable docs):

```yaml
openwebui:
  env:
    ENABLE_OAUTH_ROLE_MANAGEMENT: "true"
    OAUTH_ROLES_CLAIM: "groups"          # claim Authelia emits
    OAUTH_ALLOWED_ROLES: "ai-users,ai-power"
    OAUTH_ADMIN_ROLES: "ai-admins"
    ENABLE_OAUTH_GROUP_MANAGEMENT: "true"
    DEFAULT_USER_ROLE: "pending"
```

- **Model access** is then assignable per group in the Open WebUI admin UI
  (restrict expensive/external models to a privileged group).
- **Workspace/knowledge isolation**: keep each tenant's RAG corpus in its **own
  Qdrant collection** and grant access per group. The chart does not auto-partition
  collections — treat collection naming as a tenancy boundary you own.

### Hard isolation: namespace-per-tenant

For regulatory hard isolation (separate data stores, separate blast radius), run
**one Helm release per tenant namespace** rather than shared multi-tenancy inside
one namespace. This is the recommended pattern for strong tenant separation; the
shared-namespace controls above are appropriate for cooperative, same-trust-domain
user populations.

---

## 3. Cost control

### 3.1 Namespace guardrails (`ResourceQuota` + `LimitRange`)

The chart sets per-pod requests/limits, but a `ResourceQuota` caps the *namespace*
and a `LimitRange` defaults any pod that forgets to. Apply alongside the release:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ai-stack-quota
  namespace: ai-stack
spec:
  hard:
    requests.cpu: "16"
    requests.memory: 48Gi
    limits.cpu: "32"
    limits.memory: 96Gi
    requests.nvidia.com/gpu: "2"
    persistentvolumeclaims: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: ai-stack-defaults
  namespace: ai-stack
spec:
  limits:
    - type: Container
      default: { cpu: "1", memory: 1Gi }
      defaultRequest: { cpu: 100m, memory: 128Mi }
```

### 3.2 GPU is the dominant cost — size Ollama deliberately

GPUs are the largest line item and Ollama is the GPU consumer.

- **Right-size, don't over-request.** One `nvidia.com/gpu` is one whole GPU
  (not fractional). Co-locate models on a single GPU via `OLLAMA_KEEP_ALIVE`
  tuning rather than requesting more GPUs.
- **Idle reclaim.** Lower `ollama.env.OLLAMA_KEEP_ALIVE` (e.g. `"30s"`) so idle
  models unload from VRAM; raise it for latency-sensitive, steady traffic.
- **Pin GPU workloads to GPU nodes** with `global.nodeSelector` + `global.tolerations`
  so non-GPU pods never occupy expensive nodes.
- **Persist the model cache** (`ollama.persistence.enabled=true`, the default) so
  models are not re-downloaded (egress + cold-start cost) on every restart.
- **Scaling economics.** Stateless tiers (Open WebUI, Tika, ingestion-worker)
  scale cheaply via HPA. Ollama is GPU-bound and does **not** autoscale on GPU —
  add replicas (and GPUs) deliberately, or offload burst/large models to
  `externalAPIs` / `aiGateway` and reserve local GPU for steady, sensitive work.

### 3.3 Token budgets for external models

When users can reach hosted providers, enable the gateway's token rate-limiting
(`aiGateway.enabled=true`, `aiGateway.rateLimit.enabled=true`) to cap spend per
client window — the chart's only in-band consumption control (OWASP **LLM10**).

---

## 4. Audit retention — two different clocks

Multi-user, regulated operation has **two retention requirements that pull in
opposite directions**; do not conflate them:

| Purpose | Driver | Typical window | Where |
|---------|--------|----------------|-------|
| **Data minimisation** | GDPR Art. 5(1)(c) | Short (e.g. 30–90d for operational logs/metrics) — see [`EU_OPERATIONS_GUIDE.md`](../compliance/EU_OPERATIONS_GUIDE.md) | OTel pipeline → backend retention policy |
| **Forensic / incident audit** | NIS2 Art. 21(2)(b); AI Act Art. 26 | Longer floor (per your incident-response policy) | **Off-cluster, append-only** sink |

Key points:

- The in-cluster OTel pipeline is **collection + redaction, not immutable
  retention** (LIMITATIONS **L5**). For audit-grade evidence, export to an
  external append-only store (object lock / WORM) and apply retention there.
- PII **and credentials** are redacted before export (see B8 in the baseline), so
  the audit trail records *who did what* (trace IDs, governance labels) without
  hoarding sensitive content — satisfying both clocks at once.
- Governance labels (`assurance.platform/tier|boundary`, `control-refs`) are on
  every span's resource attributes, so audit queries can pivot by control
  ([`CONTROLS.md`](../governance/CONTROLS.md)).

---

## 5. Multi-user readiness checklist

- [ ] Authelia enabled (MFA for privileged groups); `WEBUI_AUTH=true`.
- [ ] `DEFAULT_USER_ROLE=pending`; model access scoped per group.
- [ ] Per-tenant Qdrant collections (or namespace-per-tenant for hard isolation).
- [ ] `ResourceQuota` + `LimitRange` applied to the namespace.
- [ ] GPU workloads pinned to GPU nodes; `OLLAMA_KEEP_ALIVE` tuned; model cache persisted.
- [ ] External-model token rate-limiting enabled (`aiGateway.rateLimit`).
- [ ] OTel exported off-cluster to an append-only sink with a forensic retention floor.
- [ ] PostgreSQL `mode: cnpg` (HA); for session survival across a node drain run Valkey multi-replica / clustered (the shipped single-replica PDB is drain-safe but does not by itself prevent the reschedule).
