# Ingestion Worker

Async document-ingestion worker. Consumes tasks from a Valkey Stream
(`ingestion:documents`) and orchestrates the pipeline: Tika extract → chunk →
Ollama embed → Qdrant upsert. Lets users upload documents without blocking the UI,
and (optionally) tracks a per-collection corpus lifecycle in PostgreSQL.

- **Tier**: T2 (productivity)
- **Boundary**: `ingestion`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: opt-in (`ingestionWorker.enabled=false`)
- **Upstream**: in-chart Python worker — source in [`files/ingestion-worker/worker.py`](../../files/ingestion-worker/worker.py), loaded into a ConfigMap via `.Files.Get`
- **Default image**: `python` slim base; dependencies installed at startup, or bake a prebuilt image via [`files/ingestion-worker/Dockerfile`](../../files/ingestion-worker/Dockerfile) and set `buildDeps: false`
- **Chart path**: [`templates/ingestion-worker/`](../../templates/ingestion-worker/)

> **Full contract:** the task/status protocols, delivery & retry semantics, the
> corpus state machine, and the complete env reference are specified in
> **[ingestion-worker-spec.md](ingestion-worker-spec.md)**. This page is the
> overview.

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `ingestionWorker.enabled` | Toggle the component |
| `ingestionWorker.image.{repository,tag}` | Base Python image (or a prebuilt worker image) |
| `ingestionWorker.buildDeps` | `true` (default): install deps at startup via an initContainer. `false`: deps are baked into the image (air-gapped) |
| `ingestionWorker.replicaCount` | Number of worker pods (all join one consumer group) |
| `ingestionWorker.autoscaling.*` | Optional HPA (CPU/memory targets) |
| `ingestionWorker.resources` | CPU / memory requests + limits |
| `ingestionWorker.env.RAG_CHUNK_SIZE`, `…RAG_CHUNK_OVERLAP` | Text-splitter parameters |
| `ingestionWorker.env.RAG_EMBEDDING_MODEL` | Ollama embedding model (e.g. `nomic-embed-text`) |
| `ingestionWorker.env.QDRANT_COLLECTION` | Default target Qdrant collection |
| `ingestionWorker.env.INGESTION_*` | Stream/group/status/batch/retry tuning ([spec §6](ingestion-worker-spec.md#6-configuration-reference)) |
| `ingestionWorker.sources.*` | **Opt-in** native object-store / network-share connectors via fsspec (`s3://`, `gs://`, `az://`, `smb://`, …) — see [ADR-007](../architecture/ADR-007-ingestion-source-connectors.md) |
| `ingestionWorker.fetch.{schemes,allowedCidrs}` | URL-fetch SSRF screen for producer-supplied `file_url` tasks: https-only by default; private ranges need an explicit CIDR grant — see [ADR-009](../architecture/ADR-009-ingestion-url-fetch-hardening.md) |

> Pipeline behaviour is configured through `ingestionWorker.env.*` (passed
> straight to the worker), **not** top-level keys. `VALKEY_URL`, `QDRANT_API_KEY`,
> and `POSTGRES_URI` are injected automatically by the deployment.

## Dependencies

- `valkey.enabled: true` and — strongly recommended — `valkey.persistence.enabled: true` so in-flight tasks survive restarts
- `tika.enabled: true`
- `ollama.enabled: true` with the selected embedding model pulled
- `qdrant.enabled: true`
- `postgres.enabled: true` — **optional**, enables the corpus lifecycle state machine ([spec §5](ingestion-worker-spec.md#5-corpus-lifecycle-state-machine))

## Enqueue & status (summary)

Enqueue a task on the stream (`task_id`, `file_url` required-ish; `filename`,
`collection` optional):

```
XADD ingestion:documents * task_id <id> file_url <url> filename <name> collection <coll>
```

Track it via the status hash `ingestion:status:<task_id>` (`status`, `updated_at`,
`filename`, `chunk_count`, `error`), whose `status` advances:

```
processing → extracting → chunking → embedding → upserting → done   (| failed)
```

See the [spec](ingestion-worker-spec.md) for field types, defaults, retry/ack
semantics, and the `corpus:state` pub/sub event schema.

## Related HOWTO sections

- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
