# Ingestion Worker — Specification

**Status:** stable · **Last reviewed:** 2026-06-07 · **Source of truth:**
[`files/ingestion-worker/worker.py`](../../files/ingestion-worker/worker.py)

This is the authoritative contract for the async ingestion worker: the queue and
status protocols a producer must follow, the delivery/retry semantics, the corpus
lifecycle state machine, and the full configuration surface. The concise
component overview lives in [`ingestion-worker.md`](ingestion-worker.md); this
document is the precise spec. Where this doc and the code disagree, the code wins
— file an issue.

---

## 1. Overview

The worker is a stateless consumer of a **Valkey Stream**. For each task it runs
a four-stage pipeline and records progress in a per-task **Valkey hash**:

```
Valkey Stream (ingestion:documents)
        │  XREADGROUP ">"
        ▼
  ┌─────────────────────────────────────────────────────────┐
  │ extract (Tika) → chunk → embed (Ollama) → upsert (Qdrant) │
  └─────────────────────────────────────────────────────────┘
        │                                   │
        ▼ status hash                        ▼ (optional) corpus state machine
  ingestion:status:<task_id>           PostgreSQL + pub/sub corpus:state
```

Multiple replicas form one **consumer group**, so throughput scales horizontally
and a crashed worker's in-flight messages are reclaimed by its peers. The corpus
state machine is **optional** (activated only when `POSTGRES_URI` is set) and the
pipeline degrades gracefully without it.

---

## 2. Task message contract — `ingestion:documents`

Producers enqueue with `XADD <stream> * <field> <value> …`. The stream name is
`INGESTION_STREAM` (default `ingestion:documents`).

