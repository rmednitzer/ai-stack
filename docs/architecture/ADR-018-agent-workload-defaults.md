# ADR-018 — Useful defaults for the agentic workloads (bounded runs, temperature, prompt)

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive defaults on the opt-in agentic runtimes; no L1 / template-contract signature removed or changed)
- **Relates to:** [ADR-004](ADR-004-pydantic-ai-runtime.md) (Pydantic AI runtime),
  [ADR-011](ADR-011-rag-retrieval-quality.md) (RAG quality / prompts),
  [ADR-017](ADR-017-openwebui-wiring-completeness.md) (the wiring pass that preceded this)

---

## Context

The stack's two agentic workloads are the Pydantic AI agent
(`files/pydanticai/app.py`, MIT) and LangGraph (Elastic-licensed, opt-in). A
review of their out-of-the-box configuration, validated against pydantic-ai
1.106 and `langchain-ai/langgraph`, found the workloads under-defaulted for a
governed, EU-regulated, often air-gapped / local-inference deployment:

- **Unbounded runs.** The Pydantic AI agent called `runner.run(...)` /
  `agent.run_stream(...)` with **no `usage_limits`**. pydantic-ai applies an
  implicit `request_limit` of 50, but `tool_calls_limit`, `total_tokens_limit`,
  and `output_tokens_limit` all default to `None` (unbounded). The agent exposes
  looping tools (`web_search`, `search_knowledge_base`), so a tool-calling loop
  could run up to 50 model round-trips with no token or tool-call ceiling, which
  on local inference is a real time/compute footgun. LangGraph is worse: the
  `langgraph-server` image defaults `LANGGRAPH_DEFAULT_RECURSION_LIMIT` to
  `10007`, effectively unbounded.
- **No model settings.** No `temperature` was set, so sampling used whatever the
  Ollama model defaulted to, which is not ideal for grounded, tool-using answers.
- **A thin default prompt.** The default system prompt was a single generic
  line that did not steer the agent to use its tools, ground answers, admit
  uncertainty, or disclose that it is an AI (AI Act Art. 50 transparency).

These are the "useful defaults" the workloads were missing. Constraints: never
weaken a default; `values.yaml` is the source of truth; validate against trusted
sources; keep everything env-overridable; do not invent env vars an image does
not read (the ADR-002 lesson).

## Decision

1. **Bound every Pydantic AI run (safety + cost).** Build a pydantic-ai
   `UsageLimits` from env and pass it to `runner.run`, `agent.run_stream`, and
   thus (via `DBOSAgent` forwarding) durable runs:
   `AGENT_REQUEST_LIMIT` (default `12`, tighter than the implicit `50`),
   `AGENT_TOOL_CALLS_LIMIT` (default `8`), and `AGENT_TOTAL_TOKENS_LIMIT`
   (default empty = unbounded, opt-in so long answers are not truncated). An
   empty value makes a dimension unbounded; the code and chart defaults keep the
   loop bounded out of the box. Hitting a limit returns a clean notice
   (`finish_reason: length`), not a 5xx, since a bound is expected behaviour.

2. **Set a low default temperature.** `AGENT_TEMPERATURE` (default `0.2`) is
   applied as the agent's `model_settings` (`ModelSettings(temperature=...)`);
   empty uses the model/provider default.

3. **Ship a grounded, tool-aware, transparent default prompt.** The default
   `AGENT_SYSTEM_PROMPT` now instructs the agent to use its retrieval/web tools
   when relevant, ground answers in what they return, admit uncertainty instead
   of guessing, and not claim to be human. Still fully overridable.

4. **Give LangGraph a sane default recursion limit.** Set
   `LANGGRAPH_DEFAULT_RECURSION_LIMIT=25` (LangGraph's own conventional default)
   so a runaway graph cannot loop indefinitely under the server image's `10007`.
   The model, temperature, prompt, and token usage-limits live in the operator's
   graph code (not server env); the chart documents the recommended values for
   parity rather than inventing env vars the image does not read.

All four are env-configurable; the changes are additive to the opt-in workloads
and validated against pydantic-ai 1.106 (`UsageLimits` fields, `ModelSettings`,
`UsageLimitExceeded`, `DBOSAgent`/`run_stream` forwarding) and
`langchain-ai/langgraph` (`LANGGRAPH_DEFAULT_RECURSION_LIMIT`, graph-vs-server
split).

## Consequences

**Positive**

- A tool-calling loop can no longer run away on local inference; runs are bounded
  in requests and tool calls by default, with an opt-in hard token cap.
- Grounded, tool-aware answers by default (low temperature + a prompt that steers
  retrieval and honesty), and AI-transparency baked into the default prompt.
- LangGraph gets the same loop-bound discipline at the one knob its image exposes.

**Negative**

- The default request/tool-call bounds could cut off an unusually long legitimate
  tool chain; operators raise the limits (or set them empty) for such workloads.
- The changed default prompt and temperature alter agent behaviour on upgrade for
  anyone who relied on the old generic prompt / model-default sampling; both are
  env-overridable to restore prior behaviour.

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change; agent source,
  values, tests, and docs. Accrues in `CHANGELOG.md` `[Unreleased]`.
- Both workloads are opt-in (`enabled: false`), so the default (lab) render is
  unchanged unless an agent is enabled.

## Alternatives considered and rejected

- **Leave runs unbounded (rely on pydantic-ai's implicit 50).** Rejected: 50
  model round-trips with no token/tool-call ceiling is not a safe default for a
  governed local-inference stack.
- **Default a hard `total_tokens_limit`.** Rejected as a default: it would
  truncate legitimate long answers; left opt-in (empty) while the request and
  tool-call bounds carry the safety.
- **Wire LangGraph model/temperature/prompt via env.** Rejected: those are graph
  code, not server env in `langgraph-server`; inventing env the image ignores
  would be dead config (ADR-002). Documented as graph-level guidance instead.
- **Put `temperature`/limits in the shared chart helpers.** Rejected: they are
  agent-specific; they belong in the agent's own env and code.

## Revisit triggers

- pydantic-ai changes the `UsageLimits` fields or the implicit `request_limit`.
- `langgraph-server` exposes model/temperature/prompt or per-run usage limits as
  server env (today they are graph-only) — revisit wiring them.
- A shipped reference graph for LangGraph lands — bake the parity defaults into it.
- Operators report the default request/tool-call bounds are too tight for common
  workloads — retune the defaults.
