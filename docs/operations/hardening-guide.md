# Hardening guide — supply chain and runtime enforcement

This guide covers the security controls that live **at the CI/release and cluster
layers** rather than inside the chart's rendered manifests: the blocking CVE gate
(B4), image signing and admission verification (B5), FQDN-aware egress (B6), and
in-cluster mTLS (B7). They are the upper layers of defence in depth on top of the
chart's secure-by-default floor (PodSecurity `restricted`, default-deny L3/L4
NetworkPolicies, per-component ServiceAccounts, digest-pinned images, SBOM
parity). Decision record: [ADR-014](../architecture/ADR-014-supply-chain-runtime-enforcement.md).
Example manifests: [`examples/hardening/`](../../examples/hardening/).

The chart deliberately does **not** bundle B5–B7: they are cluster-wide
capabilities an operator owns (an admission controller, a CNI, a service mesh),
not per-release chart settings. The chart provides the identities and metadata
they build on (per-component ServiceAccounts, consistent labels) and these
ready-to-adapt examples.

## B4 — Blocking container CVE gate (in CI)

**What it does.** The `cve-scan` job (`.github/workflows/lint.yaml`) scans every
image referenced in `values.yaml` with Grype and **fails the build on any critical
CVE** (`--fail-on critical`, then a non-zero exit on the aggregate count). It runs
on `push` to `main` (post-merge), matching the deliberate cost/rate-limit design
that keeps expensive image pulls off every PR. The signal is therefore a red
`main`, not a blocked PR.

**Time-boxed exceptions.** A critical CVE with no available upstream fix must not
wedge releases indefinitely, but an ignore must not become a silent, permanent
hole either. The relief valve is [`.grype.yaml`](../../.grype.yaml): add an
`ignore:` entry with a comment carrying a linked advisory and an
`expires: YYYY-MM-DD` (UTC) date. The `check_grype_exceptions.py` guard
(`.github/scripts/`) fails the build if any exception is missing an expiry, has a
malformed date, or is past it. Example:

```yaml
ignore:
  # reason: no upstream fix yet | advisory: https://github.com/.../GHSA-xxxx | expires: 2026-09-01
  - vulnerability: CVE-2026-12345
```

Prefer bumping the affected image (Renovate raises those PRs) over adding an
exception. Keep the list empty in the normal case.

**Rollback.** Restore the warning-only summary tail in the `cve-scan` job.

## B5 — Image signing and admission verification

**Signing (in the release workflow).** `release.yaml` signs the published Helm
chart OCI artifact with **cosign keyless** (Sigstore Fulcio + Rekor) using the
workflow's OIDC identity (`id-token: write`). No long-lived key: the signature and
short-lived certificate are recorded in the public transparency log. Verify a
release:

```bash
cosign verify ghcr.io/<owner>/charts/ai-stack@<digest> \
  --certificate-identity-regexp '^https://github.com/<owner>/ai-stack/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

**Admission (operator-owned).** Enforce signatures at deploy time with a cluster
admission policy. [`examples/hardening/kyverno-verify-images.yaml`](../../examples/hardening/kyverno-verify-images.yaml)
is a Kyverno `verifyImages` `ClusterPolicy` scoped to the ai-stack namespace.

Scope reality: you can only keyless-verify an identity you trust. The chart
deploys third-party images (qdrant, ollama, tika, ...); to verify them, **mirror
the upstream images into your own registry and sign them with your CI**, then
verify that identity. Images you have not signed must be mirrored+signed or left
to the chart's digest-pin + CVE gate. Start the policy in `Audit`, confirm the
report is clean across your full image set, then switch to `Enforce`.

**Rollback.** Set the policy back to `Audit` (or remove it). Signing in the
release workflow is additive and never blocks a deploy on its own.

## B6 — FQDN-aware egress

**What it adds.** The chart's NetworkPolicies are L3/L4 default-deny, but native
`NetworkPolicy` cannot name destination hosts, so the internet-egress rules open
`:443`/`:80` to any host. A persuaded workload (indirect prompt injection) could
reach an arbitrary external host. An FQDN/DNS-aware layer narrows egress to a named
allowlist while keeping the chart's port-level default-deny as the floor.

[`examples/hardening/cilium-fqdn-egress.yaml`](../../examples/hardening/cilium-fqdn-egress.yaml)
is a Cilium `CiliumNetworkPolicy` with `toFQDNs` for the Pydantic AI runtime (PyPI
+ model providers). Cilium must see DNS to learn the IPs behind the names, so the
DNS snoop rule is mandatory and precedes the FQDN rule. Duplicate the pattern,
adjusting the `endpointSelector` and FQDNs, for langgraph, searxng, and the
ingestion worker. An Istio egress gateway with `ServiceEntry` + `Sidecar`
allowlists is the mesh-native equivalent.

**Rollback.** Remove the FQDN policy; the chart's L3/L4 default-deny remains.

## B7 — In-cluster mTLS

**What it adds.** Inter-component traffic is plaintext over ClusterIP; the chart's
NetworkPolicies govern reachability, not encryption or workload identity. A service
mesh adds automatic mTLS using the chart's per-component ServiceAccount identities,
so traffic between components is encrypted and peer-authenticated.

- **Istio:** label the namespace for injection
  (`kubectl label namespace ai-stack istio-injection=enabled`), restart the
  workloads, then apply
  [`examples/hardening/istio-peerauthentication.yaml`](../../examples/hardening/istio-peerauthentication.yaml).
  Roll out `PERMISSIVE` first, confirm telemetry shows mTLS, then switch to
  `STRICT`.
- **Linkerd:** annotate the namespace
  (`kubectl annotate namespace ai-stack linkerd.io/inject=enabled`) and restart;
  Linkerd enables mTLS between meshed pods automatically, with a lighter footprint
  and no `PeerAuthentication` object. Verify with `linkerd viz edges`.

**Rollback.** Remove the mesh injection label/annotation (and the
`PeerAuthentication` for Istio) and restart.

## Rollout order

A sensible sequence on a fresh cluster:

1. **B4** is already on in CI; keep `.grype.yaml` empty and bump images when
   Renovate raises CVE fixes.
2. **B7 mTLS** in `PERMISSIVE`/meshed mode (lowest blast radius; observe first).
3. **B6 FQDN egress** per egress-heavy component, in observation, then enforce.
4. **B5 admission** in `Audit`, then `Enforce` once your signed image set is
   complete.
5. Promote B7 to `STRICT`.

See also [SECURITY.md](../../SECURITY.md) (threat model) and
[RUNBOOK-remediation.md](RUNBOOK-remediation.md) (B4–B7 findings and validation).
