# ADR-004 — Pydantic AI as an MIT-licensed agentic-runtime alternative

- **Status:** Accepted
- **Date:** 2026-05-31
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.4.0
- **Supersedes:** none (complements the LangGraph component)

---

## Context

The chart's agentic runtime is **LangGraph**, deployed via the
`docker.io/langchain/langgraph-server` image. That image is **Elastic License
2.0**: beyond the no-managed-service-resale clause, LangChain gates production
self-hosting of `langgraph-server`/`langgraph-api` behind a **LangGraph Platform
commercial license key** (a free Developer tier exists up to a usage cap). This
is documented in `LICENSE_COMPLIANCE.md` and ADR-adjacent compliance notes.

For a chart whose identity is **EU-regulated, sovereign, permissive-OSS,
air-gappable**, depending on a source-available runtime with a production key
requirement is a real liability. The stack already provides everything an
agentic runtime needs (Ollama, Qdrant, SearXNG, MCPO tools, PostgreSQL, OTel),
so a permissive alternative can reuse all of it.

## Decision

1. **Add an opt-in `pydanticai` component** (default **false**) built on
   [Pydantic AI](https://ai.pydantic.dev/) (MIT) with **durable execution via
   DBOS** (MIT), checkpointed in the **shared PostgreSQL** — degrading to
   non-durable if Postgres is absent.

2. **Alternative, not a replacement.** LangGraph stays. Both implement the same
   contracts (Postgres state, Qdrant memory, MCPO tools, Ollama/External-API
   inference, Open WebUI front door); operators choose by licensing and
   execution model. See REFERENCE.md §3.

3. **Self-contained, like the ingestion worker.** The reference agent lives in
   `files/pydanticai/app.py`, loaded into a ConfigMap via `.Files.Get`; deps
   install at startup (`buildDeps: true`) or are baked into a prebuilt image
   (`files/pydanticai/Dockerfile`, `buildDeps: false`). Base image
   `ghcr.io/astral-sh/uv` (uv + Python) — a distinct image basename keeps the
   SBOM/parity machinery's one-image-per-component invariant intact, and `uv`
   gives fast, deterministic installs.

4. **DBOS chosen over Temporal/Restate/Prefect** for durability. Pydantic AI
   documents all four; DBOS runs **in-process and checkpoints to the existing
   PostgreSQL**, so it adds no new infrastructure to the chart — the best fit for
   a self-contained, air-gappable package. Restate/Temporal remain valid for
   users who already run them.

5. **Full chart wiring**: ServiceAccount, API-key Secret (bearer-enforced on
   `POST /run`), default-deny NetworkPolicy, optional HPA + PDB, Service, and
   Ingress + Gateway API HTTPRoute (ADR-003). Catalogued in `sbom.cdx.json`,
   `zarf.yaml`, `values.schema.json`, and the license matrix.

## Consequences

**Positive**

- A fully **MIT/Apache-2.0** agentic path with no production license-key
  requirement — aligned with the chart's sovereignty/OSS posture.
- Reuses existing PostgreSQL/Ollama/Qdrant/SearXNG/MCPO/OTel; no new infra.
- Type-safe, testable agents; OpenTelemetry-instrumented for the existing pipeline.

**Negative / accepted trade-offs**

- The agent is a **reference to extend**, not a turnkey platform — teams own the
  server/tool surface (vs LangGraph Platform's batteries-included UX).
- One more in-chart Python app and one more base image (`uv`) to track.
- DBOS shares the application PostgreSQL (separate schema); heavy agent workloads
  may warrant a dedicated database.

## Related artifacts

- `files/pydanticai/{app.py,requirements.txt,Dockerfile}`
- `templates/pydanticai/deployment.yaml`, `templates/common/*` (SA/secret/netpol/pdb/hpa)
- `values.yaml` `pydanticai:` block; `values.schema.json`
- `docs/components/pydanticai.md`; `LICENSE_COMPLIANCE.md`
- `docs/architecture/REFERENCE.md` §3 (Agentic flow)
