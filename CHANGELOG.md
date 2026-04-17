# Changelog

All notable changes to the ai-stack Helm chart will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Corrected README Helm Chart badge from v2.0.0 to v2.1.1 to match `Chart.yaml`
- Replaced plain-text section reference (`HOWTO.md §10`) in README Disaster Recovery with a proper markdown anchor link

### Added

- New `appVersion` and `Kubernetes` badges in README header
- Consolidated `Documentation` navigation table in README, linking HOWTO, CHANGELOG, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, Enterprise Evaluation, and SBOM

## [2.1.1] - 2026-04-12

### Changed

- Updated Ollama image tag from 0.20.3 to 0.20.5
- Updated SearXNG image tag from 2026.4.5-474b0a55b to 2026.4.11-9e08a6771
- Updated Open Terminal image tag from 0.11.32 to 0.11.34
- Bumped chart version from 2.1.0 to 2.1.1

### Fixed

- Synced zarf.yaml Ollama image from 0.20.2 to 0.20.5 to match values.yaml
- Synced SBOM Ollama version from 0.20.2 to 0.20.5 to match values.yaml
- Synced SBOM and zarf.yaml PostgreSQL version from 17-alpine to 18-alpine to match values.yaml
- Updated SBOM ai-stack chart metadata version from 1.0.0 to 2.1.1
- Refreshed SBOM timestamp to 2026-04-12
- Updated supported version in SECURITY.md to 2.1.x
- Bumped Zarf package metadata.version and all charts[].version from 1.0.0 to 2.1.1
- Regenerated SBOM serialNumber for the new BOM instance

## [2.1.0] - 2026-04-06

### Changed

- Updated Open WebUI image tag from v0.8.10 to v0.8.12
- Updated Ollama image tag from 0.18.2 to 0.20.2
- Updated Qdrant image tag from v1.17.0 to v1.17.1
- Updated SearXNG image tag from 2026.3.23-2c1ce3bd3 to 2026.4.5-474b0a55b
- Updated Open Terminal image tag from 0.11.27 to 0.11.32
- Updated Valkey image tag from 8.1.1 to 8.1.6
- Updated OTel Collector image tag from 0.148.0 to 0.149.0
- Updated Syft from v1.21.0 to v1.42.3 in CI pipeline
- Updated Grype from v0.91.0 to v0.110.0 in CI pipeline
- Bumped chart version from 2.0.0 to 2.1.0

### Fixed

- Fixed MCPO image tag from 0.2.0 to 0.0.20 to match actual GHCR release tags
- Fixed SBOM Python ingestion-worker version from 3.13-slim to 3.12-slim to match values.yaml
- Fixed SBOM Valkey version from 8.1 to 8.1.6 to match values.yaml pinned version

## [2.0.0] - 2026-04-06

### Changed

- Renumbered HOWTO table of contents and section headers for consistency
- Updated Ollama image tag from 0.18.1 to 0.18.2
- Updated Kubernetes support statement: 1.27+ (tested against 1.32)
- Corrected tier classification system reference: T0–T2
- Updated all compliance template versions from 1.0 to 2.0
- Updated supported version in SECURITY.md to 2.0.x
- Bumped chart version from 1.0.0 to 2.0.0

### Fixed

- Fixed subsection numbering in Upgrading, ArgoCD, and Compliance documentation sections
- Fixed numbering in EU_OPERATIONS_GUIDE roadmap
- Fixed section numbering inconsistencies throughout documentation

## [1.0.0] - 2026-03-01

### Added

- Initial release of the ai-stack Helm chart
- Open WebUI, Ollama, Qdrant, Tika, SearXNG, Valkey as core components
- Optional components: LangGraph, Workbench, MCPO, Open Terminal, Authelia, Ingestion Worker
- PostgreSQL support: standalone, CloudNativePG, and external modes
- PSA restricted baseline enforcement
- Default-deny NetworkPolicy with per-component allowlists
- OpenTelemetry Collector with PII redaction
- CycloneDX SBOM (sbom.cdx.json)
- CI pipeline: helm-lint, chart-testing, sbom-validate, syft-sbom, cve-scan, kubeconform
- EU compliance documentation: DPIA, DSAR, incident response, ROPA templates
- Governance controls registry (docs/governance/CONTROLS.md)
- ArgoCD application manifests for lab and production profiles
- Dependabot configuration for GitHub Actions
- Structured issue and PR templates

[2.1.1]: https://github.com/rmednitzer/ai-stack/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/rmednitzer/ai-stack/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/rmednitzer/ai-stack/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/rmednitzer/ai-stack/releases/tag/v1.0.0
