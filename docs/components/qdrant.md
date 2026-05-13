# Qdrant

Vector database backing RAG retrieval for Open WebUI, LangGraph, and the ingestion worker.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Default**: enabled
- **Upstream**: <https://qdrant.tech/> · [docs](https://qdrant.tech/documentation/)
- **Default image**: `qdrant/qdrant` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/qdrant/`](../../templates/qdrant/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `qdrant.enabled` | Toggle the component |
| `qdrant.image.{repository,tag}` | Container image override |
| `qdrant.apiKey` | Explicit API key; otherwise auto-generated into `qdrant-secret` |
| `qdrant.persistence.{enabled,size,storageClass}` | Collection-storage PVC |
| `qdrant.resources` | CPU / memory sized to collection cardinality |
| `qdrant.service.type` | `ClusterIP` by default; not exposed publicly |

## Security

- Read-only root filesystem enforced
- API-key auth on all endpoints; key surfaced to callers via `qdrant-secret`
- NetworkPolicy default-deny with allowlist for Open WebUI, LangGraph, ingestion worker

## Data-subject operations

Point-level deletion with metadata filters (used by DSAR purges):

```bash
kubectl exec -n ai-stack deploy/ai-stack-qdrant -- \
  curl -s -X POST http://localhost:6333/collections/documents/points/delete \
    -H "Content-Type: application/json" \
    -d '{"filter":{"must":[{"key":"user_id","match":{"value":"<uid>"}}]}}'
```

## Related HOWTO sections

- [§4 RAG](../../HOWTO.md#4-rag-retrieval-augmented-generation)
- [§5 Async Document Ingestion](../../HOWTO.md#5-async-document-ingestion)
