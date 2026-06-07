# Security Policy — ai-stack

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.11.x | Yes |
| 2.10.x | Yes |
| ≤ 2.9.x | No |

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

## Threat model

The chart serves an LLM application: Open WebUI consumes web search (SearXNG)
and RAG documents (Qdrant) and can reach tools through MCPO, and the agentic
runtimes (LangGraph / Pydantic AI) drive those same tools. **Treat model inputs
and tool/RAG/web content as attacker-influenced** — the primary adversary is an
*indirect prompt injection* (a poisoned web result, document, or tool output)
that steers the model into unintended tool calls or commands. This is the
OWASP LLM "excessive agency" class, and it is most acute at the **tool/command
plane**: MCPO (the shared tool gateway) and Open Terminal (model-driven code
execution).

**What the platform controls do:** PodSecurity `restricted`, default-deny
NetworkPolicies, per-component ServiceAccounts, secret redaction in the OTel
pipeline, and (opt-in) a hardened `runtimeClassName` for the code-execution
components constrain *blast radius* — a persuaded model still operates inside an
operator-defined envelope.

**What they do not do (residual risk):** the chart does not place an in-band
command/tool allow-deny policy *inside* MCPO or Open Terminal (those are
upstream images), and standard container isolation is **not** a sandbox against
hostile code. For untrusted / model-generated code, set
`openTerminal.runtimeClassName` (and `mcpo.runtimeClassName`) to a hardened
RuntimeClass (gVisor / Kata); restrict egress; keep limits tight; and ship audit
telemetry off-cluster. If you expose MCPO / Open Terminal beyond the cluster,
front the route with Authelia (OIDC / ForwardAuth) rather than the static API
key alone. relay-shell-style tiered authority and contract / budget governance
for agent tool-use are recommended *patterns* to apply in servers and runtimes
you operate separately; they are intentionally **not bundled** into this chart.
Per-component scope boundaries and known gaps are tracked in
[LIMITATIONS.md](LIMITATIONS.md).

## Security Controls

The ai-stack implements the following security controls by default:

- **Pod Security Admission:** Restricted baseline (`runAsNonRoot`, `drop: ALL`,
  `seccompProfile: RuntimeDefault`)
- **Sandbox runtime (opt-in):** `runtimeClassName` on Open Terminal and MCPO for
  a gVisor / Kata kernel boundary around model-generated code
- **Network isolation:** Default-deny NetworkPolicy with per-component allowlists
- **Secret management:** Auto-generated 64-byte keys; external secret manager support
- **Service account isolation:** Per-component, `automountServiceAccountToken: false`
- **Governance traceability:** Every workload carries `assurance.platform/tier`
  and `boundary` labels plus a `control-refs` annotation (on both the controller
  and its pods) that resolve to the CTL/POL registry in
  [CONTROLS.md](docs/governance/CONTROLS.md)
- **Read-only filesystem:** Enforced where possible (Qdrant, Valkey, Tika, SearXNG, OTel)
- **CORS:** Open Terminal origins are scoped to the Open WebUI origin (never `*`)
- **Supply chain security:** CycloneDX SBOM, Syft deep SBOMs, CVE scanning (Grype),
  Dependabot for GitHub Actions; container images tracked manually
- **PII + secret redaction:** OTel Collector strips email, SSN, and credit-card
  patterns plus bearer tokens, JWTs, private keys, and provider API-key shapes
- **Telemetry opt-out:** `DO_NOT_TRACK=true`, `ANONYMIZED_TELEMETRY=false`

For details, see [ENTERPRISE_EVALUATION.md](docs/enterprise/ENTERPRISE_EVALUATION.md) and
[LICENSE_COMPLIANCE.md](docs/compliance/LICENSE_COMPLIANCE.md).
