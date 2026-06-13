# License Compliance — ai-stack

**Chart version:** 2.12.0 | **Last reviewed:** 2026-06-13

This document tracks licenses for all container images deployed by the
ai-stack Helm chart and evaluates compliance implications for enterprise use.

---

## SBOM

A machine-readable Software Bill of Materials is maintained in
[sbom.cdx.json](../../sbom.cdx.json) (CycloneDX 1.6, JSON). The SBOM is validated
in CI via `cyclonedx-cli validate` against the CycloneDX 1.6 schema, with
package-version and image tag/digest parity cross-checked against `values.yaml`
and `zarf.yaml`.

---

## License Matrix

| Component | Image | Version | License (SPDX) | Type | Default | Copyleft |
|-----------|-------|---------|----------------|------|---------|----------|
| Open WebUI | `ghcr.io/open-webui/open-webui` | v0.9.6 | Open WebUI License | BSD-3 + branding | Enabled | No |
| Ollama | `ollama/ollama` | 0.30.6 | MIT | Permissive | Enabled | No |
| Qdrant | `qdrant/qdrant` | v1.18.2 | Apache-2.0 | Permissive | Enabled | No |
| Tika | `apache/tika` | 3.3.1.0 | Apache-2.0 | Permissive | Enabled | No |
| SearXNG | `searxng/searxng` | 2026.5.31-300695de5 | AGPL-3.0-or-later | Copyleft | Enabled | Yes |
| Valkey | `valkey/valkey` | 9.1.0 | BSD-3-Clause | Permissive | Enabled | No |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 0.153.0 | Apache-2.0 | Permissive | Conditional | No |
| LangGraph Server | `docker.io/langchain/langgraph-server` | 0.9-py3.12 | Elastic-2.0 (ELv2) | Source-available | Opt-in | No |
| Pydantic AI | `ghcr.io/astral-sh/uv` | python3.13-trixie-slim | Apache-2.0 OR MIT | Permissive | Opt-in | No |
| PostgreSQL | `docker.io/library/postgres` | 18-alpine | PostgreSQL | Permissive | Opt-in | No |
| PostgreSQL (CNPG operand) | `ghcr.io/cloudnative-pg/postgresql` | 18 | PostgreSQL (engine) + Apache-2.0 (CNPG packaging) | Permissive | Opt-in (`postgres.mode=cnpg`) | No |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | 0.11.34 | MIT | Permissive | Opt-in | No |
| MCPO | `ghcr.io/open-webui/mcpo` | main | MIT | Permissive | Opt-in | No |
| Authelia | `ghcr.io/authelia/authelia` | 4.39.20 | Apache-2.0 | Permissive | Opt-in | No |
| Ingestion Worker | `docker.io/library/python` | 3.14-slim | PSF-2.0 | Permissive | Opt-in | No |
| Envoy AI Gateway (controller) | `docker.io/envoyproxy/ai-gateway-controller` | v0.7.0 | Apache-2.0 | Permissive | Opt-in | No |
| Envoy AI Gateway (extproc) | `docker.io/envoyproxy/ai-gateway-extproc` | v0.7.0 | Apache-2.0 | Permissive | Opt-in | No |

**ai-stack chart license:** Apache-2.0

---

## License Analysis

### Permissive (no restrictions for enterprise use)

The majority of the stack uses permissive licenses (MIT, Apache-2.0,
BSD-3-Clause, PostgreSQL). These allow unrestricted commercial use,
modification, and redistribution with only attribution requirements.

OTel Collector, PostgreSQL, Open Terminal, MCPO, Authelia, Pydantic AI (`uv`/Python base; Pydantic AI, DBOS, FastAPI are all MIT/Apache-2.0), Envoy AI Gateway (controller + extproc, Apache-2.0 — no open-core carve-out, unlike the LiteLLM alternative rejected in ADR-006)

### Copyleft — SearXNG (AGPL-3.0-or-later)

**Risk level: Low (when used unmodified)**

The AGPL-3.0 license requires that modified source code be made available to
users who interact with the software over a network. Key considerations:

- **Unmodified container use**: Deploying the upstream `searxng/searxng` image
  without source-code modifications does **not** trigger copyleft obligations
  for the ai-stack chart or other stack components. AGPL copyleft applies only
  to the SearXNG codebase itself.
- **Configuration changes**: Helm values that inject environment variables or
  mount configuration files (e.g., `settings.yml`) are not considered source
  code modifications under AGPL.
- **If you modify SearXNG source code**: You must make the modified source
  available to network users. Consider linking to a fork repository.
- **No license contamination**: SearXNG runs as an isolated container
  communicating over HTTP. It does not link with or form a derivative work of
  other stack components.

**Recommendation:** Use the upstream container image without modification. If
modifications are required, maintain a public fork and link to it from your
deployment documentation.

### Source-Available — LangGraph API (Elastic License 2.0)

**Risk level: Medium-High (review licensing before production)**

The LangGraph ecosystem ships **two artifacts with different licenses**, and the
chart deploys the more restrictive one:

- The **`langgraph` Python library** (graph definitions) is **MIT**.
- The **`langgraph-server` / `langgraph-api` runtime** — the container image this
  chart deploys (`docker.io/langchain/langgraph-server`) — is **Elastic License
  2.0**. It provides the HTTP API, persistence, task queues, and streaming.

Elastic License 2.0 restrictions:

- **Permitted**: internal self-hosted deployment, modification for internal use,
  integration with other internal tools.
- **Prohibited**: offering it as a managed service to third parties (no
  as-a-service resale), circumventing the license-key functionality, or removing
  licensing/notice markings.
- **Not OSI-approved**: ELv2 is not open source per the Open Source Initiative.