| Field | Required | Default | Meaning |
|-------|----------|---------|---------|
| `task_id` | Recommended | the Stream message ID | Correlation id; keys the status hash and the deterministic Qdrant point IDs. Provide your own for idempotent re-submits. |
| `file_url` | **Yes** | — (required) | Source document; an empty/missing value fails. `http://`/`https://` is fetched over HTTP (redirects followed, non-2xx rejected); a bare path / `file://` is read as a **local regular file**; any other scheme is resolved via `fsspec` **only if allow-listed**, otherwise **rejected** (not read as a local path). See [§2.1](#21-source-resolution-url-schemes-adr-007). |
| `filename` | No | `"unknown"` | Stored as `source` in each chunk's Qdrant payload. |
| `collection` | No | `QDRANT_COLLECTION` (default `documents`) | The **corpus-state-machine key**, and recorded under `collection` in each chunk's Qdrant payload. **It does *not* select the Qdrant collection that vectors are written to:** the worker always upserts to the single configured `QDRANT_COLLECTION` (see [§7](#7-security-and-limitations)). So this field gives per-tenant *state tracking* and a payload filter key, **not** vector-store-level isolation on its own. |

> **Security note.** `file_url` is fetched as-is — see [§7](#7-security-and-limitations). A
> producer that can write to the stream controls the URL the worker dereferences.

Example (`redis-cli`):

```bash
redis-cli -p 6379 XADD ingestion:documents '*' \
  task_id  "doc-001" \
  file_url "https://example.com/report.pdf" \
  filename "report.pdf" \
  collection "tenant-acme"
```

### 2.1 Source resolution (URL schemes, ADR-007)

`read_source(file_url)` resolves the document bytes by URL scheme:

| Scheme | Resolver | Notes |
|--------|----------|-------|
| `http://`, `https://` | `httpx` GET (redirects followed; **non-2xx rejected**) | Always available. Covers **presigned** S3/GCS/Azure URLs. |
| *(bare path)*, `file://` | local **regular-file** read | Always available. Covers **CSI-mounted NFS/SMB** shares (the recommended, lowest-risk pattern). `file://` follows RFC 8089 (`file:///p` and `file://localhost/p` → `/p`); devices/FIFOs/dirs and credential/system prefixes are rejected (see [§7](#7-security-and-limitations)). |
| `s3://`, `gs://`, `az://`, `smb://`, `sftp://`, … | `fsspec` | **Opt-in & deny-by-default**: honored only when the scheme is in `INGESTION_SOURCE_SCHEMES` (set from `ingestionWorker.sources.schemes`). An unknown or disabled scheme is **rejected**, never read as a local path. |

Native connectors require the matching `fsspec` backend (installed via
`ingestionWorker.sources.pipPackages`) and credentials (projected from
`ingestionWorker.sources.existingSecret` as the env vars the backend reads).
Native non-HTTPS protocols (SMB/445, NFS/2049, SFTP/22) also need explicit
NetworkPolicy egress — **not** opened by the chart. See
[ADR-007](../architecture/ADR-007-ingestion-source-connectors.md).

---

## 3. Status contract — `ingestion:status:<task_id>`

The worker writes a Valkey **hash** at `<INGESTION_STATUS_PREFIX><task_id>`
(default prefix `ingestion:status:`) and refreshes its TTL
(`INGESTION_STATUS_TTL`, default `86400` s) on every update.

| Hash field | Type | When | Meaning |
|------------|------|------|---------|
| `status` | string | every update | Current lifecycle state (table below). |
| `updated_at` | float (epoch s) | every update | Last-write timestamp. |
| `filename` | string | from `processing` on | Echo of the task `filename`. |
| `chunk_count` | int | from `embedding` on | Number of chunks produced. |
| `error` | string | on failure | Exception summary (terminal `failed` only). |

### 3.1 Status lifecycle

```
processing → extracting → chunking → embedding → upserting → done
     └────────────────────────────────────────────────────→ failed
```

| `status` | Stage |
|----------|-------|
| `processing` | Task dequeued; corpus drift-check + `ingesting` transition. |
| `extracting` | Document fetched and sent to Tika. |
| `chunking` | Text split into overlapping chunks. |
| `embedding` | Chunks embedded via Ollama. |
| `upserting` | Vectors written to Qdrant. |
| `done` | Terminal success. |
| `failed` | Terminal failure (`error` set). Empty extraction also yields `failed`. |

> These are the **only** emitted values. (There is no `queued` or `completed`
> state — a task not yet picked up simply has no status hash.)

---

## 4. Delivery & retry semantics

- **Consumer group.** `INGESTION_CONSUMER_GROUP` (default `ingestion-workers`),
  created at id `0` with `MKSTREAM` by both an init container and the worker
  (idempotent — `BUSYGROUP` is ignored). Each pod's consumer name is its
  `HOSTNAME`.
- **Read loop.** `XREADGROUP … STREAMS <stream> ">"` with `COUNT=INGESTION_BATCH_SIZE`
  (chart default `10`) and `BLOCK=INGESTION_BLOCK_MS` ms (chart default `2000`).
- **At-least-once.** A message is `XACK`-ed only after `process_task` returns. On
  exception it is retried up to `INGESTION_MAX_RETRIES` (default `3`) with
  exponential backoff (`2^attempt` s). After the final retry the task is marked
  `failed` **and** `XACK`-ed (terminal — it is *not* redelivered forever).
- **Dead-consumer recovery.** Each loop, `claim_pending()` `XCLAIM`s messages that
  have been pending > 60 s (a crashed peer's work) to this consumer.
- **Idempotency.** Qdrant point IDs are `sha256("<task_id>:<chunk_index>")[:32]`,
  so re-submitting the same `task_id` overwrites the same points rather than
  duplicating them. Choose stable `task_id`s for safe replays.

---

## 5. Corpus lifecycle state machine

*Optional — activated only when `POSTGRES_URI` is set (the chart injects it when
`postgres.enabled=true`).* It tracks **per-collection** ingestion state with an
auditable transition log and notifies downstream consumers (e.g. LangGraph
agents) via Valkey pub/sub.

### 5.1 States & transitions

```
empty ──▶ ingesting ──▶ ready ◀──▶ stale ──▶ re_indexing ──▶ ready
                │                                   │
                ▼                                   ▼
              failed ◀─────────────────────────── failed
              (failed ──▶ ingesting | re_indexing)
```

| From | Allowed targets |
|------|-----------------|
| `empty` | `ingesting` |
| `ingesting` | `ready`, `failed` |
| `ready` | `ingesting`, `stale` |
| `stale` | `re_indexing`, `ingesting` |
| `re_indexing` | `ready`, `failed` |
| `failed` | `ingesting`, `re_indexing` |

- A collection enters `ingesting` on a new document and returns to `ready` when
  `pending_count` reaches 0.
- **Config-drift → `stale`.** Before processing, a `ready` collection whose stored
  `embedding_model` / `chunk_size` / `chunk_overlap` differ from the worker's
  current config is moved to `stale` (a re-index signal).

### 5.2 Persistence schema (auto-created)

`corpus_state` — one row per collection: `collection` (PK), `state`,
`document_count`, `pending_count`, `failed_count`, `embedding_model`,
`chunk_size`, `chunk_overlap`, `created_at`, `updated_at`.

`corpus_transitions` — append-only audit log: `id`, `collection`, `from_state`,
`to_state`, `reason`, `task_id`, `created_at` (indexed by `collection,
created_at DESC`).

### 5.3 Pub/sub event — `corpus:state`

On every accepted transition the worker `PUBLISH`es a JSON event to
`CORPUS_PUBSUB_CHANNEL` (default `corpus:state`):

```json
{ "collection": "tenant-acme", "from": "ingesting", "to": "ready",
  "reason": "all pending documents processed", "task_id": "doc-001",
  "timestamp": 1749283200.0 }
```

Publishing is best-effort: a pub/sub failure never blocks ingestion.

---

## 6. Configuration reference

All keys are set under `ingestionWorker.env` in `values.yaml` unless noted.
"Chart default" is the value the chart ships; "code fallback" is what
`worker.py` uses if the variable is unset.

| Variable | Chart default | Required | Purpose |
|----------|---------------|----------|---------|
| `TIKA_SERVER_URL` | Tika service URL | **Yes** | Text extraction endpoint. |
| `OLLAMA_BASE_URL` | Ollama service URL | **Yes** | Embedding endpoint. |
| `QDRANT_URI` | Qdrant service URL | **Yes** | Vector upsert endpoint. |
| `VALKEY_URL` | `redis://<release>-valkey:6379` | injected by the deployment | Stream + status backend. |
| `QDRANT_API_KEY` | from `qdrant-secret` | injected | Qdrant auth header. |
| `POSTGRES_URI` | injected when `postgres.enabled` | injected | Enables the corpus state machine. |
| `RAG_EMBEDDING_MODEL` | `nomic-embed-text` | no | Ollama embedding model (must be pulled). |
| `QDRANT_COLLECTION` | `documents` | no | Default target collection. |
| `RAG_CHUNK_SIZE` | `1500` | no | Chunk size in characters (code fallback `1500`). |
| `RAG_CHUNK_OVERLAP` | `150` | no | Chunk overlap (code fallback `100`). |
| `INGESTION_STREAM` | `ingestion:documents` | no | Stream name. |
| `INGESTION_CONSUMER_GROUP` | `ingestion-workers` | no | Consumer group. |
| `INGESTION_STATUS_PREFIX` | `ingestion:status:` | no | Status-hash key prefix. |
| `INGESTION_STATUS_TTL` | `86400` | no | Status-hash TTL (seconds). |
| `INGESTION_BATCH_SIZE` | `10` | no | Messages per `XREADGROUP` (code fallback `5`). |
| `INGESTION_BLOCK_MS` | `2000` | no | Block timeout per read (code fallback `5000`). |
| `INGESTION_MAX_RETRIES` | `3` | no | Retries before terminal `failed`. |
| `CORPUS_PUBSUB_CHANNEL` | `corpus:state` | no | Corpus event channel. |
| `LOG_LEVEL` | `INFO` | no | Log verbosity. |
| `INGESTION_SOURCE_SCHEMES` | `""` (none) | from `sources.schemes` when `sources.enabled` | Comma-list of allow-listed native fsspec schemes (ADR-007); empty = http(s) + local only. |
| `HOSTNAME` | pod name | injected by K8s | Consumer name within the group. |

---

## 7. Security and limitations

- **Fetch surface (SSRF / local read).** **Local** reads (bare path / `file://`)
  are restricted to **regular files** — devices (`/dev/urandom`, `/dev/zero`),
  FIFOs, sockets and directories are rejected, closing an unbounded-`read_bytes`
  DoS — and are fenced away from sensitive system + credential prefixes (`/proc`,
  `/sys`, `/etc`, `/root`, `/run`, `/var/run`); paths are `resolve()`-canonicalized
  first, so a producer-supplied `file_url` cannot read e.g. `/proc/self/environ`
  (which carries the credentials projected via `sources.existingSecret`) into the
  store. A symlink swapped between the resolve-time check and the read (TOCTOU) is
  tracked as **R10**. **`http(s)`** fetches **reject non-2xx responses** (no
  error-page body is ingested) but still follow the producer-supplied host: treat
  stream producers as trusted and restrict who can write to the stream; a
  private/link-local CIDR allow/deny list for the HTTP path is tracked as **R5**
  in [`docs/audit/AUDIT-2026-06.md`](../audit/AUDIT-2026-06.md).
- **Liveness is file-based.** The probe checks `/tmp/healthy`; a hung-but-alive
  process is not self-healed. See audit backlog.
- **Dependency pinning.** [`requirements.txt`](../../files/ingestion-worker/requirements.txt)
  is major-version-bounded but **not hash-locked** (unlike the Pydantic AI app).
  Air-gapped/hardened deployments should bake a prebuilt image
  ([`Dockerfile`](../../files/ingestion-worker/Dockerfile), `buildDeps: false`).
  Hash-locking is audit item **R7**.
- **`error` content.** On failure the raw exception string is written to the
  status hash; readers of `ingestion:status:*` may see internal detail. The HTTP
  fetch path reports only the status code (never the URL), so a **presigned URL's
  signature is not echoed** into logs or the status hash.
- **`collection` does not route the upsert.** `upsert_vectors()` writes to the
  single configured `QDRANT_COLLECTION`; the per-task `collection` only keys the
  corpus state machine and is stored in the payload. True per-collection vector
  isolation would require the worker to target the task's collection (and create
  it on demand) — a deliberate enhancement, not current behaviour.
- Boundary/tier and controls: T2 / `ingestion`, [CTL-002 + POL-001](../governance/CONTROLS.md).
  Standing scope boundaries: [`LIMITATIONS.md`](../../LIMITATIONS.md).

---

## 8. Scaling & operations

- **Horizontal scale.** Increase `ingestionWorker.replicaCount` (or enable its
  HPA); the consumer group distributes messages across pods automatically.
- **Durability.** Set `valkey.persistence.enabled=true` so the Stream (and
  in-flight tasks) survive a Valkey restart; otherwise un-acked tasks are lost on
  Valkey loss (source documents remain and can be re-enqueued).
- **Observability.** With `global.otel.enabled=true` the worker emits OTLP via the
  injected `OTEL_*` env; trace IDs correlate a task across the four stages.
- See [HOWTO §5](../../HOWTO.md#5-async-document-ingestion) for end-to-end usage.
