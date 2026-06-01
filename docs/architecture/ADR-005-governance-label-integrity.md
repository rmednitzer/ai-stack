# ADR-005 — Governance label integrity: canonical vocabulary, control-refs on every workload, and drift enforcement

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.8.0
- **Supersedes:** none (formalises the governance-label model introduced incrementally since 2.0.0)

---

## Context

`ai-stack` claims **governance-as-code**: every workload should be classified by
an operational tier and a trust boundary, and should point back to the
control/policy registry (`docs/governance/CONTROLS.md`). `AGENTS.md` §2.6 already
states the rule — *"Governance labels are mandatory on every Deployment:
`assurance.platform/tier`, `assurance.platform/boundary`, and
`assurance.platform/control-refs`."* A full-repo audit at 2.8.0 found that the
rule was only partly honoured, and that nothing enforced it:

1. **`control-refs` was missing on every workload except the OTel Collector —
   and the one that had it carried it as an *invalid label*.** A Kubernetes label
   value cannot contain commas, so the Collector's
   `assurance.platform/control-refs: "CTL-001,CTL-002"` **label** would be
   rejected by the API server on apply; `kubeconform`/`kube-linter` are
   schema-only and never caught it (OTel is opt-in, so it was rarely applied).
   Meanwhile `POL-001` (least-privilege identity) was referenced by *no*
   in-cluster resource at all, even though every workload implements it.
2. **The Valkey Deployment had no `boundary` label** — it carried only `tier`.
3. **The `boundary` value in 8 of 14 component docs did not match the rendered
   template.** v2.6.0 fixed only `mcpo` and `open-terminal`; the rest still
   documented the old coarse `internal`/`decision` vocabulary while the templates
   already emitted a richer set (`authentication`, `ingestion`, `model-serving`,
   `observability`, `retrieval`, `storage`, …).
4. **There was no canonical boundary vocabulary.** `CONTROLS.md` (CTL-002) still
   described boundaries as "(`internal`, `decision`)" — a vocabulary the
   templates had already outgrown — so docs, registry, and templates had no
   single source of truth to agree on.
5. **The SBOM package version had silently drifted** to `2.5.0` while the chart
   was `2.7.0`. The `sbom-validate` CI job checks image tag/digest parity but
   never checked `metadata.component.version`, so this version-bearing field
   (AGENTS.md §6) could rot unnoticed.

The common thread: the governance metadata was *aspirational* — asserted in prose
but neither complete nor machine-checked, so it drifted.

## Decision

1. **Canonical label vocabulary, templates as source of truth.** The valid
   `tier` (`T0`–`T2`) and `boundary` values are defined in one authoritative
   place — `docs/governance/CONTROLS.md` → *Governance label vocabulary*. The
   rendered templates are the source of truth; the per-component docs and the
   registry mirror them. The per-component values live once in the
   `ai-stack.governanceMap` helper (`templates/_helpers.tpl`), consumed by both
   the controller metadata and the pod template so the two cannot diverge. The
   coarse `internal`/`decision`-only boundary vocabulary is **retired**.

2. **`control-refs` is a mandatory annotation on every workload.** Every
   `Deployment` (plus the CloudNativePG `Cluster`/`Pooler` and the Valkey and
   OTel Collector Deployments) carries the `assurance.platform/control-refs`
   **annotation** — an annotation, not a label, because its comma-separated value
   is not a valid label value (this also fixes the Collector bug above). `tier`
   and `boundary` remain labels (valid values, selector-capable). The annotation
   references the controls the workload implements:
   - **`CTL-002`** — network-boundary governance (default-deny NetworkPolicy +
     tier/boundary classification): every workload.
   - **`POL-001`** — least-privilege identity (dedicated ServiceAccount, no token
     automount, restricted `securityContext`): every workload. This makes
     `POL-001` traceable in-cluster for the first time.
   - **`CTL-001`** — observability/redaction: the OTel Collector (the control's
     implementer), which therefore carries `CTL-001,CTL-002,POL-001`.

   The tier/boundary labels and the control-refs annotation are emitted on
   **both the controller object and its pod template** — Kubernetes does not copy
   controller metadata onto the Pods a controller creates, so a pod-scanning
   evidence pipeline would otherwise see none of it. The previously stale,
   profile-wide `assurance.platform/control-refs: "CTL-002"` in `values-prod.yaml`'s
   `global.podAnnotations` (which would overwrite the per-workload annotation on
   every prod pod, dropping `POL-001` everywhere and `CTL-001` on the Collector)
   is removed. CNPG `Cluster`/`Pooler` are CRs without a pod template, so they
   carry the metadata on the CR object only.

3. **Enforce both, so they cannot drift again.**
   - `tests/governance_labels_test.yaml` asserts the full tier/boundary/control-refs
     mapping for every workload. A new workload (or a relabelled one) fails the
     suite until the labels and this vocabulary agree.
   - `sbom-validate` gains a step asserting `sbom.cdx.json`
     `metadata.component.version` equals `Chart.yaml` `version` — closing the
     ADR-001 §Consequences follow-up that let the SBOM package version drift.

4. **Scope is metadata only.** No security default changes: PSA `restricted`,
   default-deny NetworkPolicy, per-component identity, and digest pinning are
   untouched. Adding labels does change rendered output, hence the `2.8.0` minor
   bump and the §6 version-bearing-artifact sync.

## Consequences

**Positive**

- Every workload now traces to the controls it implements, in both directions
  (`CONTROLS.md` → templates via *Implemented By*, templates → `CONTROLS.md` via
  `control-refs`). Evidence-pipeline / governance scanners can map a running pod
  to its CTL/POL basis without external lookup tables.
- The templates, the component docs, and the registry can no longer silently
  disagree — the unittest is the contract.
- A whole class of "version-bearing artifact rotted unnoticed" bugs is closed for
  the SBOM package version.

**Negative / accepted trade-offs**

- The canonical vocabulary must be maintained as components are added; a new
  boundary value means a `CONTROLS.md` table entry and a test case. This is
  deliberate friction — it is what keeps the model honest.
- `control-refs` is a coarse mapping (workload → control), not a per-setting
  attestation; it says *which* controls a workload implements, not that each is
  correctly configured. The security-specific unittests (restricted context, no
  automount, scoped CORS, default-deny netpol) remain the per-setting evidence.

## Related artifacts

- `docs/governance/CONTROLS.md` — *Governance label vocabulary*; CTL-002 / POL-001 rows
- `templates/_helpers.tpl` — `ai-stack.governanceMap` / `governanceLabels` / `governanceControlRefs` (single source)
- `templates/**` — governance metadata on each workload's controller and pod template; Valkey `boundary`
- `values-prod.yaml` — removed the redundant profile-wide `control-refs` pod annotation
- `tests/governance_labels_test.yaml` — the enforcement suite (controller + pod)
- `.github/workflows/lint.yaml` — `sbom-validate` package-version parity step
- `docs/components/*.md` — boundary values aligned to templates; `Control refs` lines
- `AGENTS.md` §6 — SBOM package-version added to the version-bump checklist
