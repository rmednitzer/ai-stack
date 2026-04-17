# Valkey

In-memory key/value store used for session caching (Open WebUI, Authelia) and as the Stream backend for the ingestion worker. BSD-licensed fork of Redis.

- **Tier**: T2 (productivity)
- **Boundary**: `internal`
- **Default**: enabled
- **Upstream**: <https://valkey.io/>
- **Default image**: `valkey/valkey` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/valkey/`](../../templates/valkey/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `valkey.enabled` | Toggle the component |
| `valkey.image.{repository,tag}` | Container image override |
| `valkey.persistence.{enabled,size,storageClass}` | Enable to preserve Streams across restarts |
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