**Production license key (important).** Beyond the ELv2 text, LangChain gates the
`langgraph-server` runtime behind **LangGraph Platform** deployment tiers: a free
self-hosted *Developer* tier (per LangChain's published terms as of 2026-05, up to
~100k nodes/month, requiring a LangSmith API key) and a **commercial (Enterprise)
license key for production / at-scale self-hosting**. Note that `langgraph build`
and `langgraph dev` both exercise `langgraph-api`. **Verify the current terms and
the threshold for your version and deployment tier before relying on
self-hosting** — these terms change and Enterprise pricing is negotiated.

**Recommendations:**

- Internal, low-volume use: the free Developer tier may suffice — confirm the
  current node/usage cap and key requirement for your image version.
- Production/scale, or if you require a 100%-permissive-OSS stack: either budget
  for a LangGraph Platform Enterprise license, **or** use the chart's
  MIT-licensed alternative agentic runtime — **Pydantic AI**
  (`pydanticai.enabled=true`; see
  [docs/components/pydanticai.md](../components/pydanticai.md)) — which reuses the
  same PostgreSQL, Ollama, MCPO, Qdrant, and OTel integrations.
- LangGraph remains opt-in (disabled by default) to ensure conscious adoption.

### Branded — Open WebUI License (BSD-3-Clause + branding clause)

**Risk level: Low (for internal / regulated deployments).**

The deployed `open-webui` image is **not MIT**. Since v0.6.6 the project ships
under the custom **"Open WebUI License"**: BSD-3-Clause terms plus a
branding-protection clause (§4) that prohibits altering, removing, or obscuring
the "Open WebUI" branding in deployments or distributions. The clause does
**not** apply when:

- the deployment has **50 or fewer end users** (individual natural persons with
  direct access) in any rolling 30-day window, **or**
- you have prior written permission, or a commercial enterprise license that
  permits rebranding.

Implications for ai-stack:

- **No copyleft and no network-source obligation** — unlike AGPL, the branding
  clause does not require disclosing source and does not affect the licenses of
  other stack components or of the chart itself (Apache-2.0).
- **Internal / regulated use is unaffected** as long as the "Open WebUI"
  branding is left intact. The chart does not alter it; the AI Act Art. 50(1)
  transparency banner (`WEBUI_BANNER_TEXT`) is additive, not a branding change.
- **If you white-label** the UI above the 50-user threshold, obtain an
  enterprise license. The chart's MIT/Apache alternative is the agentic runtime
  (Pydantic AI), not a replacement front-end.

## Runtime-downloaded models (not container images)

Some models are **pulled at runtime** (into a PVC on first use, like any Ollama
model) rather than baked into the container images, so they are not part of the
image SBOM / Zarf mirror set. Operators selecting models must verify the model
license; the chart's defaults and recommendations are:

| Model | Used for | Default | License (SPDX) | Notes |
|-------|----------|---------|----------------|-------|
| `nomic-embed-text` | RAG embeddings (Open WebUI, ingestion worker, Pydantic AI) | Yes (pulled post-deploy) | Apache-2.0 | Instruction-tuned; the chart applies its task prefixes (ADR-011) |
| `BAAI/bge-reranker-v2-m3` | Optional cross-encoder reranker | No (opt-in) | Apache-2.0 | Fetched by Open WebUI when `RAG_RERANKING_MODEL` is set and hybrid search is enabled |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Optional cross-encoder reranker (lighter) | No (opt-in) | Apache-2.0 | Alternative reranker |
| Chat LLMs (e.g. `llama3.2`) | Inference via Ollama | Operator-selected | **Per model** | Llama models use the Llama Community License (usage restrictions, not OSI-approved); Mistral / Qwen / Gemma vary — verify before production |

Reranking models download from Hugging Face at runtime: enabling reranking under
the default-deny NetworkPolicy requires an egress grant or pre-staging the model
into the Open WebUI PVC (see
[ADR-011](../architecture/ADR-011-rag-retrieval-quality.md)).

---

## Enterprise Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| All licenses identified | Done | 17 container images catalogued |
| SBOM in standard format | Done | CycloneDX 1.6 JSON (`sbom.cdx.json`) |
| SBOM validated in CI | Done | `cyclonedx-cli validate` in lint workflow |
| No GPL-2.0-only (incompatible with Apache-2.0) | Pass | No GPL-2.0-only components |
| Copyleft components identified | Done | SearXNG (AGPL-3.0) — low risk when unmodified |
| Source-available components identified | Done | LangGraph API (ELv2) — opt-in; production self-host needs a commercial license key (MIT alternative: Pydantic AI) |
| Attribution requirements met | Done | License file included; component licenses in SBOM |
| Dependency update tracking | Done | Renovate for container images (helm-values, pinDigests), GitHub Actions, Dockerfiles, and hashed Python locks (ADR-010) |
| Deep SBOM generation | Done | Syft scans all images in CI (`syft-sbom` job) |
| License review on update | Recommended | Add license check to Renovate PR review process |

---

## Updating This Document

When adding or updating a component:

1. Update the image reference in `values.yaml`
2. Update the corresponding entry in `sbom.cdx.json` (version, purl, license)
3. Update the license matrix table above
4. If the new component introduces a copyleft or source-available license,
   add an analysis section and update the compliance checklist
5. Run `helm lint` and CI to validate the SBOM

Deep SBOMs (OS packages and language-level dependencies) are generated
automatically in CI by [Syft](https://github.com/anchore/syft). The
`syft-sbom` workflow job scans every container image via registry, produces
per-image CycloneDX 1.6 JSON SBOMs, validates them against the CycloneDX
schema, and uploads them as build artifacts (retained for 90 days).
