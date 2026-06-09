# ADR-008 — Opt-in Valkey AUTH (requirepass)

- **Status:** Accepted
- **Date:** 2026-06-09
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0
- **Supersedes:** none (adds an opt-in credential to the existing Valkey
  component; the default deployment is unchanged)

---

## Context

Valkey carries real session and pipeline state: Open WebUI sessions and
websocket coordination (`REDIS_URL` / `WEBSOCKET_REDIS_URL`), the ingestion
task stream and status hashes, and (when Authelia is enabled) the Authelia
session store. Until 2.12.0 it ran **with no AUTH**: the default-deny
NetworkPolicy plus the per-pod ingress allowlist (Open WebUI, SearXNG,
ingestion worker, Authelia, helm test) was the only gate — network identity
was the credential.

The 2026-06 deep audit recorded this as **R4**: not an open hole (the
allowlist holds), but a missing defense-in-depth layer. Any compromise of an
allow-listed pod — e.g. via the model-driven attack surface this chart's
threat model treats as attacker-influenced — yields full read/write on
sessions and the ingestion stream. R4 was deferred from 2.10.0 precisely
because the fix is cross-cutting: every consumer URL, the probes, the
stream-init job, and the helm test must change together.

Constraints that shaped the design:

- **No default may break.** `helm upgrade --reuse-values` from any 2.x must
  produce an identical Valkey deployment unless the operator opts in.
- **No secret in process args.** `--requirepass <pw>` on the command line
  leaks into `ps`, node process accounting, and any cmdline-capturing agent.
- **Generated credentials must stay stable** across upgrades
  (`ai-stack.persistentSecret` discipline; rotating silently would invalidate
  every consumer simultaneously).
- The values-defined probes (`valkey-cli ping`) and the raw-RESP helm test
  must keep working.

## Decision

1. **`valkey.auth.enabled` (default `false`).** Off means byte-identical
   rendering to 2.11.0 — no Secret, no args, no env. The
   `ai-stack.valkeyAuthEnabled` helper guards every touch point and tolerates
   values files that predate the block.

2. **Password via `ai-stack.persistentSecret`, server config via the same
   Secret.** The chart-managed `<release>-valkey-secret` carries two keys
   derived from one resolution: `password` (for clients) and `valkey.conf`
   (`requirepass <password>`). The server runs
   `valkey-server /etc/valkey/valkey.conf` with the file Secret-mounted, so
   the password never appears in container args or process listings.

3. **Probes authenticate via environment.** `VALKEYCLI_AUTH` and
   `REDISCLI_AUTH` (set from the Secret) make the existing values-defined
   `valkey-cli ping` probes — and the ingestion stream-init container —
   authenticate without changing their commands.

4. **Consumers embed the credential by `$(...)` substitution**, the chart's
   existing `_PG_PASSWORD` pattern: an `_VALKEY_PASSWORD` env sourced from the
   Secret, referenced inside `redis://:$(_VALKEY_PASSWORD)@host:port/db`.
   Wired for Open WebUI (`REDIS_URL`, `WEBSOCKET_REDIS_URL`), the ingestion
   worker (`VALKEY_URL`), and Authelia
   (`AUTHELIA_SESSION_REDIS_PASSWORD` → `session.redis.password`). The helm
   test sends a RESP `AUTH` before `PING`, reading the password from a
   Secret-sourced env var. Generated passwords are alphanumeric (URL-safe);
   an override must be URL-safe too (documented in values.yaml).

5. **SearXNG is intentionally not wired.** The chart's SearXNG config does
   not point at Valkey (the limiter is off by default and no `valkey.url` is
   rendered); its NetworkPolicy egress remains for operators who configure it
   themselves — they own adding the password to their settings override.

## Consequences

**Positive**
- A second, independent control on the session/pipeline datastore: a
  compromised allow-listed pod no longer gets Valkey for free; an
  accidentally widened NetworkPolicy no longer exposes an open datastore.
- No process-args leakage; credential storage and stability follow the
  chart's existing Secret discipline; asserted in `tests/valkey_auth_test.yaml`.

**Negative / trade-offs**
- Enabling (or disabling) AUTH is a coordinated rollout: Valkey restarts and
  every consumer re-renders in the same `helm upgrade`. In-flight sessions
  survive (state is in Valkey, not the connections), but plan it as a
  deliberate change window.
- Password **rotation** is manual: change the override (or delete the Secret
  key), then `kubectl rollout restart` Valkey and its consumers. The chart
  deliberately avoids a config-checksum annotation on the Valkey pod — under
  GitOps/`helm template` the `lookup`-based secret renders fresh randoms,
  which would churn the workload on every sync.
- One password for all consumers (Valkey ACL users/roles are out of scope for
  this chart's single-tenant topology; revisit if multi-tenant ACLs become a
  requirement).

## Alternatives considered

- **`--requirepass $(VALKEY_PASSWORD)` in args** — simplest, but the expanded
  password is visible in `/proc/<pid>/cmdline` and process-level telemetry.
  Rejected.
- **Default-on AUTH** — strictly stronger, but a breaking `--reuse-values`
  upgrade for every existing install of a chart that promises stable
  defaults. Rejected in favour of opt-in plus documentation.
- **Valkey ACLs (per-consumer users)** — finer-grained, but adds an ACL file
  schema and per-consumer credential plumbing for marginal gain in this
  single-namespace topology. Deferred until a concrete multi-tenant need.
- **TLS to Valkey** — orthogonal transport protection; not bundled here to
  keep the change reviewable. Can follow as its own opt-in.
