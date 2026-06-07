# AI Gateway

Governed, in-cluster OpenAI-compatible **model-egress gateway** (ADR-006), **implemented by [Envoy AI Gateway](https://aigateway.envoyproxy.io/)**. Turns a pre-existing Gateway into one endpoint that fronts local Ollama and external providers, centralizing provider credentials, routing, optional token-based rate limiting, and JWT/OIDC client auth. **Apache-2.0**, no open-core carve-out.

The component is named for its **role** (`aiGateway`), not the implementation, so the gateway behind it can evolve without a breaking values rename — see the [component-naming standard](../../AGENTS.md#component-naming).

- **Tier**: T1 (operational)
- **Boundary**: `model-serving`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: opt-in (`aiGateway.enabled=false`)
- **Implementation**: Envoy AI Gateway · <https://aigateway.envoyproxy.io/> · [docs](https://aigateway.envoyproxy.io/docs/)
- **Mirrored images**: `docker.io/envoyproxy/ai-gateway-controller`, `docker.io/envoyproxy/ai-gateway-extproc` (see `values.yaml` for pinned tags)
- **Chart path**: [`templates/ai-gateway/`](../../templates/ai-gateway/)

## Runtime model — CR-only, BYO controller

This component is **configuration, not a workload**. The chart emits only the AI Gateway custom resources (`AIGatewayRoute`, `AIServiceBackend`, `BackendSecurityPolicy`, the Envoy Gateway `Backend`, and optional `BackendTrafficPolicy` / `SecurityPolicy`) and attaches them to a **pre-existing Gateway** — exactly as the opt-in `HTTPRoute` (ADR-003) attaches to a Gateway it does not provision.

It does **not** install the Envoy AI Gateway controller, the Envoy Gateway data plane, or the CRDs. Install those out of band (the upstream `ai-gateway-crds-helm` + `ai-gateway-helm` charts); the controller + extproc images are mirrored into the Zarf package so an air-gapped platform can install them from the local registry.

Because there is no pod in the release namespace, there is **no ServiceAccount and no per-pod NetworkPolicy** — governance metadata lives on the CR objects, like the CloudNativePG `Cluster`/`Pooler`.

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `aiGateway.enabled` | Toggle the component (mutually exclusive with `externalAPIs`) |
| `aiGateway.parentRefs` | The pre-existing Gateway(s) the `AIGatewayRoute` attaches to (required when enabled) |
| `aiGateway.includeOllama` / `ollamaModel` | Route the in-cluster Ollama backend, reached by the configured model id |
| `aiGateway.providers[]` | External providers (`name`, `schema`, `hostname`, `model`, `apiKey`/`existingSecret`) |
| `aiGateway.rateLimit.*` | Token-based rate limiting (`BackendTrafficPolicy` + `LLMRequestCosts`) |
| `aiGateway.clientAuth.*` | JWT/OIDC client auth (`SecurityPolicy`; defaults to the Authelia issuer when `authelia.enabled`) |

## Secrets

Each provider's upstream API key is stored in a chart-managed `*-ai-gateway-<name>-secret` Secret under data key `apiKey` (`helm.sh/resource-policy: keep`). To bring your own, set `existingSecret.name` — the referenced Secret must expose the key under `apiKey` (Envoy AI Gateway's `BackendSecurityPolicy` reads only the Secret name, with a fixed data key). Keys are never written into a rendered manifest.

## Security notes

- **No privileged workload added.** CR-only: no pod, no token-mounted ServiceAccount, no cluster RBAC. Bundling the controller in-chart was evaluated and rejected (ADR-006 §4) precisely because it would require those.
- **Mutually exclusive with `externalAPIs`** — one governed egress path, one audit story; enabling both is a render-time error.
- The data-plane enforcement (rate limits, auth, routing) runs in the BYO Envoy Gateway, not in this namespace.

## Related

- [ADR-006 — Envoy AI Gateway for governed model egress](../architecture/ADR-006-envoy-ai-gateway-model-egress.md)
- [License compliance](../compliance/LICENSE_COMPLIANCE.md)
