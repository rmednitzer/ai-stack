# ADR-019 — Gate Ollama runtime model-pull egress

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive opt-out flag; the default preserves current behaviour)
- **Relates to:** [ADR-002](ADR-002-image-digest-pinning.md) (digest pinning),
  the accepted-posture **A-8** recorded in
  [docs/audit/AUDIT-2026-06.md](../audit/AUDIT-2026-06.md) (third pass, finding
  D-1), and the FQDN-aware egress hardening (B6,
  [hardening guide](../operations/hardening-guide.md))

---

## Context

The Ollama `NetworkPolicy` permits egress to `TCP/443` to any destination
whenever `ollama.enabled` — Ollama needs it to pull models at runtime
(`ollama pull` from `registry.ollama.ai`). DNS is permitted separately by the
shared `allow-dns` policy; `:443` is the only other outbound connection Ollama
makes.

The 2026-06-14 audit (third pass, finding **D-1** / accepted posture **A-8**)
flagged this as the one component egress that was both **ungated and
undocumented**. The analogous open `:443`/`:80` egress on Open WebUI, the
Pydantic AI agent, and the ingestion worker (**A-1**) is operator-owned and
documented, with the FQDN-aware B6 layer to narrow it; Ollama's was neither
surfaced as a knob nor written down. In a regulated / air-gapped cluster, models
should be pre-pulled and no runtime egress permitted.

## Decision

Add an opt-out boolean `ollama.allowModelPullEgress`, **default `true`**, gating
the Ollama `:443` egress rule.

- **Default `true`** preserves the out-of-box experience (models pull at runtime)
  and does **not weaken any current default** — the egress is open today, so this
  is purely additive: a new opt-out lever, not a posture relaxation.
- **`false`** drops the egress rule. `policyTypes` still lists `Egress`, so with
  no rules the namespace default-deny isolates Ollama to **DNS only**. Operators
  pre-pull models into the persistence PVC (`ollama pull` via `kubectl exec`, or
  a mirrored registry) before closing the gate.

**Default `false` was considered and rejected.** It would break runtime model
pulls out of the box — a surprising functional regression in a minor release —
and is inconsistent with the chart's working-lab default and the A-1 precedent
(those egresses are also open by default and hardened by the operator layer).
Regulated operators flip one flag; the trade-off is documented in
[`docs/components/ollama.md`](../components/ollama.md) and the hardening guide.

## Consequences

- Regulated / air-gapped operators get a one-line L3/L4 control that **fully
  closes** Ollama's internet egress — complementing the B6 FQDN layer, which
  *narrows* egress to named hosts rather than closing it.
- No behaviour change at the default. Both states are asserted in
  `tests/networkpolicy_test.yaml` (`:443` present by default; no egress rule when
  gated off).
- DNS egress is unaffected (shared `allow-dns` policy), so in-cluster name
  resolution and the readiness/liveness paths keep working when the gate is off.
- No image or chart-version change; additive opt-out value only.
