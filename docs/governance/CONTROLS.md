# ai-stack Governance Controls and Policies

This document is the **authoritative registry** for all control (CTL) and
policy (POL) identifiers used in the ai-stack Helm chart. Every
`assurance.platform/control-refs` annotation in templates and every
governance reference in documentation traces back to an entry here.

---

## How to Use This Registry

- **`assurance.platform/control-refs`** annotations in Kubernetes resources
  carry a comma-separated list of CTL/POL identifiers, e.g.
  `"CTL-001,CTL-002"`.
- Template comment blocks reference identifiers with a short description, e.g.
  `# CTL-001: Logging legality, minimisation, and forensic correlation`.
- When adding a new control or policy, append a new entry to the appropriate
  table below, using the next sequential number.

---

## Controls (CTL)

Controls are **technical or procedural measures** that enforce a specific
security or compliance requirement at the platform level.

| ID | Title | Description | Implemented By | Regulatory Basis |
|----|-------|-------------|----------------|-----------------|
| **CTL-001** | Observability — logging legality, minimisation, and forensic correlation | All platform components export logs, metrics, and traces via the OTel Collector. PII and credential material are redacted at the pipeline layer — email, SSN/VSNR, and credit-card patterns, plus bearer tokens, JWTs, PEM private keys, and OpenAI/AWS/GitHub/GitLab/Google/Slack/Stripe API-key shapes — before forwarding to the observability backend. Forensic correlation is maintained via trace IDs across services. | OTel Collector (`templates/otel/otel-collector.yaml`), ServiceMonitors (`templates/otel/servicemonitors.yaml`) | GDPR Art. 5(1)(c) data minimisation; NIS2 Art. 21(2)(b) incident handling; CRA Annex I vulnerability monitoring |
| **CTL-002** | AI gateway policy — OTel GenAI instrumentation and network boundary enforcement | All AI inference traffic is governed by NetworkPolicies (default-deny with explicit allowlists), tier labels (`T0`–`T2`), and boundary annotations (one of the canonical values defined in [Governance label vocabulary](#governance-label-vocabulary)). The OTel Collector enriches AI-related telemetry with GenAI semantic conventions for audit traceability. | NetworkPolicies (`templates/common/networkpolicies.yaml`), OTel Collector, the Envoy AI Gateway model-egress CRs (`templates/ai-gateway/`), and `tier`/`boundary` labels plus a `control-refs` annotation on every workload | NIS2 Art. 21(2)(a) risk policies; AI Act Art. 26 deployer monitoring obligations; GDPR Art. 25 data protection by design |

---

## Policies (POL)

Policies are **organisational rules** that govern how the platform is
configured and operated. Unlike controls, policies may not be fully
automatable — they require operational discipline in addition to
technical enforcement.

| ID | Title | Description | Enforced By | Regulatory Basis |
|----|-------|-------------|-------------|-----------------|
| **POL-001** | Least-privilege access control | Every component runs under a dedicated Kubernetes ServiceAccount with `automountServiceAccountToken: false`. No component shares a ServiceAccount with another. RBAC is scoped to the minimum required. Pods run as non-root with all Linux capabilities dropped. | Per-component ServiceAccounts (`templates/common/serviceaccounts.yaml`), `securityContext` on all Deployments, reverse-referenced by the `assurance.platform/control-refs` annotation on every workload | NIS2 Art. 21(2)(i) access control; GDPR Art. 25 data protection by design; CRA Annex I §1(b) least-privilege |

---

## Governance label vocabulary

Every workload — every `Deployment`, plus the CloudNativePG `Cluster`/`Pooler`
and the Valkey and OTel Collector Deployments — carries two governance **labels**
(`tier`, `boundary`) and one **annotation** (`control-refs`), on both the
controller object and (for Deployments) its pod template, so controller and pod
scans see identical governance metadata.
The rendered templates are the **source of truth**; the per-component docs and
this registry mirror them, and `tests/governance_labels_test.yaml` asserts the
mapping so the three can no longer drift apart.

**Tier** (`assurance.platform/tier`) — operational criticality:

| Value | Meaning |
|-------|---------|
| `T0` | Safety / integrity plane — identity and observability (Authelia, OTel Collector) |
| `T1` | Operational plane — model serving, retrieval, and the decision/agent front door (Open WebUI, Ollama, Qdrant, LangGraph, Pydantic AI) |
| `T2` | Productivity plane — supporting services and datastores (Tika, SearXNG, MCPO, Open Terminal, PostgreSQL, Valkey, ingestion worker) |

**Boundary** (`assurance.platform/boundary`) — the trust boundary the workload sits on:

| Value | Meaning | Components |
|-------|---------|-----------|
| `authentication` | Identity and access decisions | Authelia |
| `decision` | Model/agent decision and tool-brokering plane | Open WebUI, MCPO, LangGraph, Pydantic AI |
| `model-serving` | Model inference serving | Ollama, Envoy AI Gateway |
| `retrieval` | RAG vector retrieval | Qdrant |
| `ingestion` | Content ingestion (documents, web search) | Tika, SearXNG, ingestion worker |
| `execution` | Model-generated code execution | Open Terminal |
| `storage` | Durable and session-state datastores | PostgreSQL, Valkey |
| `observability` | Telemetry collection and redaction | OTel Collector |

**Control refs** (`assurance.platform/control-refs`) — a comma-separated list of
the CTL/POL identifiers above that the workload implements. This is an
**annotation, not a label**: a Kubernetes label value cannot contain commas, so a
multi-value list must be carried as an annotation. Every workload references at
least `CTL-002` (network-boundary governance) and `POL-001` (least-privilege
identity); the OTel Collector additionally references `CTL-001` (observability).
The old coarse `internal`/`decision`-only boundary vocabulary is retired in
favour of the table above (ADR-005).

---

## Adding New Entries

1. Determine whether the entry is a technical control (CTL) or an
   organisational policy (POL).
2. Assign the next sequential number: `CTL-003`, `POL-002`, etc.
3. Add a row to the appropriate table above.
4. Add `assurance.platform/control-refs` annotation(s) to the relevant
   Kubernetes resource templates.
5. Reference the identifier in template comment blocks and in `values.yaml`.
6. Update `README.md` §Governance and Compliance if the control or policy
   is user-facing.

---

*Registry version: 2.12.0 | Maintained alongside Chart version in `Chart.yaml`.*
