# Qdrant

Vector database backing RAG retrieval for Open WebUI, LangGraph, and the ingestion worker.

- **Tier**: T1 (operational)
- **Boundary**: `retrieval`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
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
| `qdrant.cluster.enabled` | Opt-in distributed high availability (StatefulSet); default `false` |
| `qdrant.cluster.replicas` | Peer count (odd, >= 3 for a quorum); default `3` |
| `qdrant.cluster.replicationFactor` | Shard replicas per collection (>= 2 for data HA); default `2` |
| `qdrant.cluster.shardNumber` | Shards per collection; empty = Qdrant default (1) |
| `qdrant.cluster.p2pPort` | Raft consensus (p2p) port; default `6335`, intra-Qdrant only |

## High availability (distributed mode)

Off by default: the chart renders a single-node `Deployment` with one
`ReadWriteOnce` PVC. Set `qdrant.cluster.enabled: true` to switch to a
`StatefulSet` of `cluster.replicas` peers running Raft consensus over the p2p
port, behind a headless `Service` (`clusterIP: None`,
`publishNotReadyAddresses: true`) for peer discovery, with per-pod PVCs
(`volumeClaimTemplates`). Bootstrap follows Qdrant's documented model: pod-0
forms the cluster, the rest join via pod-0. See
[ADR-013](../architecture/ADR-013-distributed-qdrant-ha.md) and
[runbook A7](../operations/RUNBOOK-remediation.md).

Two conditions are needed to actually survive a node loss:

1. **Spread:** peers on distinct nodes. The default pod anti-affinity is *soft*
   (so cluster mode still schedules on a small cluster); for guaranteed HA, pin
   nodes or harden it to a required rule / topology spread.
2. **Replicated collections:** `replication_factor >= 2`, which is a per-collection
   property set at *creation* time. The ingestion worker applies
   `cluster.replicationFactor` / `cluster.shardNumber` automatically when cluster
   mode is on. Collections created elsewhere (Open WebUI manages its own) must set
   their own replication at creation.

The client `Service` name (`<release>-qdrant`) is unchanged across the switch, so
consumers' `QDRANT_URI` needs no edit. The p2p port is confined to qdrant peers by
the NetworkPolicy and never exposed on the client Service.

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
