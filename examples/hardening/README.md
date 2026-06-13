# ai-stack hardening examples (operator-owned, out-of-chart)

These manifests are **examples**, not chart templates. The ai-stack chart ships a
secure-by-default floor (PodSecurity `restricted`, default-deny L3/L4
NetworkPolicies, per-component ServiceAccounts, digest-pinned images, SBOM +
blocking CVE gate). The controls here are **cluster-wide capabilities an operator
owns**, layered on top of that floor. They are deliberately kept out of the chart
(see [ADR-014](../../docs/architecture/ADR-014-supply-chain-runtime-enforcement.md)
and the [hardening guide](../../docs/operations/hardening-guide.md)).

Apply them with your own GitOps/kubectl after substituting the placeholders
(`<your-org>`, registry hosts, FQDNs) for your environment. Roll each out in
`audit`/permissive mode first, confirm a clean window, then switch to enforce.

| File | Control | Requires | Runbook |
|------|---------|----------|---------|
| [`kyverno-verify-images.yaml`](kyverno-verify-images.yaml) | B5 — admission signature verification | Kyverno >= 1.11 | B5 |
| [`cilium-fqdn-egress.yaml`](cilium-fqdn-egress.yaml) | B6 — FQDN-aware egress allowlist | Cilium CNI (FQDN policy) | B6 |
| [`istio-peerauthentication.yaml`](istio-peerauthentication.yaml) | B7 — in-cluster mTLS | Istio (or Linkerd, see guide) | B7 |

> These are starting points validated against the referenced project versions.
> Re-check them against the version you run; admission and CNI APIs evolve.
