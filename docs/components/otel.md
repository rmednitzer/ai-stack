# OpenTelemetry Collector

Centralises logs, metrics, and traces from every ai-stack component, enriches them with GenAI semantic conventions, and redacts PII before forwarding to the observability backend. Gated by `global.otel.enabled`.

- **Tier**: T0 (safety / integrity)
- **Boundary**: `observability`
- **Control refs**: [CTL-001](../governance/CONTROLS.md#controls-ctl), [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: deployed when `global.otel.enabled=true`
- **Upstream**: <https://opentelemetry.io/docs/collector/> · [Contrib distro](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- **Default image**: `otel/opentelemetry-collector-contrib` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/otel/`](../../templates/otel/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `global.otel.enabled` | Deploy the Collector and inject `OTEL_*` env vars into all pods |
| `global.otel.endpoint` | OTLP endpoint (typically cluster-local) |
| `global.otel.exportNamespace` | Namespace of the platform observability pipeline (default `observability`); scopes the Collector's NetworkPolicy export egress — keep in sync with `endpoint` |
| `global.otel.sampler` | `always_on`, `parentbased_traceidratio`, etc. |
| `global.serviceMonitor.enabled` | Emit Prometheus Operator `ServiceMonitor` resources |
| `otel.image.{repository,tag}` | Container image override |
| `otel.config` | Extra Collector pipelines |

## PII redaction

The Collector runs a `redaction` processor (patterns configurable via `otelCollector.redaction.blockedPatterns`) that masks, before export, both **PII** (email, social-security/VSNR, and credit-card patterns) **and credential shapes** that ride along in MCPO / Open Terminal tool traffic — bearer tokens, JWTs, PEM private-key blocks, and OpenAI / AWS / GitHub / GitLab / Google / Slack / Stripe API-key patterns. Implements GDPR Art. 5(1)(c) data minimisation (see [CTL-001](../governance/CONTROLS.md#controls-ctl)). The redaction processor is wired ahead of every exporter in all three pipelines (traces, metrics, logs), so even the lab-only `debug` exporter receives already-redacted data. Resource enrichment uses the `resource_detection` and `resource` processors.

## Network posture

The Collector accepts OTLP only from `part-of: ai-stack` pods and Prometheus
scrapes only from `global.monitoringNamespace`. Its **export egress is
namespace-scoped** (since 2.12.0): OTLP/Loki/remote-write ports are reachable
only in `global.otel.exportNamespace` and `global.monitoringNamespace` — set
`exportNamespace` if your pipeline lives in another namespace. An
**off-cluster** export endpoint cannot be matched by namespace selectors: add
your own additive NetworkPolicy with an `ipBlock` egress for the collector
pods.

## Related HOWTO sections

- [§14 Observability](../../HOWTO.md#14-observability)
