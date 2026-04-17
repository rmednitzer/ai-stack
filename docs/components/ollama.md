# Ollama

Local large-language-model inference engine. Serves an OpenAI-compatible HTTP API consumed by Open WebUI, LangGraph, and the ingestion worker.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Default**: enabled
- **Upstream**: <https://ollama.com/> · [docs](https://github.com/ollama/ollama/tree/main/docs)
- **Default image**: `ollama/ollama` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/ollama/`](../../templates/ollama/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `ollama.enabled` | Toggle the component |
| `ollama.image.{repository,tag}` | Container image override |
| `ollama.gpu.{enabled,count,resourceName}` | GPU scheduling (e.g. `nvidia.com/gpu`) |
| `ollama.persistence.{enabled,size,storageClass}` | Model-cache PVC — typically 100 GB+ |
| `ollama.resources` | CPU / memory; memory must be ≥ model size |
| `ollama.env.OLLAMA_KEEP_ALIVE` | Time to keep idle models resident |
| `ollama.env.OLLAMA_NUM_PARALLEL` | Concurrent requests per model |

## GPU notes

GPU acceleration requires the NVIDIA GPU Operator (or equivalent) on the cluster. The Ollama pod has a documented root-exception annotation for device access (`assurance.platform/security-exception`); see [§19.8 GPU Not Detected](../../HOWTO.md#198-gpu-not-detected).

## Pulling models

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull llama3.2
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull nomic-embed-text
```

## Related HOWTO sections

- [§3 Working with Models](../../HOWTO.md#3-working-with-models)
- [§7 GPU Acceleration](../../HOWTO.md#7-gpu-acceleration)
- [§19.2 Ollama Out of Memory](../../HOWTO.md#192-ollama-out-of-memory)
