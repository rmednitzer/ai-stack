# License Compliance — ai-stack

**Chart version:** 2.4.0 | **Last reviewed:** 2026-05-31

This document tracks licenses for all container images deployed by the
ai-stack Helm chart and evaluates compliance implications for enterprise use.

---

## SBOM

A machine-readable Software Bill of Materials is maintained in
[sbom.cdx.json](../../sbom.cdx.json) (CycloneDX 1.6, JSON). The SBOM is validated
in CI via `check-jsonschema` against the CycloneDX 1.6 JSON schema.

---

## License Matrix

| Component | Image | Version | License (SPDX) | Type | Default | Copyleft |
|-----------|-------|---------|----------------|------|---------|----------|
| Open WebUI | `ghcr.io/open-webui/open-webui` | v0.9.5 | MIT | Permissive | Enabled | No |
| Ollama | `ollama/ollama` | 0.24.0 | MIT | Permissive | Enabled | No |
| Qdrant | `qdrant/qdrant` | v1.18.1 | Apache-2.0 | Permissive | Enabled | No |
| Tika | `apache/tika` | 3.3.1.0 | Apache-2.0 | Permissive | Enabled | No |
| SearXNG | `searxng/searxng` | 2026.5.31-300695de5 | AGPL-3.0-or-later | Copyleft | Enabled | Yes |
| Valkey | `valkey/valkey` | 9.1.0 | BSD-3-Clause | Permissive | Enabled | No |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 0.153.0 | Apache-2.0 | Permissive | Conditional | No |
| LangGraph Server | `docker.io/langchain/langgraph-server` | 0.9-py3.12 | Elastic-2.0 (ELv2) | Source-available | Opt-in | No |
| Pydantic AI | `ghcr.io/astral-sh/uv` | python3.13-trixie-slim | Apache-2.0 OR MIT | Permissive | Opt-in | No |
| PostgreSQL | `docker.io/library/postgres` | 18-alpine | PostgreSQL | Permissive | Opt-in | No |
| Workbench | `quay.io/jupyter/pytorch-notebook` | cuda12-python-3.13 | BSD-3-Clause | Permissive | Opt-in | No |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | 0.11.34 | MIT | Permissive | Opt-in | No |
| MCPO | `ghcr.io/open-webui/mcpo` | main | MIT | Permissive | Opt-in | No |
| Authelia | `ghcr.io/authelia/authelia` | 4.39.20 | Apache-2.0 | Permissive | Opt-in | No |
| Ingestion Worker | `docker.io/library/python` | 3.14-slim | PSF-2.0 | Permissive | Opt-in | No |

**ai-stack chart license:** Apache-2.0

---

## License Analysis

### Permissive (no restrictions for enterprise use)

The majority of the stack uses permissive licenses (MIT, Apache-2.0,
BSD-3-Clause, PostgreSQL). These allow unrestricted commercial use,
modification, and redistribution with only attribution requirements.

OTel Collector, PostgreSQL, Workbench, Open Terminal, MCPO, Authelia, Pydantic AI (`uv`/Python base; Pydantic AI, DBOS, FastAPI are all MIT/Apache-2.0)

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

---

## Enterprise Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| All licenses identified | Done | 15 container images catalogued |
| SBOM in standard format | Done | CycloneDX 1.6 JSON (`sbom.cdx.json`) |
| SBOM validated in CI | Done | `cyclonedx-cli validate` in lint workflow |
| No GPL-2.0-only (incompatible with Apache-2.0) | Pass | No GPL-2.0-only components |
| Copyleft components identified | Done | SearXNG (AGPL-3.0) — low risk when unmodified |
| Source-available components identified | Done | LangGraph API (ELv2) — opt-in; production self-host needs a commercial license key (MIT alternative: Pydantic AI) |
| Attribution requirements met | Done | License file included; component licenses in SBOM |
| Dependency update tracking | Done | Renovate (helm-values, pinDigests) for container images; Dependabot for GitHub Actions |
| Deep SBOM generation | Done | Syft scans all images in CI (`syft-sbom` job) |
| License review on update | Recommended | Add license check to Dependabot PR review process |

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
