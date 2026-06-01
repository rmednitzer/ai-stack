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
| `global.otel.sampler` | `always_on`, `parentbased_traceidratio`, etc. |
| `global.serviceMonitor.enabled` | Emit Prometheus Operator `ServiceMonitor` resources |
| `otel.image.{repository,tag}` | Container image override |
| `otel.config` | Extra Collector pipelines |

## PII redaction

The Collector runs a `redaction` processor (patterns configurable via `otelCollector.redaction.blockedPatterns`) that masks email, social-security (VSNR), and credit-card patterns in log and trace attributes before export. Implements GDPR Art. 5(1)(c) data minimisation (see [CTL-001](../governance/CONTROLS.md#controls-ctl)). Resource enrichment uses the `resource_detection` and `resource` processors.

## Related HOWTO sections

- [§14 Observability](../../HOWTO.md#14-observability)
