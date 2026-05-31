# Limitations

Explicit scope boundaries and known gaps for the ai-stack chart. Each entry
states the current state, the implication for an operator, and where it is
tracked. This is a living document; the list is expected to change as the chart
evolves. Last reviewed: 2026-05-31 (v2.6.0, tool/command-plane hardening).

The focus here is the **tool/command plane** (MCPO and Open Terminal) and the
**agentic runtimes**, where the chart ships capability that operators must
constrain deliberately. For the threat model these flow from, see
[SECURITY.md](SECURITY.md). For the control registry, see
[docs/governance/CONTROLS.md](docs/governance/CONTROLS.md).

## L1. Open Terminal runs model-generated code in a standard container

State: Open Terminal executes attacker-influenceable (model-generated) shell /
notebook commands. The pod is PodSecurity `restricted` + `seccomp:RuntimeDefault`
but, by default, shares the host kernel — that is the *minimum-viable* isolation
for untrusted code, not a sandbox.
Implication: a kernel-level escape from hostile code is not mitigated by the
chart defaults. Set `openTerminal.runtimeClassName` to a hardened RuntimeClass
(gVisor / Kata) for untrusted use, keep egress tight, and keep `resources.limits`
low. Prefer dedicated nodes.
Tracking: `SECURITY.md` (Threat model); `docs/components/open-terminal.md`.

## L2. No in-band command/tool authority policy

State: the chart does not classify, allow-list, or deny individual commands
(Open Terminal) or tool calls (MCPO) — those are upstream images, and ai-stack
does not patch them. Network egress + the API key + (opt-in) sandbox runtime are
the available controls.
Implication: a persuaded model can invoke any tool a configured MCP server
exposes, or run any command the sandbox permits. For per-command / per-tool
authority classification (tiering, deny-first, read-only mode), front the
surface with — or replace it by — a policy-aware MCP server you operate
separately (kept as a separate project; not bundled here).
Tracking: `docs/components/{mcpo,open-terminal}.md`.

## L3. MCPO authenticates with a single shared API key

State: MCPO requires an auto-generated API key on every request, but it is one
static shared secret — no per-client identity, rotation, or token audience
binding. MCPO is `ClusterIP` (in-cluster) by default.
Implication: acceptable as an in-cluster baseline alongside the default-deny
NetworkPolicy. If you expose MCPO via the gateway/ingress, front the route with
Authelia (OIDC / ForwardAuth) rather than relying on the key alone; the MCP
authorization spec's model for HTTP-exposed servers is OAuth 2.1.
Tracking: `docs/components/mcpo.md`.

## L4. Agentic runtimes ship without budget / approval governance

State: the chart deploys LangGraph and Pydantic AI and wires them to the tool
surface, but does not impose action budgets (steps / tokens / cost), a
human-in-the-loop approval gate for high-impact tool calls, or behavioral
contracts on tool use.
Implication: tool-use governance is the operator's responsibility in the
workload/graph code. OWASP LLM "excessive agency" mitigations (least privilege,
HITL for high-impact actions, budgets) should be implemented in the agent code;
ai-stack documents the pattern but does not enforce it.
Tracking: `SECURITY.md` (Threat model); `docs/components/{langgraph,pydanticai}.md`.

## L5. Audit telemetry is not tamper-evident on-cluster

State: with `global.otel.enabled=true`, tool-call and command activity is
traced and secrets are redacted before export, but the chart does not itself
provide an append-only, tamper-evident audit store.
Implication: for forensic / compliance-grade audit (CTL-001), export OTel
telemetry to an external, append-only sink off-cluster; the in-cluster pipeline
is collection + redaction, not immutable retention.
Tracking: `docs/components/otel.md`; `SECURITY.md`.

## L6. RBAC Roles/RoleBindings are not shipped

State: every component has a dedicated ServiceAccount with
`automountServiceAccountToken: false`, but the chart ships no Roles or
RoleBindings — least-privilege RBAC beyond "no API access" is left to the
deployer.
Implication: components do not get Kubernetes API permissions by default (good),
but if a workload needs scoped API access, the operator must author the RBAC.
Tracking: `docs/governance/CONTROLS.md` (POL-001).

## L7. Single-replica components are not highly available

State: several components are single-replica by default (e.g. Ollama is
GPU-bound; standalone PostgreSQL and single-node Qdrant have no replication).
Open WebUI is HA-capable only when its shared PostgreSQL + Valkey backends are
healthy.
Implication: a node or pod failure interrupts these components. For HA, use
`postgres.mode=cnpg`, scale stateless tiers, and review per-component docs;
single-node stores remain a recovery-from-backup story, not an HA story.
Tracking: `README.md`; `docs/components/*`.
