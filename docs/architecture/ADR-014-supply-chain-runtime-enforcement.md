# ADR-014 — Supply-chain and runtime enforcement: blocking CVE gate, chart signing, and operator-owned admission/egress/mTLS

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive — a CI gate change, a release-workflow signing
  step, and operator-facing examples + a guide; no chart template, image,
  `values.yaml`, SBOM, or `zarf.yaml` change, and no L1 / template-contract
  signature is removed or altered)
- **Relates to:** [ADR-002](ADR-002-image-digest-pinning.md) (digest pinning),
  [ADR-010](ADR-010-consolidate-dependency-automation-on-renovate.md) (Renovate)

---

## Context

The chart's remediation runbook (`docs/operations/RUNBOOK-remediation.md`, ADR-012)
deferred four supply-chain and runtime hardening items. This ADR records how they
are addressed.

- **B4 — the container CVE gate did not block.** `cve-scan` ran Grype with
  `--fail-on critical` per image but captured the result into a `::warning::` and
  never failed the step; critical CVEs were visible in artifacts but advisory only.
- **B5 — images were not signed, and nothing verified signatures at admission.**
  Images are digest-pinned and SBOM-attested with CI parity, but carry no
  cryptographic signature and no admission-time verification.
- **B6 — egress was port-level, not host-level.** The chart's NetworkPolicies are
  L3/L4 default-deny, but native `NetworkPolicy` cannot name destination FQDNs, so
  the internet-egress rules open `:443`/`:80` to any host.
- **B7 — inter-component traffic was plaintext.** NetworkPolicy governs
  reachability, not encryption or workload identity.

The dividing question for each: does it belong **inside the chart**, or is it a
**cluster-wide capability the operator owns**? The chart's scope is a single Helm
release; an admission controller, a CNI, and a service mesh are cluster
singletons that one chart must not assume or install.

Constraints: never weaken a default; surgical change over rewrite; `values.yaml`
is the source of truth; respect the deliberate CI cost design (image pulls run on
`push`, not every PR).

## Decision

1. **B4 — make the CVE gate blocking (in CI).** The `cve-scan` job now exits
   non-zero when any image has a critical CVE (runbook option (a): fail on `push`,
   so the signal is a red `main` post-merge, preserving the push-only cost
   design). The relief valve is a time-boxed exception file, `.grype.yaml`: an
   `ignore:` entry must carry a linked advisory and an `expires: YYYY-MM-DD` (UTC)
   comment. A new guard, `.github/scripts/check_grype_exceptions.py`, runs first in
   the job and fails the build if any exception is missing an expiry, malformed, or
   past it, so an exception cannot silently become permanent.

2. **B5 — sign the chart in the release workflow; verify at admission out-of-chart.**
   `release.yaml` signs the published Helm chart OCI artifact with **cosign keyless**
   (Sigstore Fulcio + Rekor) via the workflow's OIDC identity — ai-stack ships a
   *chart*, not images, so the chart artifact is what this repo can authentically
   sign. Admission-time verification of the *workload* images is operator-owned: an
   example Kyverno `verifyImages` `ClusterPolicy`
   (`examples/hardening/kyverno-verify-images.yaml`, `Audit` by default) plus the
   guide document the mirror-and-sign pattern needed to verify third-party images.

3. **B6 and B7 — ship as operator-owned examples + a guide.** FQDN egress
   (Cilium `toFQDNs`) and in-cluster mTLS (Istio `PeerAuthentication` / Linkerd
   injection) are delivered as example manifests under `examples/hardening/` and a
   `docs/operations/hardening-guide.md`, layered on the chart's L3/L4 default-deny
   and per-component ServiceAccount identities. They are not chart templates.

4. **Governance home.** B4–B7 are CI/release/cluster controls with no rendered
   manifest to annotate, so they trace through this ADR, `SECURITY.md`, and the
   runbook (each item's own "Tracking" line), not the per-component
   `assurance.platform/control-refs` annotation (which is for chart workloads).
   This is the chart's established treatment of CI/release controls.

## Consequences

**Positive**

- A critical CVE in a pinned image now blocks the pipeline instead of emitting an
  ignorable warning, while the time-boxed exception file keeps an unfixable
  upstream advisory from wedging releases and the guard keeps exceptions honest.
- Released charts are cryptographically verifiable (keyless, no key to manage),
  closing the gap between "digest-pinned + SBOM-attested" and "signed".
- Operators get correct, adaptable starting points for admission, FQDN egress, and
  mTLS, plus a rollout order, instead of scattered prose.

**Negative**

- The blocking gate runs on `push`, so the first failing signal is a red `main`
  (not a blocked PR); a latent critical in a currently-pinned image will surface
  there and must be fixed or time-boxed. This is the accepted cost of the
  push-only design (option (a)); a PR-scoped gate (option (b)) was rejected for
  its image-pull cost on every PR.
- cosign keyless signing depends on Sigstore public-good infrastructure (Fulcio,
  Rekor) being reachable from the release runner.
- B5 admission, B6, and B7 require cluster capabilities (Kyverno, Cilium, a mesh)
  the operator must install and own; the chart cannot guarantee they are present.

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change: the work is a CI
  gate, a release step, examples, and docs. It accumulates in `CHANGELOG.md`
  `[Unreleased]` for the next release.
- The `sigstore/cosign-installer` action is SHA-pinned with a version comment per
  the repo convention; Renovate (ADR-010) keeps it current.

## Alternatives considered and rejected

- **B4 option (b): gate on PRs (scan only changed images).** Rejected as the
  default: it contradicts the deliberate push-only cost design (image pulls are
  expensive and hit registry rate limits) and adds diff-parsing complexity. Option
  (a) plus the exception file is the runbook's ready patch and the lighter gate.
- **B4 with no exception mechanism.** Rejected: a single unfixable upstream
  critical would wedge all releases, pressuring a revert of the gate itself. A
  time-boxed, guard-enforced exception is the safety valve that keeps the gate on.
- **Sign every workload image in this repo.** Not possible: ai-stack does not build
  the images; it references third-party ones. Signing the chart artifact is what
  this repo can authentically attest; verifying workload images is the operator's
  mirror-and-sign responsibility, documented rather than faked.
- **Bundle Kyverno/Cilium/a mesh into the chart (templates or subcharts).**
  Rejected: these are cluster singletons; a single application chart installing or
  presuming them would collide with cluster-wide operator choices and break the
  "one Helm release" scope. Examples + a guide keep ownership where it belongs.
- **A long-lived cosign key in a Secret.** Rejected in favour of keyless OIDC: no
  key material to store, rotate, or leak, and a transparency-log record by default.

## Revisit triggers

- A shipped overlay or a consumer begins mirroring images into a known registry
  with a stable signing identity — promote the Kyverno example toward an enforced,
  parameterised default and consider verifying the chart signature at install.
- Sigstore changes its keyless flow or endpoints, or the project adopts a
  long-lived KMS key for an air-gapped release — revisit the signing step.
- A blocking PR-scoped CVE gate becomes affordable (registry mirror / cache) —
  revisit B4 option (b) for a pre-merge signal.
- B7 mesh adoption lands in a shipped overlay — revisit whether the Qdrant p2p
  port (ADR-013) should require mesh mTLS (`QDRANT__CLUSTER__P2P__ENABLE_TLS`).
