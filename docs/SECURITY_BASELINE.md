# ai-stack — Security & Operations Baseline

**Chart version:** 2.12.0 · **Last reviewed:** 2026-06-14

This is the **operator-facing baseline**: the secure-by-default posture the chart
ships, the validated external standards each default maps to, and the commands to
verify conformance on a live release. It complements — and does not replace — the
contributor spec ([`AGENTS.md`](../AGENTS.md)), the threat model
([`SECURITY.md`](../SECURITY.md)), and the control registry
([`docs/governance/CONTROLS.md`](governance/CONTROLS.md)).

> **Normative language.** **MUST** = a baseline guarantee the chart enforces or
> the operator is required to provide; **SHOULD** = a strongly recommended
> production hardening the chart enables but does not force.

---

## 1. What the chart guarantees (and what you must provide)

The chart is **secure-by-default**, but Kubernetes splits responsibility. Two
controls live outside the chart and are **operator MUSTs**:

1. **Pod Security Admission.** The chart sets every pod/container `securityContext`
   to satisfy the **Restricted** profile, but the enforcing namespace label is
   applied *externally* (the chart does not create namespaces). Before install:

   ```bash
   kubectl label namespace ai-stack \
     pod-security.kubernetes.io/enforce=restricted \
     pod-security.kubernetes.io/enforce-version=latest --overwrite
   ```

2. **A NetworkPolicy-enforcing CNI.** The default-deny NetworkPolicies are inert
   unless your CNI enforces them (Cilium, Calico, Antrea, …). Verify the CNI
   enforces `NetworkPolicy` before relying on network isolation.

---

## 2. Security baseline — conformance matrix

Each row is a shipped default, the validated source it aligns with, and a
verification command (run against a deployed release in namespace `ai-stack`).

| # | Baseline requirement | ai-stack default | Validated source | Verify |
|---|----------------------|------------------|------------------|--------|
| B1 | Pods run unprivileged, non-root, no privilege escalation | `allowPrivilegeEscalation: false`, `runAsNonRoot: true` (documented exceptions in §3), `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault` | PSS *Restricted*; CIS K8s Benchmark §5.2; NIST SP 800-190 §4.4 | `kubectl get pods -n ai-stack -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].securityContext.allowPrivilegeEscalation}{"\n"}{end}'` |
| B2 | Read-only root filesystem where the image supports it | `readOnlyRootFilesystem: true` on Qdrant, Valkey, OTel Collector, ingestion-worker, Pydantic AI; others mount an `emptyDir` at `/tmp` and drop all caps (SearXNG alone re-adds `SETUID`/`SETGID` at startup) | CIS K8s §5.2.x; NSA/CISA *Immutable container filesystems* | `kubectl get deploy -n ai-stack -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.template.spec.containers[*].securityContext.readOnlyRootFilesystem}{"\n"}{end}'` |
| B3 | Per-component identity, no token automount | One `ServiceAccount` per component; `automountServiceAccountToken: false`; no Roles/RoleBindings shipped (no API access by default) | NSA/CISA *RBAC/least privilege*; CIS K8s §5.1; POL-001 | `kubectl get sa -n ai-stack` · `kubectl get rolebindings,clusterrolebindings -A -o wide \| grep ai-stack \|\| echo "none (expected)"` |
| B4 | Default-deny network, least-privilege allowlists | A namespace-wide `default-deny` (ingress **and** egress) + `allow-dns`, then per-component allowlists | NSA/CISA *Network separation*; CIS K8s §5.3; NIS2 Art. 21(2)(a); CTL-002 | `kubectl get networkpolicy -n ai-stack` · confirm a `…-default-deny` exists |
| B5 | No hardcoded secrets; stable across upgrades | Auto-generated keys via `ai-stack.persistentSecret` (lookup-stable), `helm.sh/resource-policy: keep`; `existingSecret`/external-store support | OWASP ASVS V6; CIS K8s §5.4; NIST SP 800-190 §4.2 | `helm template ai-stack . \| grep -iE "password\|secret-key\|api-key" \| grep -v secretKeyRef \|\| echo "no inline secrets"` |
| B6 | Images pinned by immutable digest | Every image carries `tag@sha256:…`; bumps managed by Renovate (`pinDigests: true`); parity enforced across `values.yaml` ↔ `sbom.cdx.json` ↔ `zarf.yaml` | SLSA *provenance*; CIS K8s §5.5; NIST SP 800-190 §3.1; ADR-002 | `kubectl get pods -n ai-stack -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' \| grep -c @sha256` |
| B7 | Resource requests **and** limits on every workload | Requests + limits set per component (lab/prod profiles); HPAs + PDBs for scalable/critical tiers | CIS K8s §5.x; NIST SP 800-190 §4.3 (resource bounds) | `kubectl get deploy -n ai-stack -o json \| jq -r '.items[] \| .metadata.name + " " + (.spec.template.spec.containers[0].resources.limits \| tostring)'` |
| B8 | Telemetry redaction before export | OTel `redaction` processor masks PII **and** credential shapes (bearer/JWT/PEM/provider-key) ahead of every exporter | GDPR Art. 5(1)(c); NIS2 Art. 21(2)(b); CTL-001 | `helm template ai-stack . --set global.otel.enabled=true \| grep -A2 blocked_values` |
| B9 | Supply-chain transparency | CycloneDX 1.6 SBOM committed + Syft deep SBOMs + Grype CVE scan in CI; SLSA build provenance on release | CRA Annex I; SLSA; NTIA SBOM minimum elements | inspect [`sbom.cdx.json`](../sbom.cdx.json); CI `lint.yaml` / `release.yaml` |
| B10 | Governance traceability on every workload | `assurance.platform/tier` + `boundary` labels and `control-refs` annotation on controller **and** pod, asserted in `tests/` | EU AI Act Art. 26; ISO/IEC 42001 §8; ADR-005 | `kubectl get deploy -n ai-stack -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.assurance\.platform/tier}{"\n"}{end}'` |

