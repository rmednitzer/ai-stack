# Open Terminal

Sandboxed terminal service for AI agents. Executes shell commands on behalf of Open WebUI or LangGraph inside an isolated container with its own filesystem and resource limits.

- **Tier**: T2 (productivity)
- **Boundary**: `execution`
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
| `openTerminal.runtimeClassName` | Sandbox runtime for model-generated code (e.g. `gvisor`, `kata`). Empty = cluster default. **See Security below.** |
| `openTerminal.corsAllowedOrigins` | CORS allowed origin(s), comma-separated. Empty derives the Open WebUI origin; **never `*`**. |
| `openTerminal.persistence.{enabled,size,storageClass}` | Optional PVC for the home directory. **Defaults to `false` (ephemeral)** — see Security. |
| `openTerminal.resources` | CPU / memory; keep tight to contain blast radius |

## Security

Open Terminal executes **attacker-controlled (model-generated) shell commands**.
Treat it as a privileged tier despite the T2 label, and design for the case
where the model is steered by an indirect prompt injection (poisoned web
result, RAG document, or tool output) into running hostile commands.

### Threat model

The trust boundary is the command/notebook input: assume it can be
attacker-influenced. PodSecurity `restricted` + `seccomp:RuntimeDefault`
constrain the *container*, but they are **not a sandbox against hostile code**
— the container shares the host kernel. The defensive posture is layered:

1. **Runtime isolation (primary).** For untrusted code the
   industry-consensus control is a stronger kernel/VM boundary, not a standard
   container: microVM (Kata/Firecracker) ≈ gold standard, gVisor ≈ strong
   middle ground, standard container = minimum viable. Set
   `openTerminal.runtimeClassName` to a hardened RuntimeClass your cluster
   provides (`gvisor` / `kata`). This is the single highest-value hardening.
2. **Network egress (default-deny).** The chart's NetworkPolicy already
   restricts ingress to Open WebUI and permits only HTTP/HTTPS egress. Tighten
   egress further (or remove it) when the workload does not need the internet.
3. **Ephemeral home (default).** `persistence.enabled` now defaults to
   `false` so a payload written to `$HOME` does not survive a restart. Enable
   persistence only when a durable home is genuinely required; the PVC keeps
   `helm.sh/resource-policy: keep` so existing data is not deleted on change.
4. **Scoped CORS.** In the default topology Open Terminal is `ClusterIP` and its
   NetworkPolicy admits only the Open WebUI pod, so it is reached **server-side
   (pod-to-pod)** and CORS is not exercised. CORS only applies if you
   deliberately expose Open Terminal's terminal/notebook UI to a browser. Either
   way the chart never emits `*` (OWASP A05): `corsAllowedOrigins` is templated
   into `OPEN_TERMINAL_CORS_ALLOWED_ORIGINS`; leave it empty to derive the Open
   WebUI ingress origin, or set the exact browser origin(s) when you expose the UI.
5. **Tight resource limits.** Keep `resources.limits` low to bound a runaway
   or mining payload (CPU limits throttle rather than kill — pair with #1).
6. **Audit.** When `global.otel.enabled=true`, traffic is traced through the
   OTel Collector, which redacts secrets (incl. tokens/keys) before export.
   For a tamper-evident record, ship that telemetry off-cluster (an external,
   append-only sink); see [OTel](otel.md) and `SECURITY.md` (Threat model).

### Residual risk

Without a hardened `runtimeClassName`, a kernel-level escape from
model-generated code is *not* mitigated by the chart — the controls above
reduce but do not eliminate blast radius. State and design for this rather
than discover it: prefer a sandboxed RuntimeClass, dedicated nodes, and tight
egress for any untrusted use. ai-stack does not add an in-band command
allow/deny policy *inside* Open Terminal (that is an upstream concern); if you
need per-command authority classification, front it with — or replace it by —
a policy-aware MCP server of your own (kept as a separate project).

## Related HOWTO sections

- [HOWTO §13.2 Pod Security](../../HOWTO.md#132-pod-security)
- [HOWTO §13.1 Network policies](../../HOWTO.md#131-network-policies)
