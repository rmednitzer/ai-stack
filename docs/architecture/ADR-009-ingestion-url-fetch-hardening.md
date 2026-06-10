# ADR-009 — Ingestion worker URL-fetch hardening (SSRF defense)

- **Status:** Accepted
- **Date:** 2026-06-09
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0
- **Supersedes:** none (hardens the `http(s)` source path ADR-007 left
  unchanged; native-scheme and local-path fences are ADR-007's)

---

## Context

The ingestion worker fetches producer-supplied `file_url` values. Producers
are NetworkPolicy-gated, but this chart's threat model (SECURITY.md) treats
the model-driven plane as attacker-influenced — a prompt-injected tool or a
compromised allow-listed pod can enqueue arbitrary URLs. Until 2.12.0 the
worker fetched **any** `http(s)` URL with redirects followed blindly: a
classic SSRF surface reaching the cloud metadata service
(`169.254.169.254`), node-local services, and anything on the pod's
80/443 egress (which the NetworkPolicy allows to any address). The 2026-06
audit recorded this as **R5**, and the sibling TOCTOU race on local reads as
**R10**; both were deferred because the correct network allowlist is
deployment-specific.

## Decision

1. **Scheme allowlist, https-only by default.** `INGESTION_FETCH_SCHEMES`
   (chart: `ingestionWorker.fetch.schemes`, default `["https"]`) gates the
   fetch path. Plain `http` is a deliberate operator choice, not a default.
   *Breaking change:* pre-2.12.0 workers accepted `http://` unconditionally —
   operators with plain-HTTP sources add `http` back explicitly.

2. **Resolved-address screening with a hard floor.** Before each request the
   worker resolves the URL host and screens **every** returned address:
   loopback, link-local (incl. IMDS), multicast, reserved, and unspecified
   addresses are always refused — they have no legitimate ingestion use and
   are **not** overridable. Other non-global addresses (RFC 1918, ULA,
   CGNAT — i.e. in-cluster Services and internal ranges) are refused unless
   covered by `INGESTION_FETCH_ALLOWED_CIDRS`
   (chart: `ingestionWorker.fetch.allowedCidrs`, default empty). Operators
   using in-cluster presigned object-store URLs allow-list their Service
   CIDR — the deployment-specific decision the audit anticipated, now a
   values key instead of a code change.

3. **Redirects are followed manually and re-screened per hop** (bounded at
   5): an allowed public URL can no longer 302-bounce the worker into
   metadata/private space. Error messages keep the existing no-URL-leak
   property — they may name the host, never the full URL (presigned
   signatures live in the query string and `str(exc)` lands in the status
   hash).

4. **Local reads validate the live file handle (R10).** The worker opens the
   resolved path with `O_NOFOLLOW` (+`O_NONBLOCK`, so a FIFO cannot hang the
   open) and `fstat`s the **open descriptor** for `S_ISREG` before reading —
   replacing the check-then-reopen sequence a symlink swap could race on a
   writable mount. The deny-prefix fence and RFC 8089 `file://` parsing are
   unchanged (ADR-007).

5. **Fail closed on misconfiguration.** An unparsable CIDR in the allowlist
   raises at startup (crash-loop with a clear message) rather than silently
   altering the screen.

## Consequences

**Positive**
- IMDS/credential-endpoint SSRF via enqueued URLs is closed, including via
  redirects; internal reach now requires an explicit, auditable CIDR grant
  rendered as env on the pod (`tests/ingestion_sources_test.yaml` asserts the
  wiring and the https-only default).
- The TOCTOU window on local reads is reduced to the kernel-level open
  itself.

**Negative / trade-offs**
- **Upgrade impact:** deployments fetching plain-HTTP or in-cluster/private
  URLs must set `fetch.schemes` / `fetch.allowedCidrs` (CHANGELOG carries the
  upgrade note). The zero-config alternatives — CSI mounts and *external*
  presigned HTTPS — keep working untouched.
- **Residual risk:** addresses are re-resolved by the HTTP client after
  screening (no connection pinning), so a fast-flux DNS-rebinding window
  remains; parent-directory symlink races outside the final path component
  are likewise out of scope. Both are documented in LIMITATIONS.md L9 —
  proportionate for reference code whose producers are NetworkPolicy-gated.
- One extra DNS resolution per fetch hop (negligible against Tika/embedding
  cost).

## Alternatives considered

- **Keep `http` in the default scheme list** — zero upgrade friction, but
  contradicts the audit recommendation and the secure-by-default posture;
  rejected.
- **Pin connections to the screened IP** (resolve once, connect by IP, send
  SNI/Host manually) — closes the rebinding window but requires custom
  transport plumbing in `httpx`, disproportionate for reference code;
  documented as residual instead.
- **Egress NetworkPolicy tightening only** — NetworkPolicy cannot express
  "public addresses only" portably (no notIP semantics), and the worker
  legitimately needs broad 443 egress for presigned URLs; rejected as the
  sole control.
- **Host-name allowlist instead of CIDRs** — friendlier but trivially
  bypassed via attacker-controlled DNS; CIDRs screen what actually matters
  (the resolved addresses).
