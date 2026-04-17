# Workbench

GPU-enabled JupyterLab environment for model experimentation, evaluation, and ad-hoc ML work. Talks to the same Ollama, Qdrant, Tika, and SearXNG services as Open WebUI.

- **Tier**: T1 (operational)
- **Boundary**: `decision`
- **Default**: opt-in (`workbench.enabled=false`)
- **Upstream**: <https://jupyter-docker-stacks.readthedocs.io/>
- **Default image**: `quay.io/jupyter/pytorch-notebook` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/workbench/`](../../templates/workbench/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `workbench.enabled` | Toggle the component |
| `workbench.image.{repository,tag}` | Container image override |
| `workbench.token` | Jupyter token; otherwise auto-generated into `workbench-secret` |
| `workbench.gpu.{enabled,count,resourceName}` | GPU scheduling |
| `workbench.persistence.{enabled,size,storageClass}` | Notebook/home PVC |
| `workbench.resources` | CPU / memory / GPU limits |
| `workbench.ingress.*` | Ingress / Gateway API configuration |

## Security considerations

- Workbench gives users an interactive shell — scope access carefully and pair with Authelia MFA
- Jupyter token stored in `workbench-secret`; rotate periodically
- NetworkPolicy restricts egress to in-cluster services and allowed external endpoints only

## Related HOWTO sections

- [§7.2 Enable the GPU Workbench](../../HOWTO.md#72-enable-the-gpu-workbench)
