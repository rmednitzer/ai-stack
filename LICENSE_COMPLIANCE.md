# License Compliance — ai-stack

**Chart version:** 1.0.0 | **Last reviewed:** 2026-03-17

This document tracks licenses for all container images deployed by the
ai-stack Helm chart and evaluates compliance implications for enterprise use.

---

## SBOM

A machine-readable Software Bill of Materials is maintained in
[sbom.cdx.json](sbom.cdx.json) (CycloneDX 1.6, JSON). The SBOM is validated
in CI via `check-jsonschema` against the CycloneDX 1.6 JSON schema.

---

## License Matrix

| Component | Image | Version | License (SPDX) | Type | Default | Copyleft |
|-----------|-------|---------|----------------|------|---------|----------|
| Open WebUI | `ghcr.io/open-webui/open-webui` | v0.8.10 | MIT | Permissive | Enabled | No |
| Ollama | `ollama/ollama` | 0.17.7 | MIT | Permissive | Enabled | No |
| Qdrant | `qdrant/qdrant` | v1.13.2 | Apache-2.0 | Permissive | Enabled | No |
| Pipelines | `ghcr.io/open-webui/pipelines` | 0.1.2 | MIT | Permissive | Enabled | No |
| Tika | `apache/tika` | 3.0.0.0 | Apache-2.0 | Permissive | Enabled | No |
| SearXNG | `searxng/searxng` | 2026.3.10 | AGPL-3.0-or-later | Copyleft | Enabled | Yes |
| Valkey | `valkey/valkey` | 8.0 | BSD-3-Clause | Permissive | Enabled | No |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 0.116.0 | Apache-2.0 | Permissive | Conditional | No |
| LangGraph API | `docker.io/langchain/langgraph-api` | 0.2 | Elastic-2.0 (ELv2) | Source-available | Opt-in | No |
| PostgreSQL | `docker.io/library/postgres` | 16-alpine | PostgreSQL | Permissive | Opt-in | No |
| Workbench | `quay.io/jupyter/pytorch-notebook` | cuda12-python-3.11 | BSD-3-Clause | Permissive | Opt-in | No |
| Open Terminal | `ghcr.io/open-webui/open-terminal` | 0.1.2 | MIT | Permissive | Opt-in | No |
| MCPO | `ghcr.io/open-webui/mcpo` | 0.2.0 | MIT | Permissive | Opt-in | No |

**ai-stack chart license:** Apache-2.0

---

## License Analysis

### Permissive (no restrictions for enterprise use)

The majority of the stack uses permissive licenses (MIT, Apache-2.0,
BSD-3-Clause, PostgreSQL). These allow unrestricted commercial use,
modification, and redistribution with only attribution requirements.

**Components:** Open WebUI, Ollama, Qdrant, Pipelines, Tika, Valkey,
OTel Collector, PostgreSQL, Workbench, Open Terminal, MCPO

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

**Risk level: Medium (review before enabling)**

The Elastic License 2.0 permits self-hosted use but imposes restrictions:

- **Permitted**: Internal self-hosted deployment, modification for internal use,
  integration with other internal tools.
- **Prohibited**: Offering LangGraph Platform as a managed service to third
  parties (i.e., you cannot resell it as-a-service).
- **Not OSI-approved**: ELv2 is not considered open-source by the Open Source
  Initiative.

**Recommendation:** Acceptable for internal enterprise use. If your business
model involves offering AI orchestration as a service to external customers,
consult legal counsel before enabling LangGraph. The component is opt-in
(disabled by default) specifically to ensure conscious adoption.

---

## Enterprise Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| All licenses identified | Done | 13 components catalogued |
| SBOM in standard format | Done | CycloneDX 1.6 JSON (`sbom.cdx.json`) |
| SBOM validated in CI | Done | `cyclonedx-cli validate` in lint workflow |
| No GPL-2.0-only (incompatible with Apache-2.0) | Pass | No GPL-2.0-only components |
| Copyleft components identified | Done | SearXNG (AGPL-3.0) — low risk when unmodified |
| Source-available components identified | Done | LangGraph API (ELv2) — opt-in only |
| Attribution requirements met | Done | License file included; component licenses in SBOM |
| Dependency update tracking | Done | Renovate with digest pinning |
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

For automated SBOM generation from running containers, consider integrating
[Syft](https://github.com/anchore/syft) or
[Trivy](https://github.com/aquasecurity/trivy) into the CI pipeline to
produce deep SBOMs that include OS packages and language-level dependencies
within each container image.