---

## 3. LLM-specific baseline (OWASP LLM Top 10)

The model-driven plane is the sharp edge. Treat model output, RAG documents, web
results, and tool output as **attacker-influenced** (indirect prompt injection →
excessive agency). See [`SECURITY.md`](../SECURITY.md) (Threat model).

| OWASP LLM risk | Baseline posture in ai-stack | Operator action |
|----------------|------------------------------|-----------------|
| **LLM01 Prompt injection** | No in-band tool/command allow-deny inside MCPO / Open Terminal (upstream images) | Constrain at the seams: tight egress, `runtimeClassName`, and a policy-aware MCP server you operate (LIMITATIONS L2) |
| **LLM02 Sensitive-information disclosure** | OTel credential+PII redaction (B8); secrets never in rendered manifests | Export audit telemetry to an off-cluster, append-only sink (LIMITATIONS L5) |
| **LLM06 Excessive agency** | Code-exec (Open Terminal) is opt-in, PSA-restricted, default-deny network; **SHOULD** set a hardened `runtimeClassName` (gVisor/Kata) | Set `openTerminal.runtimeClassName` + `mcpo.runtimeClassName`; budgets/HITL in agent code (LIMITATIONS L4) |
| **LLM08 Vector/embedding weaknesses** | Qdrant reachable only from allowlisted components; ingestion is decoupled | Per-tenant collections; validate ingest sources |
| **LLM10 Unbounded consumption** | Resource limits (B7); opt-in gateway token rate-limiting (`aiGateway.rateLimit`) | Enable `aiGateway` rate limits / quotas for multi-user (see [MULTI_USER.md](operations/MULTI_USER.md)) |

---

## 4. Documented deviations (intentional, tracked)

Deviations from a pure Restricted posture are **few, intentional, and annotated** —
never silent. Authoritative source: [`.kube-linter.yaml`](../.kube-linter.yaml)
(the only excluded checks) plus per-pod `assurance.platform/security-exception`
annotations.

| Deviation | Components | Why | Evidence |
|-----------|-----------|-----|----------|
| `runAsNonRoot: false` | Ollama, Tika, SearXNG | Upstream entrypoints require root (GPU/model mgmt; privilege-drop at startup) | `assurance.platform/security-exception` annotation on each pod; `.kube-linter.yaml` `run-as-non-root` exclusion |
| `readOnlyRootFilesystem: false` | Open WebUI, Ollama, Tika, SearXNG, Postgres, Authelia | Writable rootfs required at runtime; each drops all caps + `/tmp` `emptyDir` (SearXNG re-adds `SETUID`/`SETGID`) | `.kube-linter.yaml` `no-read-only-root-fs` exclusion |
| `env-var-secret` (kube-linter) | Authelia | The matches are `*_SECRET_FILE` **file paths**, not raw secrets — the recommended file-mount pattern | `.kube-linter.yaml` `env-var-secret` exclusion |

Every other default kube-linter / kubeconform check is **blocking** in CI.

---

## 5. Production hardening checklist (SHOULD)

- [ ] Namespace labelled `pod-security.kubernetes.io/enforce=restricted` (§1).
- [ ] CNI enforces NetworkPolicy (§1).
- [ ] `global.profile: prod` (HA replicas, topology spread, stricter limits, OTel on).
- [ ] PostgreSQL `mode: cnpg` with `backup.enabled: true` (Barman object store) for HA + PITR.
- [ ] Authelia enabled with `defaultPolicy: two_factor` for MFA at the edge.
- [ ] Code-exec components (`openTerminal`, `mcpo`) given a hardened `runtimeClassName`.
- [ ] OTel exported to an **off-cluster, append-only** audit sink (LIMITATIONS L5).
- [ ] External secret manager (ESO / Vault CSI) for rotation in regulated environments.
- [ ] TLS at the edge (cert-manager) and PostgreSQL `tls.mode: require` (cnpg/external).
- [ ] Per-tenant `ResourceQuota` / `LimitRange` and Open WebUI group model-access (see [MULTI_USER.md](operations/MULTI_USER.md)).

---

## 6. Validated references

- **CIS Kubernetes Benchmark** — <https://www.cisecurity.org/benchmark/kubernetes>
- **NSA/CISA Kubernetes Hardening Guide** — <https://www.cisa.gov/resources-tools/resources/kubernetes-hardening-guidance>
- **Kubernetes Pod Security Standards** — <https://kubernetes.io/docs/concepts/security/pod-security-standards/>
- **NIST SP 800-190 — Application Container Security** — <https://csrc.nist.gov/pubs/sp/800/190/final>
- **OWASP Top 10 for LLM Applications** — <https://genai.owasp.org/>
- **OWASP ASVS** — <https://owasp.org/www-project-application-security-verification-standard/>
- **SLSA — Supply-chain Levels for Software Artifacts** — <https://slsa.dev/>
- **CycloneDX** — <https://cyclonedx.org/> · **NTIA SBOM minimum elements** — <https://www.ntia.gov/page/software-bill-materials>
- **ISO/IEC 42001 (AI management systems)**; **EU AI Act**, **GDPR**, **NIS2**, **CRA** — mapped per control in [`docs/governance/CONTROLS.md`](governance/CONTROLS.md) and [`docs/compliance/EU_COMPLIANCE_CHECK.md`](compliance/EU_COMPLIANCE_CHECK.md).
