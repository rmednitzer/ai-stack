# Open Terminal

Sandboxed terminal service for AI agents. Executes shell commands on behalf of Open WebUI or LangGraph inside an isolated container with its own filesystem and resource limits.

- **Tier**: T2 (productivity)
- **Boundary**: `internal`
- **Default**: opt-in (`openTerminal.enabled=false`)
- **Upstream**: <https://github.com/open-webui/open-terminal>
- **Default image**: `ghcr.io/open-webui/open-terminal` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/open-terminal/`](../../templates/open-terminal/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `openTerminal.enabled` | Toggle the component |
| `openTerminal.image.{repository,tag}` | Container image override |
| `openTerminal.apiKey` | Explicit API key; otherwise auto-generated into `open-terminal-secret` |
| `openTerminal.persistence.{enabled,size,storageClass}` | Optional PVC for the sandbox home directory |
| `openTerminal.resources` | CPU / memory; keep tight to contain blast radius |

## Security

Open Terminal executes attacker-controlled (i.e. model-generated) shell commands. Treat it as a privileged tier despite the T2 label:

- Keep `resources.limits` tight
- Put the pod on dedicated nodes or with strong `NetworkPolicy` egress restrictions
- Prefer ephemeral `emptyDir` storage unless persistence is explicitly required
- Review and audit the tool's command log in Open WebUI

## Related HOWTO sections

- [HOWTO §13.2 Pod Security](../../HOWTO.md#132-pod-security)
- [HOWTO §13.1 Network policies](../../HOWTO.md#131-network-policies)
