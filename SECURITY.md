# Security Policy — ai-stack

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.1.x | Yes |
| 2.0.x | No |

## Reporting a Vulnerability

If you discover a security vulnerability in the ai-stack Helm chart, please
report it responsibly.

### How to Report

1. **Preferred:** Use [GitHub Security Advisories](https://github.com/rmednitzer/ai-stack/security/advisories/new) to report privately
2. **Alternative:** Email **r.mednitzer@outlook.com** with subject `[ai-stack] Security vulnerability report`
3. **Include:**
   - Description of the vulnerability
   - Steps to reproduce
   - Affected component(s) and version(s)
   - Potential impact assessment
   - Suggested fix (if any)

### What to Expect

| Step | Timeline |
|------|----------|
| Acknowledgement of report | Within **48 hours** |
| Initial triage and severity assessment | Within **5 business days** |
| Fix development and testing | Depends on severity (see below) |
| Coordinated disclosure | After fix is available |

### Severity Response Times

| Severity | Fix Target | Disclosure |
|----------|-----------|------------|
| Critical (active exploitation, data breach risk) | **48 hours** | After fix deployed |
| High (exploitable with moderate effort) | **7 days** | After fix released |
| Medium (limited impact or difficult to exploit) | **30 days** | After fix released |
| Low (informational, hardening) | **90 days** | With next scheduled release |

### Scope

This policy covers:

- The ai-stack Helm chart (templates, values, helpers)
- CI/CD pipeline configuration (`.github/workflows/`)
- Documentation that could lead to insecure configurations

This policy does **not** cover vulnerabilities in upstream container images
(Open WebUI, Ollama, Qdrant, etc.). Report those to their respective projects.
However, if an upstream vulnerability creates risk in the ai-stack deployment
context, we welcome reports so we can issue guidance or workarounds.

### Coordinated Vulnerability Disclosure (CVD)

Per CRA Art. 13(8) and industry best practice:

1. We will work with reporters to understand and reproduce the vulnerability
2. We will develop and test a fix
3. We will coordinate disclosure timing with the reporter
4. We will credit the reporter (unless they prefer anonymity)
5. We will not take legal action against good-faith security researchers

### Bug Bounty

There is currently no bug bounty program. We gratefully acknowledge all
responsible disclosures in our release notes (with permission).

## Security Controls

The ai-stack implements the following security controls by default:

- **Pod Security Admission:** Restricted baseline (`runAsNonRoot`, `drop: ALL`,
  `seccompProfile: RuntimeDefault`)
- **Network isolation:** Default-deny NetworkPolicy with per-component allowlists
- **Secret management:** Auto-generated 64-byte keys; external secret manager support
- **Service account isolation:** Per-component, `automountServiceAccountToken: false`
- **Read-only filesystem:** Enforced where possible (Qdrant, Valkey, Tika, SearXNG, OTel)
- **Supply chain security:** CycloneDX SBOM, Syft deep SBOMs, CVE scanning (Grype),
  Dependabot for GitHub Actions; container images tracked manually
- **PII redaction:** OTel Collector strips email, SSN, and credit card patterns
- **Telemetry opt-out:** `DO_NOT_TRACK=true`, `ANONYMIZED_TELEMETRY=false`

For details, see [ENTERPRISE_EVALUATION.md](docs/enterprise/ENTERPRISE_EVALUATION.md) and
[LICENSE_COMPLIANCE.md](docs/compliance/LICENSE_COMPLIANCE.md).
