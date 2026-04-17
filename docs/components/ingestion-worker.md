# Ingestion Worker

Async document-ingestion worker. Consumes tasks from a Valkey Stream (`ingestion:documents`) and orchestrates the pipeline: Tika extract → chunk → Ollama embed → Qdrant upsert. Lets users upload documents without blocking the UI.

- **Tier**: T2 (productivity)
- **Boundary**: `internal`
- **Default**: opt-in (`ingestionWorker.enabled=false`)
- **Upstream**: in-chart Python worker (see `templates/ingestion-worker/`)
- **Default image**: `python` slim base, with the worker script mounted from a ConfigMap
- **Chart path**: [`templates/ingestion-worker/`](../../templates/ingestion-worker/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `ingestionWorker.enabled` | Toggle the component |
| `ingestionWorker.image.{repository,tag}` | Base Python image |
| `ingestionWorker.replicaCount` | Number of worker pods |
| `ingestionWorker.chunkSize`, `ingestionWorker.chunkOverlap` | Text splitter parameters |
| `ingestionWorker.embedModel` | Ollama embedding model (e.g. `nomic-embed-text`) |
| `ingestionWorker.qdrantCollection` | Target Qdrant collection |
| `ingestionWorker.resources` | CPU / memory |

## Dependencies

- `valkey.enabled: true` and — strongly recommended — `valkey.persistence.enabled: true` so in-flight tasks survive restarts
- `tika.enabled: true`
- `ollama.enabled: true` with the selected embedding model pulled
- `qdrant.enabled: true`

## Enqueue API

```
XADD ingestion:documents * task_id <id> file_url <url> filename <name>
```

Status is written to `HSET ingestion:status:<task_id>` (`state`, `chunks`, `error`).

## Related HOWTO sections

- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
