# Changelog

All notable changes to the ai-stack Helm chart will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.0.0]: https://github.com/rmednitzer/ai-stack/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/rmednitzer/ai-stack/releases/tag/v1.0.0
