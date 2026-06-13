# ADR-012 — Open WebUI HA shared-database guard, CTL-003 execution-isolation control, and the remediation runbook

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive — a fail-closed render guard, a new governance
  control over already-enforced behaviour, a corrected production default, and a
  tracked remediation runbook; no existing render changes shape, and no L1 /
  template-contract signature is removed or altered)

---

## Context

An in-depth architecture review of the chart surfaced one shipped-broken default,
one traceability gap, and a backlog of larger remediations that needed a single
operator-facing plan. This ADR records the subset executed in-chart now and
anchors the rest in a tracked runbook.

1. **Production high-availability was silently broken.** `values.yaml` documents
   `postgres.enabled: true` as a **core dependency** — "Open WebUI HA state
   (`DATABASE_URL`) + LangGraph/DBOS checkpoints. Disable only for an ephemeral
   single-pod lab." The production overlay (`values-prod.yaml`) nonetheless set
   `postgres.enabled: false` while running Open WebUI at `replicaCount: 2` with
   autoscaling to 5. `ai-stack.webuiHaEnv` only emits `DATABASE_URL` when
   `postgres.enabled`, so every Open WebUI replica fell back to a private per-pod
   SQLite file: users, chats, and settings split across pods depending on which
   replica served the request. The misconfiguration rendered cleanly and failed
   only at runtime, with data-integrity loss.

2. **Model-driven execution isolation was enforced but not a named control.** The
   chart already contains the components that act on model-influenced input
   (Open Terminal runs model-generated commands; MCPO brokers model tool calls):
   opt-in hardened `runtimeClassName`, a CORS allowlist that never resolves to
   `*`, a bounded root filesystem, `automountServiceAccountToken: false`, and
   default-deny egress. None of this traced to a `CTL`/`POL` identifier in the
   registry, so the control could not be referenced from an annotation, a test,
   or an audit.

3. **Larger remediations had no single home.** Multi-node Open WebUI file
   storage, the opt-in Qdrant collection bootstrap, per-tenant retrieval
   isolation and GDPR erasure, a blocking CVE gate, supply-chain signing and
   admission, FQDN egress, distributed Qdrant, and disaster-recovery backups are
   each real but out of scope for one surgical change. They needed an
   operator-executable runbook rather than scattered TODOs.

Constraints that shaped the decision: never weaken a default; `values.yaml` is
the source of truth; surgical change over rewrite; every security-relevant
template change carries a `tests/` assertion; governance-as-code is load-bearing.

## Decision

1. **Fail-closed HA guard.** Add `ai-stack.openwebuiHaGuard` (in
   `templates/_helpers.tpl`), invoked from `templates/openwebui/deployment.yaml`.
   It calls `fail` at render time when Open WebUI is scaled
   (`openwebui.replicaCount > 1` **or** `openwebui.autoscaling.enabled`) **and**
   `postgres.enabled` is false, with an actionable message. It emits nothing on
   success, so no rendered manifest changes. The guard fires only on the
   genuinely unsafe topology: it does **not** trip the single-replica ephemeral
   lab (`postgres.enabled: false`, one replica), which stays valid.

2. **Correct the production default.** Set `postgres.enabled: true` in
   `values-prod.yaml` — restoring the documented core dependency the overlay had
   disabled. The overlay already fully configures `postgres.mode: cnpg` (3
   instances, pooler, TLS `require`, monitoring), so this enables the HA Postgres
   the overlay was already built for. Because `mode: cnpg` now renders
   `postgresql.cnpg.io/v1` `Cluster`/`Pooler` (and `ScheduledBackup` when backups
   are on) in the production profile, those CR kinds are added to the
   `kubeconform -skip` lists in `.github/workflows/lint.yaml`, matching the
   chart's established practice for operator-owned CRDs.

3. **CTL-003 — model-driven execution isolation.** Add `CTL-003` to the control
   registry (`docs/governance/CONTROLS.md`) and to the `README.md` governance
   table. Open Terminal and MCPO reference it via `ai-stack.governanceMap`
   (`CTL-002,CTL-003,POL-001`), so the `control-refs` annotation propagates to
   both the controller and the pod template through the existing helpers.
   `tests/governance_labels_test.yaml` is extended to pin the new value.

4. **Remediation runbook.** Land `docs/operations/RUNBOOK-remediation.md` as the
   tracked, operator-executable plan: it records the fixes above as completed
   phases with verification commands, and documents every deferred item (finding,
   evidence, severity, fix design, ready-to-apply patch, validation, rollback).

## Consequences

**Positive**

- The production overlay deploys highly-available Open WebUI correctly instead of
  splitting state; the guard prevents the same misconfiguration in any
  operator-authored values, with a message that names the fix.
- Execution isolation is now a first-class, referenceable control: annotated on
  the attack-surface components, asserted by a test, and traceable to AI Act
  Art. 15 / NIS2 / CRA in the registry.
- The deferred work has a single, reviewable home with concrete operator steps.

**Negative**

- The production profile now requires the CloudNativePG operator (v1.25+) to be
  installed before deploy — already a documented prerequisite of `mode: cnpg`,
  but now load-bearing for the shipped overlay rather than opt-in.
- The guard is a hard render failure. An operator who deliberately wants
  multi-replica Open WebUI on an external database they wire by other means must
  keep `postgres.enabled: true` (the flag that gates `DATABASE_URL`); the guard
  is intentionally coupled to that single flag.

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change: the work is
  template logic, values, governance metadata, tests, and docs. It accumulates in
  `CHANGELOG.md` `[Unreleased]` for the next release.
- The guard adds no rendered fields; the all-optional and lab profiles are
  unaffected (they keep `postgres.enabled: true` and a single Open WebUI replica).

## Alternatives considered and rejected

- **Guard only, leave the prod overlay broken.** Rejected: the guard would make
  the shipped production profile fail to render (and CI's prod lint fail), and the
  overlay would still promise HA it cannot deliver. The default must be correct.
- **Downgrade prod to a single Open WebUI replica.** Rejected: the overlay's
  intent (autoscaling 2–5, topology spread) is HA; the cnpg block was configured
  precisely to back it. Enabling the database honours that intent rather than
  abandoning it.
- **Bootstrap the Qdrant `documents` collection from a chart Job in this change.**
  Rejected for now: only the opt-in ingestion-worker→Pydantic AI path needs it
  (Open WebUI manages its own Qdrant collections), and a chart Job would hard-code
  the embedding dimension separately from the model, risking drift. The
  worker-side ensure-collection fix is specified in the runbook, where it can land
  with the right test home.
- **Make the CVE gate blocking in this change.** Rejected for now: `cve-scan`
  runs on `push` only by deliberate cost/rate-limit design and swallows Grype's
  exit code; turning it blocking interacts with that tradeoff and belongs in the
  runbook with the PR-vs-push analysis, not a drive-by flip.
- **Add `POL-002` (credential management) alongside CTL-003.** Deferred to the
  runbook: it would touch the `control-refs` of most secret-bearing components and
  their tests at once; the value is real but the churn is wider than this surgical
  change warrants.

## Revisit triggers

- Open WebUI gains first-class object storage such that multi-node file
  durability no longer needs RWX/S3 — revisit the runbook HA recipe and whether
  the guard should also assert on the PVC access mode.
- The opt-in RAG path (ingestion worker + Pydantic AI) is enabled in a shipped
  overlay — promote the Qdrant collection-bootstrap fix out of the runbook.
- A second control joins the execution-isolation family (e.g. a bundled
  policy-aware MCP broker), or `POL-002` is formalised — fold both into the
  registry and the `governanceMap` together.
