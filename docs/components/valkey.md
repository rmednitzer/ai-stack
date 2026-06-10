# Valkey

In-memory key/value store used for session caching (Open WebUI, Authelia) and as the Stream backend for the ingestion worker. BSD-licensed fork of Redis.

- **Tier**: T2 (productivity)
- **Boundary**: `storage`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: enabled
- **Upstream**: <https://valkey.io/>
- **Default image**: `valkey/valkey` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/common/valkey.yaml`](../../templates/common/valkey.yaml)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `valkey.enabled` | Toggle the component |
| `valkey.image.{repository,tag}` | Container image override |
| `valkey.auth.{enabled,password}` | Opt-in AUTH (`requirepass`, [ADR-008](../architecture/ADR-008-valkey-auth.md)). Password auto-generated (stable across upgrades) unless overridden; overrides must be URL-safe (embedded in `redis://` URLs). |
| `valkey.persistence.{enabled,size,accessMode}` | Provision a PVC (RDB snapshots under `/data`) to preserve Streams across restarts; switches the Deployment to the `Recreate` strategy. Storage class comes from `global.storageClass`. |
| `valkey.resources` | CPU / memory |

## Persistence recommendation

When the ingestion worker is enabled, set `valkey.persistence.enabled=true` — otherwise in-flight ingestion tasks are lost on pod restart.

## Security

- Read-only root filesystem enforced
- No external exposure; `ClusterIP` only
- Default access control is the default-deny NetworkPolicy + per-pod ingress
  allowlist (Open WebUI, SearXNG, ingestion worker, Authelia, helm test)
- **Opt-in AUTH** (`valkey.auth.enabled`, [ADR-008](../architecture/ADR-008-valkey-auth.md)):
  `requirepass` is read from a Secret-mounted config file (never process
  args); probes authenticate via `VALKEYCLI_AUTH`/`REDISCLI_AUTH`; consumer
  URLs (Open WebUI, ingestion worker, Authelia session store, helm test)
  embed the password via `$(...)` env substitution. Enabling/disabling is a
  coordinated rollout of Valkey + consumers; rotation is manual
  (`kubectl rollout restart`). The chart's SearXNG config does not use
  Valkey — if you wire it yourself (e.g. the limiter), add the password to
  your settings override.

## Related HOWTO sections

- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
- [§12 Authelia SSO/OIDC](../../HOWTO.md#12-authentication-with-authelia-sso--oidc)
