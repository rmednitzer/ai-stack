# ADR-015 — Open WebUI wiring correction and the full-deployment overlay

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (corrects env-var names that the pinned Open WebUI no
  longer reads, adds a new overlay + guide; no L1 / template-contract signature
  removed or changed)
- **Relates to:** [ADR-011](ADR-011-rag-retrieval-quality.md) (RAG quality),
  [ADR-004](ADR-004-pydantic-ai-runtime.md) (Pydantic AI runtime)

---

## Context

A review of how the components are wired into Open WebUI, validated against the
upstream Open WebUI source (`config.py`), found that several Open WebUI
environment variables the chart sets had been **renamed or removed upstream** and
were therefore silently ignored on the pinned image (`v0.9.6`):

- `RAG_WEB_SEARCH_ENGINE` → `WEB_SEARCH_ENGINE`, and there was **no enable flag**
  at all (`ENABLE_WEB_SEARCH`). SearXNG was configured but web search could never
  run.
- `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` → `CHUNK_SIZE` / `CHUNK_OVERLAP`. The
  chart's chunking tuning was ignored; Open WebUI used its own defaults.
- `WEBUI_BANNER_TEXT` / `WEBUI_BANNER_DISMISSIBLE` → `WEBUI_BANNERS` (a JSON list).
  **The AI Act Art. 50(1) transparency banner never rendered** — a compliance
  claim that was not actually met.
- `MAX_UPLOAD_SIZE` (bytes) → `FILE_MAX_SIZE` (**megabytes**). The upload cap was
  ignored, and a naive rename carrying the byte value would have set a ~50 TB cap.

The embedding, top-k, hybrid/rerank, content-extraction, and Qdrant vars were
verified **current** and left unchanged.

Separately, "wiring the ingestion worker into Open WebUI" needed clarifying.
Open WebUI's native RAG manages its **own** Qdrant collections (per knowledge
base / file id); it does not read an arbitrary external collection. The ingestion
worker always upserts to one shared collection (`documents`). The clean
integration is the **Pydantic AI agent**: it already exposes a
`search_knowledge_base` tool over `QDRANT_COLLECTION` (default `documents`, the
same the worker writes), and `pydanticai.exposeToOpenWebUI` registers it as a
model in Open WebUI's picker. So there are two distinct RAG paths, and the worker
reaches Open WebUI through the agent, not through native RAG.

Constraints: never weaken a default; `values.yaml` is the source of truth;
surgical change; validate against trusted sources; POL-002 (no inline credentials
in workload manifests).

## Decision

1. **Correct the stale Open WebUI env vars** in `values.yaml`, each annotated as
   validated against `open-webui` `config.py`: add `ENABLE_WEB_SEARCH`, rename to
   `WEB_SEARCH_ENGINE`, `CHUNK_SIZE` / `CHUNK_OVERLAP`, `FILE_MAX_SIZE` (in MB,
   value `50`), and convert the AI Act banner to `WEBUI_BANNERS` (a JSON array
   carrying the same disclosure). Fix every doc reference to the old names. The
   worker's own `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` (a separate contract it
   reads) are left unchanged.

2. **Keep web search off by default; on only in the full overlay.** Web content
   is attacker-influenced (SECURITY.md), so the base stays `ENABLE_WEB_SEARCH=false`
   (its prior *effective* behaviour, now correctly named and toggleable);
   `values-full.yaml` sets it true.

3. **Add `values-full.yaml`** — a feature-complete reference overlay that enables
   the optional plane (ingestion worker, Pydantic AI with `exposeToOpenWebUI`,
   web search, standalone Postgres, Valkey persistence, OTel) and wires the
   worker → agent → Open WebUI RAG path out of the box. MCPO, LangGraph, and
   Authelia are left as commented, ready-to-enable blocks (operator-specific).

4. **MCPO → Open WebUI stays a documented operator step.** Open WebUI's
   `TOOL_SERVER_CONNECTIONS` embeds the tool-server API key as inline JSON; baking
   MCPO's generated key into the Open WebUI pod env as plaintext would violate
   POL-002. The operator adds the connection in the Open WebUI admin UI (key from
   the `mcpo` Secret), where Open WebUI stores it in its database.

5. **Add `docs/operations/full-deployment.md`** documenting the topology, the two
   RAG paths, model pulls, feeding the worker, and the MCPO / LangGraph / Authelia
   steps, plus the security posture of enabling the model-driven plane.

## Consequences

**Positive**

- Open WebUI is actually configured, not nominally: web search works when enabled,
  chunking tuning applies, the upload cap is correct, and the AI Act transparency
  banner renders — restoring a compliance claim that was silently unmet.
- The "especially the ingestion worker" goal is delivered: `values-full.yaml`
  makes documents enqueued to the worker answerable in Open WebUI via the
  `pydanticai-agent` model, with the writer/reader collection and embedding
  prefixes kept consistent by the chart.
- A single, validated reference for a complete deployment, distinct from the HA
  hardening overlay it composes with.

**Negative**

- The full overlay enables the model-driven attack surface (web search, agent
  tool-use). Mitigated by keeping it opt-in, documenting the posture, and pointing
  at the hardening guide (FQDN egress, runtimeClass, mTLS, admission).
- MCPO wiring is not turn-key (one manual UI step), a deliberate trade for
  credential hygiene (POL-002).

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change: values, template
  env names, a new overlay, tests, and docs. Accumulates in `CHANGELOG.md`
  `[Unreleased]`.
- The env-var corrections change which Open WebUI settings take effect on upgrade
  (e.g. chunking now applies the chart's 1500/150). Operators who relied on the
  silently-ignored values get the intended ones; re-index if chunking changes
  retrieval materially.

## Alternatives considered and rejected

- **Auto-wire MCPO via `TOOL_SERVER_CONNECTIONS`.** Rejected: the key is inline in
  that JSON; templating the generated MCPO key into the pod env is a plaintext
  credential in a manifest (POL-002). The admin-UI step keeps the key in Open
  WebUI's database.
- **Make the ingestion worker feed Open WebUI's native RAG collections.**
  Rejected: Open WebUI owns its collection naming/lifecycle; writing into them
  externally is brittle and unsupported. The agent-as-model path is the
  supported, stable integration.
- **Enable web search by default once the var name is fixed.** Rejected: it would
  turn on the attacker-influenced web surface for every deployment — a security
  default weakening. Opt-in via the full overlay instead.
- **Keep the old env-var names "for compatibility."** Rejected: they are not read
  by the pinned image, so keeping them ships dead config and a false compliance
  claim. Correctness over inertia.

## Revisit triggers

- Open WebUI renames these vars again, or the pinned image is bumped across a
  config-breaking release — re-validate the env set against the new `config.py`.
- Open WebUI gains a way to reference tool-server credentials from a Secret (not
  inline JSON) — revisit auto-wiring MCPO.
- A shipped overlay enables the agent path in production — revisit whether the
  worker → agent collection contract should be asserted by a test beyond the
  shared default.
