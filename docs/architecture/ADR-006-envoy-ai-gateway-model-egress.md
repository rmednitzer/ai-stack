# ADR-006 — Envoy AI Gateway for governed model egress

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.9.0
- **Supersedes:** none (the `externalAPIs` egress path is retained as a lightweight, implementation-agnostic alternative; the two are mutually exclusive — see Decision §2)

---

## Context

External inference is today wired **only into Open WebUI**: the `externalAPIs`
block (`values.yaml`, tier `T1` / boundary `model-serving`) injects per-provider
OpenAI-compatible base URLs + keys into Open WebUI alone. The other model-driven
components — `pydanticai`, `langgraph`, `ingestionWorker` — each only know
`OLLAMA_BASE_URL`. Two consequences follow:

- **No single model-egress boundary.** Reaching an external provider is an
  Open WebUI-only privilege; the agentic runtimes cannot use governed external
  models without duplicating key wiring per component.
- **Scattered credentials.** Each consumer that wanted an external provider would
  hold its own key in its own Secret — many egress points, no central policy or
  audit chokepoint.

For a stack whose identity is *governed, EU-regulated, secure-by-default*, the
natural fix is one in-cluster, auditable OpenAI-compatible endpoint that every
consumer targets — the place to centralize provider credentials, enforce
token/usage limits, attach per-user identity, and log egress.

Two implementations were evaluated:

- **LiteLLM** — most popular, but **open-core**: an MIT core plus a **proprietary
  `enterprise/` carve-out bundled in the published image**, and the features that
  *are* the governance story (SSO/OIDC, JWT+RBAC, audit logs with retention,
  per-key/team budget enforcement, secret-detection guardrails, GDPR opt-out) are
  all enterprise-gated. Shipping it through the Helm chart **and** the Zarf
  air-gap package would **redistribute non-OSI files** to enforce policies an
  operator must *separately license to enable*. This is the same class of
  licensing liability ADR-004 flagged in LangGraph's Elastic-2.0 runtime — there
  answered by adding a permissive alternative (Pydantic AI) while keeping
  LangGraph; here it is answered by declining LiteLLM in favour of a permissive
  gateway.
