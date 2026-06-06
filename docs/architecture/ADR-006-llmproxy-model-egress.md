# ADR-006 — Apache-2.0 LLM gateway (`llmproxy`) for governed model egress

- **Status:** Proposed
- **Date:** 2026-06-06
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** _pending — drafted against 2.8.0_
- **Supersedes:** none (subsumes the `externalAPIs` egress path when enabled; see Decision §2)

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

## Decision (proposed)

1. **Add an opt-in `llmproxy` component (default `false`)** built on Envoy AI
   Gateway (Apache-2.0). It exposes one in-cluster OpenAI-compatible endpoint;
   every model consumer (`openwebui`, `pydanticai`, `langgraph`,
   `ingestionWorker`) targets it instead of a provider URL. Local Ollama and the
   external providers sit behind the same endpoint as `AIServiceBackend`s;
   upstream provider credentials live in one place via `BackendSecurityPolicy`
   (chart-managed Secret or `existingSecret`).

2. **`llmproxy` subsumes `externalAPIs` when enabled, and the two are mutually
   exclusive.** With the proxy on, external providers are configured **once on the
   proxy** and Open WebUI points at it (not at per-provider base URLs).
   `externalAPIs` is retained as the lightweight, implementation-agnostic,
   Open WebUI-only path for deployments that do not run Envoy Gateway; enabling
   both is a **fail-fast template error** (one egress path, one audit story). No
   behaviour changes for existing deployments that use neither.

3. **Gateway-API-native, BYO data plane (mirrors ADR-003).** The chart emits the
   Envoy AI Gateway CRs (`AIGatewayRoute` / `AIServiceBackend` /
   `BackendSecurityPolicy`) attached to a **pre-existing** Gateway; it does
   **not** provision Envoy Gateway, its `GatewayClass`, or the CRDs — exactly as
   ADR-003 emits `HTTPRoute` without provisioning the Gateway. Exact CRD
   `apiVersion`s are pinned at implementation against the targeted release (the
   core CRDs reached `v1beta1` in Envoy AI Gateway v0.6.0).

4. **Identity reuses Authelia; no paid SSO.** Client auth is an Envoy
   `SecurityPolicy` (JWT/OIDC) wired to Authelia when `authelia.enabled`; quotas
   use Envoy AI Gateway **token/usage-based rate limiting**. Per-team RBAC, dollar
   budgets, and retained audit logs are composed from Envoy policy + the IdP +
   access logs / OTel — they are **not** a turnkey admin UI (see trade-offs).

5. **Secure-by-default wiring, no weakened defaults.** Dedicated ServiceAccount
   (no token automount), `restrictedSecurityContext`, default-deny NetworkPolicy
   (ingress only from model consumers; egress `443` to the configured external
   providers and `11434` to in-cluster Ollama), governance metadata **tier `T1` / boundary `model-serving`
   / control-refs `CTL-002,POL-001`** (existing vocabulary — no new boundary).
   The new image is **digest-pinned** and catalogued as a **single `Apache-2.0`
   row** in `sbom.cdx.json`, `zarf.yaml`, `values.schema.json`, and
   `LICENSE_COMPLIANCE.md`; a `tests/llmproxy_test.yaml` asserts the security
   posture (ADR-005 discipline).

   *Open question for acceptance:* whether a centralized egress audit point
   warrants a **new control** in `docs/governance/CONTROLS.md` (vs. reusing
   `CTL-001` observability, whose implementer stays the OTel Collector). Flagged
   rather than assumed.

## Consequences

**Positive**

- **One clean `Apache-2.0` SBOM row, no open-core carve-out** — preserves the
  sovereign / permissive-OSS / air-gappable identity (consistent with ADR-004);
  nothing proprietary is redistributed in the chart or Zarf package.
- **A single, auditable model-egress boundary for *all* consumers** (not just
  Open WebUI): provider keys centralized in one Secret, token/usage rate limiting
  at the chokepoint, OTel-friendly access logging.
- **Continuous with existing decisions** — Gateway-API-native (ADR-003) and
  identity via Authelia, so OIDC/RBAC needs no vendor license.

**Negative / accepted trade-offs**

- **Younger project, primitives not a product.** Envoy AI Gateway is v0.6.0
  (May 2026, CRDs at `v1beta1`); dollar-budgets / per-team RBAC / retained audit
  logs are *assembled*, not toggled — the same "reference to extend, not turnkey
  platform" trade-off ADR-004 accepted for `pydanticai`.
- **Hard dependency on Envoy Gateway + AI Gateway CRDs.** Clusters on a different
  Gateway API implementation cannot enable `llmproxy` — which is exactly why
  `externalAPIs` is retained as the implementation-agnostic fallback. CI
  `kubeconform` gains the AI Gateway CRD kinds in its skip list (as ADR-003 did
  for `HTTPRoute`/`Gateway`).
- **No built-in PII redaction.** LiteLLM ships free Presidio masking at the
  proxy; Envoy AI Gateway does not. PII/secret redaction stays with the existing
  OTel pipeline (`CTL-001`) until an `ext_proc` guardrail is added (future work).
  *If proxy-level PII masking becomes a hard requirement, the LiteLLM trade-off is
  revisited.*

**Alternatives considered**

- **LiteLLM** — rejected on redistribution / open-core grounds (above); revisit
  only if free Presidio PII masking outweighs shipping the proprietary carve-out.
- **Status quo (`externalAPIs` only)** — leaves the agentic runtimes with no
  governed external-model path and keeps credentials scattered.

## Related artifacts (to be created at implementation — none touched by this ADR)

- `values.yaml` `llmproxy:` block + `externalAPIs` mutual-exclusion guard;
  `values.schema.json`.
- `templates/llmproxy/*` (`AIGatewayRoute` / `AIServiceBackend` /
  `BackendSecurityPolicy` / Envoy `SecurityPolicy`), `templates/common/*`
  (SA / Secret / NetworkPolicy).
- `sbom.cdx.json` (Apache-2.0 row), `zarf.yaml` (image + CRD manifests),
  `LICENSE_COMPLIANCE.md` row.
- `tests/llmproxy_test.yaml`; `docs/components/llmproxy.md`;
  `docs/architecture/REFERENCE.md` (egress flow); `docs/governance/CONTROLS.md`
  *Implemented By* for `CTL-002` / `POL-001`.
- `.github/workflows/lint.yaml` — `kubeconform` skip for Envoy AI Gateway CRD
  kinds.
