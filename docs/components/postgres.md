# PostgreSQL

Relational database backing **Open WebUI's high-availability state**, LangGraph / Pydantic AI checkpoints, and (optionally) Authelia session storage. The chart supports three provisioning modes so you can stay in a single Helm release from lab to HA production to external managed services.

- **Tier**: T2 (productivity)
- **Boundary**: `storage`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: enabled (`postgres.enabled=true`). Set `false` for an ephemeral single-pod lab — Open WebUI then falls back to local SQLite.
- **Upstream**: <https://www.postgresql.org/> · [CloudNativePG](https://cloudnative-pg.io/)
- **Default image**: `docker.io/library/postgres` (standalone) / `ghcr.io/cloudnative-pg/postgresql` (cnpg operand, `postgres.cnpg.image.{repository,tag}`) — see `values.yaml` for pinned tags
- **Chart path**: [`templates/postgres/`](../../templates/postgres/)

## Modes

| Mode | When to use | HA | Managed by |
|------|-------------|----|------------|
| `standalone` | Lab / dev | No | Helm chart |
| `cnpg` | Production — CloudNativePG operator | Yes (3 instances, streaming replication, failover) | CNPG operator ≥ 1.25 |
| `external` | Bring-your-own RDS, Cloud SQL, etc. | Provider-dependent | External |

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `postgres.enabled` | Toggle the component (default `true`) |
| `postgres.mode` | `standalone` / `cnpg` / `external` |
| `postgres.database`, `postgres.user` | Default DB (LangGraph / DBOS) and role; Open WebUI uses its own `openwebui.databaseName` |
| `postgres.password` | Explicit password; otherwise auto-generated into `postgres-secret` |
| `postgres.tls.mode` | `disable`, `prefer`, `require` |
| `postgres.cnpg.instances` | CNPG replica count (default 3) |
| `postgres.cnpg.pooler.enabled` | PgBouncer connection pooling |
| `postgres.external.host`, `postgres.external.port` | External endpoint |
| `postgres.external.existingSecret.{name,key}` | Reference an existing secret for the password |

## Backups (CNPG)

CNPG supports automated Barman-based backups to S3-compatible storage. Configure via `postgres.cnpg.backup.*` — see [HOWTO §10.2 CloudNativePG](../../HOWTO.md#102-cloudnativepg-production-ha).

## Related HOWTO sections

- [§10 PostgreSQL Modes](../../HOWTO.md#10-postgresql-modes)
- [§8 Agentic Workloads (LangGraph / Pydantic AI)](../../HOWTO.md#8-agentic-workloads-langgraph-or-pydantic-ai)
- [§12.4 Authelia with PostgreSQL](../../HOWTO.md#124-use-postgresql-as-storage-backend)