- **[Envoy AI Gateway](https://aigateway.envoyproxy.io/)** — **Apache-2.0, no
  carve-out** (envoyproxy / CNCF). Gateway-API-native, so it is continuous with
  the edge model ADR-003 already adopted (the chart's reference data plane is
  Envoy Gateway), and it delegates client identity to **JWT/OIDC** — which the
  stack already issues via Authelia.

## Decision

1. **Add an opt-in `envoyAIGateway` component (default `false`)** built on Envoy
   AI Gateway (Apache-2.0). It turns a pre-existing Gateway into one in-cluster
   OpenAI-compatible endpoint; model consumers target that endpoint instead of a
   provider URL. Local Ollama and the external providers sit behind it as
   `AIServiceBackend`s; upstream provider credentials live in one place via
   `BackendSecurityPolicy` (chart-managed Secret or `existingSecret`).

2. **It is the governed alternative to `externalAPIs`, and the two are mutually
   exclusive.** With the gateway on, external providers are configured **once on
   the gateway** (`envoyAIGateway.providers`) rather than per Open WebUI;
   `externalAPIs` is retained as the lightweight, implementation-agnostic,
   Open WebUI-only path for deployments that do not run Envoy Gateway. Enabling
   both is a **fail-fast template error** (one egress path, one audit story). No
   behaviour changes for existing deployments that use neither.

3. **CR-only: BYO control + data plane (mirrors ADR-003).** The chart emits only
   the AI Gateway custom resources (`AIGatewayRoute` / `AIServiceBackend` /
   `BackendSecurityPolicy` + the Envoy Gateway `Backend`, and optional
   `BackendTrafficPolicy` / `SecurityPolicy`) attached to a **pre-existing**
   Gateway — exactly as ADR-003 emits `HTTPRoute` without provisioning the
   Gateway. It does **not** install the Envoy AI Gateway controller, the Envoy
   Gateway data plane, or the CRDs; those are assumed present. CRDs are
   `aigateway.envoyproxy.io/v1beta1` (pinned against Envoy AI Gateway v0.7.0).

4. **Bundling the controller was evaluated and rejected.** Vendoring the Envoy AI
   Gateway *controller* as an in-chart Deployment would require a cluster-scoped
   `ClusterRole`, a token-mounted ServiceAccount, and (per upstream's chart) a
   controller Service/webhook — a documented exception to the chart's
   non-negotiable least-privilege / no-token-automount baseline (AGENTS.md §2.4)
   and a cluster-privileged workload, fragile to keep in lockstep with upstream's
   two Helm charts. The CR-only model keeps the security baseline fully intact.
   The controller + extproc **images are still mirrored** for air-gap (see §6).

5. **Identity reuses Authelia; no paid SSO.** Client auth is an Envoy
   `SecurityPolicy` (JWT/OIDC) wired to Authelia when `authelia.enabled`; quotas
   use Envoy AI Gateway **token/usage-based rate limiting** (`BackendTrafficPolicy`
   + `LLMRequestCosts`). Per-team RBAC, dollar budgets, and retained audit logs
   are composed from Envoy policy + the IdP + access logs / OTel — they are
   **not** a turnkey admin UI (see trade-offs).

6. **Secure-by-default, no weakened defaults.** CR-only means **no pod** in the
   release namespace, hence **no ServiceAccount and no per-pod NetworkPolicy** —
   governance metadata (tier `T1` / boundary `model-serving` / control-refs
   `CTL-002,POL-001`) lives on the **CR objects only**, exactly as the CNPG
   `Cluster`/`Pooler` carry it. Provider keys are stored in chart-managed (or
   existing) Secrets, never in rendered manifests. The two upstream images
   (`ai-gateway-controller`, `ai-gateway-extproc`, v0.7.0, **Apache-2.0**) are
   **digest-pinned** and catalogued as **two rows** in `sbom.cdx.json`,
   `zarf.yaml`, and `LICENSE_COMPLIANCE.md` so Zarf mirrors them for air-gap; the
   platform installs the upstream controller chart against the mirror.
   `tests/envoy_ai_gateway_test.yaml` asserts the apiVersions, routing, governance
   metadata, the no-plaintext-secret invariant, and the render guards (ADR-005
   discipline).

   *Resolved open question:* a centralized egress audit point does **not** mint a
   new control for now — the component reuses `CTL-002` (network-boundary
   governance) and `POL-001`; `CTL-001` observability stays implemented by the
   OTel Collector. A dedicated egress-audit control can be added later if the
   audit pipeline is built out.

## Consequences

**Positive**

- **Two clean `Apache-2.0` SBOM rows, no open-core carve-out** — preserves the
  sovereign / permissive-OSS / air-gappable identity (consistent with ADR-004);
  nothing proprietary is redistributed in the chart or Zarf package.
- **A single, auditable model-egress boundary** for every consumer, not just Open
  WebUI: provider keys centralized, token/usage rate limiting at the chokepoint,
  OTel-friendly access logging.
- **No new attack surface in the chart.** CR-only adds no privileged workload, no
  cluster RBAC, no token automount — the strongest reason to prefer it over
  bundling the controller.
- **Continuous with existing decisions** — Gateway-API-native (ADR-003) and
  identity via Authelia, so OIDC/RBAC needs no vendor license.

**Negative / accepted trade-offs**

- **BYO controller + data plane.** The platform must install Envoy Gateway, the
  AI Gateway controller, and the CRDs out of band (the chart only ships the
  config + mirrored images). This is the same BYO posture ADR-003 already accepts
  for the Gateway API implementation.
- **Younger project, primitives not a product.** Envoy AI Gateway is v0.7.0
  (Jun 2026, CRDs at `v1beta1`); dollar-budgets / per-team RBAC / retained audit
  logs are *assembled*, not toggled — the same "reference to extend, not turnkey
  platform" trade-off ADR-004 accepted for `pydanticai`. CI `kubeconform` skips
  the AI Gateway CRD kinds (as ADR-003 did for `HTTPRoute`/`Gateway`).
- **No built-in PII redaction.** LiteLLM ships free Presidio masking at the
  proxy; Envoy AI Gateway does not. PII/secret redaction stays with the existing
  OTel pipeline (`CTL-001`) until an `ext_proc` guardrail is added (future work).
  *If proxy-level PII masking becomes a hard requirement, the LiteLLM trade-off is
  revisited.*

**Alternatives considered**

- **LiteLLM** — rejected on redistribution / open-core grounds (above); revisit
  only if free Presidio PII masking outweighs shipping the proprietary carve-out.
- **Bundling the Envoy AI Gateway controller in-chart** — rejected (Decision §4):
  cluster RBAC + token automount + webhook would weaken the security baseline.
- **Status quo (`externalAPIs` only)** — leaves the agentic runtimes with no
  governed external-model path and keeps credentials scattered.

## Artifacts (this change)

- `values.yaml` `envoyAIGateway:` block + `externalAPIs` mutual-exclusion guard;
  `values.schema.json`.
- `templates/envoy-ai-gateway/aigateway.yaml` (`AIGatewayRoute` /
  `AIServiceBackend` / `BackendSecurityPolicy` / `Backend` / `BackendTrafficPolicy`
  / `SecurityPolicy`); the provider Secret in `templates/common/secrets.yaml`;
  the `envoy-ai-gateway` entry in `ai-stack.governanceMap` (`templates/_helpers.tpl`).
- `sbom.cdx.json` + `zarf.yaml` (two digest-pinned Apache-2.0 images);
  `docs/compliance/LICENSE_COMPLIANCE.md` rows.
- `tests/envoy_ai_gateway_test.yaml`; `tests/governance_labels_test.yaml`
  (CR governance assertion); `docs/components/envoy-ai-gateway.md`;
  `docs/governance/CONTROLS.md` *Implemented By* for `CTL-002` / `POL-001`.
- `.github/workflows/lint.yaml` — `kubeconform` skip for the AI Gateway CRD kinds.
