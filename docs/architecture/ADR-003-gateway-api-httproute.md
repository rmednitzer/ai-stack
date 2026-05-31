# ADR-003 — Opt-in Gateway API (HTTPRoute) for edge routing

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.3.0
- **Supersedes:** none

---

## Context

The chart targets [Envoy Gateway](https://gateway.envoyproxy.io/) as its
reference edge (`global.ingressNamespace: envoy-gateway-system`, and the
production `openwebui.ingress.className: envoy`), yet it only emitted the legacy
`networking.k8s.io/v1` **Ingress** resource for externally-exposed components.

The Kubernetes **Gateway API** reached GA (`v1.0`) in 2023; `HTTPRoute`,
`Gateway`, and `GatewayClass` are Stable at `gateway.networking.k8s.io/v1`, and
the project shipped `v1.5` in early 2026. Envoy Gateway is a Gateway API
implementation, so the chart's own reference edge is more idiomatically driven
by `HTTPRoute` than by `Ingress`.

## Decision

1. **Add an opt-in `HTTPRoute` (`gateway.networking.k8s.io/v1`) per
   externally-exposed component** — `openwebui`, `langgraph`,
   `pydanticai`, `authelia` — via a shared `ai-stack.httpRoute` helper, gated by
   a per-component `httpRoute.enabled` (default **false**).

2. **Additive, not a replacement.** The existing `Ingress` path is unchanged and
   both may be enabled simultaneously. Existing deployments are unaffected.

3. **The chart emits only the per-app `HTTPRoute`**, attached to a
   **pre-existing** `Gateway` via `parentRefs` — it does **not** provision the
   `Gateway`/`GatewayClass`. This mirrors the Ingress path, which relies on an
   externally-managed IngressClass/controller. `parentRefs[].namespace` defaults
   to `global.gateway.namespace`, falling back to `global.ingressNamespace`
   (where the Envoy Gateway data plane runs).

4. **No NetworkPolicy change required.** The per-component ingress policies
   already admit traffic from `global.ingressNamespace`, which is where the
   Gateway data plane terminates and forwards from — so HTTPRoute traffic is
   covered by the same allow rule as Ingress.

5. **Fail-fast validation.** Enabling `httpRoute` without a `parentRefs` entry is
   a template error; `values.schema.json` validates the `httpRoute`/`parentRefs`
   shape.

## Consequences

**Positive**

- Modern, Stable-channel edge routing that matches the chart's Envoy Gateway
  reference, including richer match/filter semantics than Ingress.
- Zero-risk adoption: default-off and additive; teams migrate per component.
- Rendered routes are validated against the upstream Gateway API v1 JSON schema.

**Negative / accepted trade-offs**

- `HTTPRoute`/`Gateway` are CRDs, so the cluster must have a Gateway API
  implementation installed. CI `kubeconform` skips these kinds (as it already
  does for `ServiceMonitor`/`PrometheusRule`); local validation uses the
  gateway-api schema.
- Two edge mechanisms now coexist; operators choose one per component.

**Operational**

- `kubeVersion` floor raised to `>=1.27` (also required by PDB
  `unhealthyPodEvictionPolicy`); Gateway API CRDs are version-independent but the
  feature set assumes a current implementation.

## Related artifacts

- `templates/_helpers.tpl` — `ai-stack.httpRoute` helper.
- `values.yaml` — `global.gateway` + per-component `httpRoute` blocks.
- `values.schema.json` — `httpRoute`/`parentRefs` validation.
- `.github/workflows/lint.yaml` — kubeconform `-skip` includes `HTTPRoute,Gateway`.
- README "Gateway API (HTTPRoute)".
