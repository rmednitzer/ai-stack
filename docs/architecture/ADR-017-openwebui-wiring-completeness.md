# ADR-017 — Open WebUI wiring completeness: OTel activation, signup defaults, terminal-server docs

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (completes the Open WebUI wiring from ADR-015; no L1 / template-contract signature removed or changed)
- **Relates to:** [ADR-015](ADR-015-openwebui-wiring-full-deployment.md) (Open WebUI wiring + full overlay),
  [ADR-016](ADR-016-audit-2026-06.md) (the audit that preceded this), and
  [MULTI_USER.md](../operations/MULTI_USER.md) (multi-user governance guidance)

---

## Context

A focused, source-validated review of how Open WebUI is configured and wired to
the stack's tools (the brief: "is it optimally configured and wired with all
tools?") found the data/retrieval/model plane wired well and tuned, with the
tool-execution plane (MCPO, Open Terminal) deliberately left as admin-UI steps
for credential hygiene (POL-002). It also found one real defect and a few
completeness/optimal-config gaps. Every fix below was validated against the
upstream `open-webui` source/docs (via DeepWiki and the env-config reference):

- **F-A (defect):** the chart injects the OTel SDK convention vars
  (`OTEL_EXPORTER_OTLP_*`, via `ai-stack.otelEnv`) into Open WebUI, but Open WebUI
  gates all OpenTelemetry behind its **own** `ENABLE_OTEL` flag plus the
  per-signal `ENABLE_OTEL_TRACES` / `ENABLE_OTEL_METRICS` (all default-off
  upstream; OTel added in Open WebUI 0.6.0, present in the pinned v0.9.6). Without
  them, Open WebUI emitted **no** traces or metrics even with
  `global.otel.enabled=true` — so the "monitoring via OTel" control credited to
  the chat surface was nominal, not real. (The shared vars do work for the
  self-instrumenting Pydantic AI app, which is why this was easy to miss.)
- **F-B (posture):** the chart set `WEBUI_AUTH=true` but left `ENABLE_SIGNUP` /
  `DEFAULT_USER_ROLE` to Open WebUI's defaults (open self-registration; new users
  `pending`). The governed default was documented in `MULTI_USER.md` but not
  applied, so it could silently regress.
- **F-C (completeness/doc):** Open Terminal ships as a component, but Open WebUI
  was never told how to reach it. It connects via `TERMINAL_SERVER_CONNECTIONS`,
  whose JSON embeds the auth key inline (the same POL-002 situation as MCPO), so
  it must be an admin-UI step — but unlike MCPO that step was undocumented.
- **F-D (optimal-config):** when web search is enabled (the full overlay), only
  the engine and URL were set; the result-count, concurrency, and domain-filter
  knobs were left at upstream defaults.

Constraints honoured: never weaken a default; `values.yaml` is the source of
truth; surgical change; validate against trusted sources; assert security-
relevant behaviour in `tests/` (CLAUDE.md principle 3); POL-002.

## Decision

1. **Activate Open WebUI OTel with the pipeline (F-A).** Add `ENABLE_OTEL`,
   `ENABLE_OTEL_TRACES`, and `ENABLE_OTEL_METRICS` to `openwebui.env`, each
   templated to `global.otel.enabled` — so they render `false` by default (off,
   no telemetry) and `true` when the operator turns the collector pipeline on.
   They ride the `OTEL_EXPORTER_OTLP_*` vars `ai-stack.otelEnv` already injects,
   and export through the redaction-applying OTel Collector. Logs stay off.

2. **Pin the governed signup defaults (F-B).** Set `DEFAULT_USER_ROLE: "pending"`
   explicitly (it matches upstream's default, so no behaviour change, but it can
   no longer silently regress and it documents intent). Keep `ENABLE_SIGNUP=true`
   so the first admin can bootstrap, with a comment directing operators to set it
   `false` in production once an admin exists, or when Authelia OIDC is the front
   door (OIDC signup remains handled by `ENABLE_OAUTH_SIGNUP`).

3. **Document the Open Terminal admin-UI step (F-C).** Add an "Open Terminal"
   section to the full-deployment guide (retrieve the key from
   `<release>-open-terminal-secret`, add the connection in **Admin Settings →
   Integrations → Open Terminal**), surface it as a ready-to-enable block in
   `values-full.yaml`, and reiterate the runtime-hardening caveat for the
   highest-risk plane. No env wiring (POL-002: the key is inline JSON).

4. **Add web-search tuning to the full overlay (F-D).** Set
   `WEB_SEARCH_RESULT_COUNT=5` (upstream 3), `WEB_SEARCH_CONCURRENT_REQUESTS=10`
   (upstream 0 = unbounded), and an empty `WEB_SEARCH_DOMAIN_FILTER_LIST` with the
   allow/`!`-exclude syntax documented, as a defense-in-depth hook for the
   attacker-influenced web plane.

## Consequences

**Positive**

- Open WebUI now actually emits traces + metrics when telemetry is enabled, so
  the NIS2 Art. 21(2)(b) detection / Art. 26 monitoring control covers the chat
  surface, not just the backend services.
- The governed signup posture is a chart default, not just documentation.
- Operators can wire Open Terminal without reverse-engineering the admin UI, and
  the web plane has a domain-filter hook.

**Negative**

- Three more env vars on the Open WebUI pod when telemetry is on; metrics export
  adds minor overhead. Acceptable for the observability gained.
- Open Terminal wiring stays a manual admin-UI step (POL-002 trade-off, as MCPO).

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change; values, an overlay,
  tests, and docs. Accrues in `CHANGELOG.md` `[Unreleased]`.
- OTel flags default `false`, so the default (lab) render only gains the two
  signup vars; nothing else changes out of the box.

## Alternatives considered and rejected

- **Set `ENABLE_OTEL` in the shared `ai-stack.otelEnv` helper.** Rejected: that
  helper feeds every component; `ENABLE_OTEL` is an Open WebUI-specific flag and
  would be meaningless noise on Tika/Qdrant/etc. Keep it in `openwebui.env`.
- **`ENABLE_OTEL=true` alone.** Rejected: upstream requires the per-signal
  `ENABLE_OTEL_TRACES` / `ENABLE_OTEL_METRICS` (both default-off) — confirmed
  against `open-webui` and its `docker-compose.otel.yaml`.
- **Enable `ENABLE_OTEL_LOGS` too.** Rejected for now: logs can carry more raw
  content and the collector pipeline targets traces + metrics; revisit if a logs
  pipeline is added.
- **`ENABLE_SIGNUP=false` by default.** Rejected: it blocks first-admin
  bootstrap. Documented as the production hardening instead.
- **Auto-wire Open Terminal via env.** Rejected: `TERMINAL_SERVER_CONNECTIONS` is
  inline-key JSON (POL-002), exactly like MCPO. Admin-UI step.

## Revisit triggers

- Open WebUI changes the OTel flag names or makes `ENABLE_OTEL` activate signals
  on its own — re-validate the env set.
- Open WebUI gains a way to reference terminal/tool-server keys from a Secret
  (not inline JSON) — revisit auto-wiring Open Terminal and MCPO.
- A logs pipeline is added to the OTel Collector — revisit `ENABLE_OTEL_LOGS`.
- The chart adopts OIDC-only auth as a profile — revisit defaulting
  `ENABLE_SIGNUP=false` there.
