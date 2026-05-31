# CLAUDE.md

Claude-specific collaboration guide for `ai-stack`. The full operating spec and
repo map live in [`AGENTS.md`](AGENTS.md); read it first. This file is the
behavior overlay.

## Objective

Evolve a single Helm chart that deploys a **governed, secure-by-default** AI
inference stack for EU-regulated Kubernetes — without weakening its governance
(`docs/governance/CONTROLS.md`), its security defaults, or its supply-chain
parity (`values.yaml` ↔ `sbom.cdx.json` ↔ `zarf.yaml`).

## Core behavior expectations

1. **Surgical changes over broad rewrites.** Reuse the named templates in
   `templates/_helpers.tpl` (`restrictedSecurityContext`, `persistentSecret`,
   `componentName`, `netpolEgress`, …).
2. **Render before you claim.** A change is not real until `helm template`
   (lab / prod / all-optional), `helm lint`, and `helm unittest .` are green.
3. **Governance-as-code is load-bearing.** Keep the `assurance.platform/*`
   labels accurate and traceable to `CONTROLS.md`; add a `tests/` assertion for
   any security-relevant template change.
4. **`values.yaml` is the source of truth.** Changing an image syncs the SBOM
   and `zarf.yaml` in the same PR (ADR-001/002); bumping `Chart.yaml` triggers
   the full version-bump checklist in `AGENTS.md` §6 (CHANGELOG, README badge,
   `zarf.yaml`, and the version-bearing docs — `zarf dev lint` will not catch a
   stale Zarf version, so do it by hand).
5. **Never weaken a default.** PSA `restricted`, default-deny NetworkPolicy,
   per-component ServiceAccount + no token automount, digest-pinned images,
   no hardcoded secrets, no wildcard CORS on the code-executing components.

## Required development loop

1. Read the impacted template(s), `values.yaml`, and `_helpers.tpl`.
2. Make the minimal change; reuse helpers.
3. Gate locally:
   ```
   helm lint . && helm lint . -f values.yaml -f values-prod.yaml
   helm template ai-stack . >/dev/null
   helm template ai-stack . -f values.yaml -f values-prod.yaml >/dev/null
   helm unittest .
   make check-links            # when docs change
   ```
4. Add/adjust `tests/` for changed behavior; update `CHANGELOG.md` and the
   affected `docs/`.
5. Complete the version-bump checklist (`AGENTS.md` §6) if `Chart.yaml` changed.

## Coding guidance

- **Security posture:** treat the model-driven plane (MCPO, Open Terminal) as
  the attack surface — model/RAG/web input is attacker-influenced. See
  `SECURITY.md` (Threat model) and `LIMITATIONS.md`. Prefer a hardened
  `runtimeClassName` for code execution; keep OTel redaction covering secrets.
- **Decisions:** record cross-cutting choices as an ADR in
  `docs/architecture/` (see `AGENTS.md` §7). ADR "version at acceptance" lines
  are historical — never rewrite them.
- **Errors of omission to avoid:** an unsynced `zarf.yaml`/SBOM after an image
  or version change, a missing governance annotation, or a security claim with
  no `tests/` assertion behind it.

## When uncertain

Default to: (1) preserving security defaults and governance traceability,
(2) syncing the version-bearing artifacts, (3) adding a `tests/` assertion and
docs, and (4) raising the question rather than guessing on a security-relevant
default — over inventing scope mid-PR.
