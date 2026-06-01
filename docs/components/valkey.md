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
| `valkey.persistence.{enabled,size,accessMode}` | Provision a PVC (RDB snapshots under `/data`) to preserve Streams across restarts; switches the Deployment to the `Recreate` strategy. Storage class comes from `global.storageClass`. |
| `valkey.resources` | CPU / memory |
| `valkey.config` | Extra config passed to `valkey-server` |

## Persistence recommendation

When the ingestion worker is enabled, set `valkey.persistence.enabled=true` — otherwise in-flight ingestion tasks are lost on pod restart.

## Security

- Read-only root filesystem enforced
- No external exposure; `ClusterIP` only
- Auth via `requirepass` (auto-generated when unset)

## Related HOWTO sections

- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
- [§12 Authelia SSO/OIDC](../../HOWTO.md#12-authentication-with-authelia-sso--oidc)
