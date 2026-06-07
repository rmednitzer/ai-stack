# ADR-007 — Native ingestion source connectors (fsspec)

- **Status:** Accepted
- **Date:** 2026-06-07
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.11.0
- **Supersedes:** none (extends the ingestion worker; the existing `http(s)` and
  local-path sources are unchanged)

---

## Context

The async ingestion worker (`files/ingestion-worker/worker.py`) resolves a task's
`file_url` in exactly two ways: an `http(s)://` URL (fetched with `httpx`) or a
local filesystem path (read from disk). Enterprises keep documents in **object
stores** (S3, GCS, Azure Blob) and **network shares** (SMB, NFS) — so the question
is whether, and how, the worker should ingest from those natively.

Two patterns already work today without any code:

- **NFS / SMB → CSI volume mount.** Mount the share into the worker pod with the
  NFS/SMB CSI driver and enqueue a local path. The kubelet performs the mount, so
  the pod's default-deny NetworkPolicy does not even apply to it.
- **Object stores → presigned HTTPS URLs.** The producer presigns a time-bounded
  GET URL; the worker fetches it over its existing port-443 egress. No credentials
  ever reach the worker.

What is genuinely missing is **native scheme support** (`s3://`, `gs://`, `az://`,
`smb://`, `sftp://`, …) so a producer can enqueue `s3://bucket/key` directly. That
requires an in-worker connector with credentials — a supply-chain and security
decision, hence this ADR (per `AGENTS.md` §7).

Approaches evaluated:

- **Per-backend SDKs** (`boto3`, `google-cloud-storage`, `azure-storage-blob`, …)
  — most direct, but N dependencies, N credential conventions, N code paths.
- **[`fsspec`](https://filesystem-spec.readthedocs.io/)** — one filesystem
  abstraction with pluggable backends (`s3fs`, `gcsfs`, `adlfs`, `smbprotocol`,
  `sshfs`, http, local). One uniform `fsspec.open(url, "rb")` call covers every
  scheme, and each backend reads its **conventional credential env vars**, so the
  chart only has to project a Secret — no per-provider glue in the worker.

`fsspec` wins on uniformity and on keeping the worker's code provider-agnostic.

## Decision

1. **Add an opt-in `fsspec`-based source resolver** to the worker. `http(s)` and
   local paths behave **exactly as before**; only the new schemes route through
   `fsspec`. The component is off by default (`ingestionWorker.sources.enabled:
   false`) and fully backward compatible.

2. **Deny-by-default for the new surface.** A native scheme is honored **only if
   it is listed in `ingestionWorker.sources.schemes`** (an explicit allowlist). A
   scheme that is neither `http(s)`/local nor allow-listed is **rejected** rather
   than silently treated as a local path — closing the confusing failure mode and
   bounding the SSRF reach the audit flagged (R5).

3. **Operator-selected dependencies.** The connector libraries are **not** baked
   into the default image. The operator lists exactly the backends they need in
   `ingestionWorker.sources.pipPackages` (e.g. `fsspec`, `s3fs`, `gcsfs`,
   `adlfs`, `smbprotocol`); the existing `buildDeps` initContainer installs them,
   or they are baked into a prebuilt image. The default image stays lean and the
   import is lazy (only attempted when an allow-listed native scheme is used).

4. **Credentials via a Secret, projected as env.** `ingestionWorker.sources.existingSecret`
   is mounted with `envFrom`, so the `fsspec` backends pick up their standard env
   vars (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`,
   `AZURE_STORAGE_*`, etc.). No credential-handling code lives in the worker, and
   nothing is written to rendered manifests.

5. **No security default is auto-weakened.** Object stores reach over the
   already-allowed port-443 egress. Native **non-HTTPS** protocols (SMB/445,
   NFS/2049, SFTP/22) need egress that the default-deny policy blocks; the chart
   does **not** open those automatically — the operator adds the egress
   explicitly (documented). The CSI-mount path for NFS/SMB remains the
   recommended, lowest-risk option and needs none of this.

## Consequences

**Positive**
- Native multi-source ingestion (object stores + shares) from one uniform code path.
- Lean default image; credentials scoped to one Secret; provider-agnostic worker.
- Backward compatible — existing `http(s)`/local/CSI-mount and presigned-URL flows are unchanged.
- Local-path reads are restricted to **regular files** (devices/FIFOs/sockets/
  directories rejected, closing an unbounded-`read_bytes` DoS) and fenced from
  sensitive system/credential prefixes (`/proc`, `/sys`, `/etc`, `/root`, `/run`,
  `/var/run`), so the env-projected credentials this ADR introduces cannot be
  read back through a crafted `file_url` (e.g. `/proc/self/environ`) and
  exfiltrated into the vector store.

**Negative / trade-offs**
- Widens the worker's fetch surface (SSRF). Mitigated by: deny-by-default scheme
  allowlist, operator-scoped egress (non-HTTPS stays blocked by default), and the
  Secret-scoped credentials. Treat stream producers as trusted. A symlink-swap
  TOCTOU on local reads is a residual, tracked as **R10** in the audit backlog.
- The operator owns the backend dependency set, the credential Secret, and any
  extra egress — more configuration than the zero-code presigned/mount patterns.
- `pipPackages` installed at runtime are not hash-pinned (consistent with the
  existing `requirements.txt` posture; hash-locking is audit item R7).

## Alternatives considered

- **Presigned URLs only** — works today, zero code, but pushes per-object signing
  onto every producer and does not cover network shares.
- **CSI volume mounts only** — ideal for NFS/SMB, but cannot express object-store
  schemes natively.
- **Per-backend SDKs** — rejected for the N-deps / N-credentials / N-code-paths
  cost versus `fsspec`'s single abstraction.

Both zero-code patterns remain first-class and documented; this ADR adds the
native path for operators who want producers to enqueue scheme URLs directly.
