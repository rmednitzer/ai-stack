"""
Async document ingestion worker using Valkey Streams.

Flow: Valkey Stream → Tika extract → chunk → Ollama embed → Qdrant upsert
Status tracking via Valkey hash keys (ingestion:status:<task_id>).

Corpus lifecycle state machine (requires PostgreSQL):
  empty → ingesting → ready ↔ stale → re_indexing → ready
  Any active state → failed; failed → ingesting | re_indexing (retry)
State stored in PostgreSQL; transitions auditable via corpus_transitions table.
Valkey pub/sub channel 'corpus:state' notifies consumers (e.g. LangGraph agents)
when a collection becomes ready or changes state.
"""

import errno
import fcntl
import hashlib
import ipaddress
import json
import logging
import os
import signal
import socket
import stat
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
import valkey

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
VALKEY_URL = os.environ.get("VALKEY_URL", "redis://localhost:6379")
STREAM_NAME = os.environ.get("INGESTION_STREAM", "ingestion:documents")
CONSUMER_GROUP = os.environ.get("INGESTION_CONSUMER_GROUP", "ingestion-workers")
CONSUMER_NAME = os.environ.get("HOSTNAME", "worker-0")
STATUS_PREFIX = os.environ.get("INGESTION_STATUS_PREFIX", "ingestion:status:")
STATUS_TTL = int(os.environ.get("INGESTION_STATUS_TTL", "86400"))

TIKA_URL = os.environ["TIKA_SERVER_URL"]
OLLAMA_URL = os.environ["OLLAMA_BASE_URL"]
QDRANT_URL = os.environ["QDRANT_URI"]
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "nomic-embed-text")
# Task-instruction prefix prepended to passages before embedding. Instruction-
# tuned embedders (e.g. nomic-embed-text) require "search_document: " on stored
# passages and "search_query: " on queries; readers of this collection (Open
# WebUI, Pydantic AI) embed queries with the matching RAG_EMBEDDING_QUERY_PREFIX.
# Empty default keeps the worker model-agnostic when run outside the chart.
EMBEDDING_CONTENT_PREFIX = os.environ.get("RAG_EMBEDDING_CONTENT_PREFIX", "")
COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION", "documents")

CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "1500"))
# Default aligned with the chart's values.yaml (RAG_CHUNK_OVERLAP=150) and Open
# WebUI so a chartless run matches the deployed splitter.
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "150"))

BATCH_SIZE = int(os.environ.get("INGESTION_BATCH_SIZE", "5"))
BLOCK_MS = int(os.environ.get("INGESTION_BLOCK_MS", "5000"))
MAX_RETRIES = int(os.environ.get("INGESTION_MAX_RETRIES", "3"))
HEALTH_FILE = "/tmp/healthy"

POSTGRES_URI = os.environ.get("POSTGRES_URI", "")
CORPUS_PUBSUB_CHANNEL = os.environ.get("CORPUS_PUBSUB_CHANNEL", "corpus:state")

# Native source-scheme allowlist (ADR-007). Empty by default → only http(s) and
# local paths are accepted. Listing e.g. "s3,gs,az,smb" opts those schemes in;
# they are resolved via fsspec (installed via ingestionWorker.sources.pipPackages)
# using credentials projected from ingestionWorker.sources.existingSecret.
SOURCE_SCHEMES = {
    s.strip().lower()
    for s in os.environ.get("INGESTION_SOURCE_SCHEMES", "").split(",")
    if s.strip()
}

# Local-path reads (bare paths / file://, e.g. CSI-mounted NFS/SMB shares) are
# fenced away from sensitive system and credential paths so a producer-supplied
# file_url cannot exfiltrate, say, /proc/self/environ (which carries the source
# credentials projected via ingestionWorker.sources.existingSecret) into the
# vector store. Legitimate document mounts (/mnt, /data, …) are unaffected.
_LOCAL_DENY_PREFIXES = ("/proc", "/sys", "/etc", "/root", "/run", "/var/run")

# URL-fetch hardening (ADR-009, SSRF defense): a producer-supplied file_url is
# attacker-influenced input. Schemes are allow-listed (https-only by default;
# add "http" deliberately), and every hop of the fetch — including redirects —
# must resolve to a permitted address. Loopback, link-local (incl. the cloud
# metadata service 169.254.169.254), multicast, reserved, and unspecified
# addresses are ALWAYS refused; other non-global addresses (RFC 1918 / ULA /
# CGNAT — e.g. in-cluster Service IPs) are refused unless covered by the
# operator-supplied INGESTION_FETCH_ALLOWED_CIDRS. Residual risk: the address
# is re-resolved by the HTTP client after screening (no connection pinning), so
# a DNS-rebinding window remains — see LIMITATIONS.md L9.
FETCH_SCHEMES = {
    s.strip().lower()
    for s in os.environ.get("INGESTION_FETCH_SCHEMES", "https").split(",")
    if s.strip()
}
FETCH_ALLOWED_NETS = [
    # Invalid CIDRs raise at startup (crash-loop with a clear message) rather
    # than silently weakening or tightening the screen at fetch time.
    ipaddress.ip_network(c.strip(), strict=False)
    for c in os.environ.get("INGESTION_FETCH_ALLOWED_CIDRS", "").split(",")
    if c.strip()
]
MAX_FETCH_REDIRECTS = 5

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("ingestion-worker")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = False


def _handle_signal(sig: int, _: Any) -> None:
    global _shutdown
    log.info("Received signal %s, shutting down gracefully", sig)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ---------------------------------------------------------------------------
# Valkey client
# ---------------------------------------------------------------------------
vk = valkey.from_url(VALKEY_URL, decode_responses=True)

# ---------------------------------------------------------------------------
# HTTP clients (connection pooling)
# ---------------------------------------------------------------------------
http = httpx.Client(timeout=120.0)
qdrant_headers: dict[str, str] = {}
if QDRANT_API_KEY:
    qdrant_headers["api-key"] = QDRANT_API_KEY

# =========================================================================
# Corpus lifecycle state machine
# =========================================================================

# Valid transitions: {current_state: {target_state, ...}}
CORPUS_TRANSITIONS: dict[str, set[str]] = {
    "empty":       {"ingesting"},
    "ingesting":   {"ready", "failed"},
    "ready":       {"ingesting", "stale"},
    "stale":       {"re_indexing", "ingesting"},
    "re_indexing":  {"ready", "failed"},
    "failed":      {"ingesting", "re_indexing"},
}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS corpus_state (
    collection     TEXT PRIMARY KEY,
    state          TEXT NOT NULL DEFAULT 'empty',
    document_count INTEGER NOT NULL DEFAULT 0,
    pending_count  INTEGER NOT NULL DEFAULT 0,
    failed_count   INTEGER NOT NULL DEFAULT 0,
    embedding_model TEXT,
    chunk_size     INTEGER,
    chunk_overlap  INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corpus_transitions (
    id          SERIAL PRIMARY KEY,
    collection  TEXT NOT NULL,
    from_state  TEXT NOT NULL,
    to_state    TEXT NOT NULL,
    reason      TEXT,
    task_id     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_corpus_transitions_collection
    ON corpus_transitions (collection, created_at DESC);
"""


class CorpusStateMachine:
    """PostgreSQL-backed corpus lifecycle state machine.

    Tracks per-collection state with auditable transitions.
    Publishes state changes to Valkey pub/sub for downstream consumers.
    Degrades gracefully: if PostgreSQL is unavailable, the document
    ingestion pipeline continues without corpus-level tracking.
    """

    def __init__(self, postgres_uri: str, vk_client: valkey.Valkey, channel: str) -> None:
        self._pg = None
        self._vk = vk_client
        self._channel = channel

        if not postgres_uri:
            log.info("Corpus state machine disabled (no POSTGRES_URI)")
            return

        try:
            import psycopg
            self._pg = psycopg.connect(postgres_uri, autocommit=True)
            self._pg.execute(_SCHEMA_SQL)
            log.info("Corpus state machine initialised (PostgreSQL)")
        except Exception as exc:
            log.warning("Corpus state machine unavailable: %s", exc)
            self._pg = None

    @property
    def enabled(self) -> bool:
        return self._pg is not None

    def _ensure_collection(self, collection: str) -> str:
        """Return current state, creating the row if needed."""
        row = self._pg.execute(
            "SELECT state FROM corpus_state WHERE collection = %s",
            (collection,),
        ).fetchone()
        if row:
            return row[0]
        self._pg.execute(
            """INSERT INTO corpus_state (collection, state, embedding_model, chunk_size, chunk_overlap)
               VALUES (%s, 'empty', %s, %s, %s)
               ON CONFLICT (collection) DO NOTHING""",
            (collection, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP),
        )
        return "empty"

    def transition(
        self,
        collection: str,
        to_state: str,
        reason: str = "",
        task_id: str = "",
    ) -> bool:
        """Attempt a state transition. Returns True on success."""
        if not self.enabled:
            return False

        try:
            current = self._ensure_collection(collection)

            valid_targets = CORPUS_TRANSITIONS.get(current, set())
            if to_state not in valid_targets:
                log.warning(
                    "Corpus %s: invalid transition %s → %s (allowed: %s)",
                    collection, current, to_state, valid_targets,
                )
                return False

            self._pg.execute(
                """UPDATE corpus_state
                   SET state = %s, updated_at = now()
                   WHERE collection = %s AND state = %s""",
                (to_state, collection, current),
            )
            self._pg.execute(
                """INSERT INTO corpus_transitions
                   (collection, from_state, to_state, reason, task_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (collection, current, to_state, reason, task_id),
            )

            # Publish to Valkey for downstream consumers
            event = json.dumps({
                "collection": collection,
                "from": current,
                "to": to_state,
                "reason": reason,
                "task_id": task_id,
                "timestamp": time.time(),
            })
            try:
                self._vk.publish(self._channel, event)
            except Exception:
                log.debug("Pub/sub publish failed (non-critical)")

            log.info("Corpus %s: %s → %s (%s)", collection, current, to_state, reason)
            return True

        except Exception as exc:
            log.warning("Corpus state transition failed: %s", exc)
            return False

    def get_state(self, collection: str) -> dict[str, Any] | None:
        """Return current corpus state as a dict, or None if disabled."""
        if not self.enabled:
            return None
        try:
            row = self._pg.execute(
                """SELECT collection, state, document_count, pending_count,
                          failed_count, embedding_model, chunk_size,
                          chunk_overlap, created_at, updated_at
                   FROM corpus_state WHERE collection = %s""",
                (collection,),
            ).fetchone()
            if not row:
                return None
            cols = [
                "collection", "state", "document_count", "pending_count",
                "failed_count", "embedding_model", "chunk_size",
                "chunk_overlap", "created_at", "updated_at",
            ]
            return dict(zip(cols, row))
        except Exception as exc:
            log.warning("Failed to read corpus state: %s", exc)
            return None

    def increment_pending(self, collection: str) -> None:
        """Increment pending document count."""
        if not self.enabled:
            return
        try:
            self._ensure_collection(collection)
            self._pg.execute(
                """UPDATE corpus_state
                   SET pending_count = pending_count + 1, updated_at = now()
                   WHERE collection = %s""",
                (collection,),
            )
        except Exception as exc:
            log.debug("increment_pending failed: %s", exc)

    def complete_document(self, collection: str, chunk_count: int) -> None:
        """Record a successfully ingested document."""
        if not self.enabled:
            return
        try:
            self._pg.execute(
                """UPDATE corpus_state
                   SET document_count = document_count + 1,
                       pending_count = GREATEST(pending_count - 1, 0),
                       updated_at = now()
                   WHERE collection = %s""",
                (collection,),
            )
        except Exception as exc:
            log.debug("complete_document failed: %s", exc)

    def fail_document(self, collection: str) -> None:
        """Record a failed document ingestion."""
        if not self.enabled:
            return
        try:
            self._pg.execute(
                """UPDATE corpus_state
                   SET failed_count = failed_count + 1,
                       pending_count = GREATEST(pending_count - 1, 0),
                       updated_at = now()
                   WHERE collection = %s""",
                (collection,),
            )
        except Exception as exc:
            log.debug("fail_document failed: %s", exc)

    def check_ready(self, collection: str) -> bool:
        """Transition to 'ready' if no documents are pending."""
        if not self.enabled:
            return False
        try:
            row = self._pg.execute(
                "SELECT state, pending_count FROM corpus_state WHERE collection = %s",
                (collection,),
            ).fetchone()
            if row and row[0] == "ingesting" and row[1] == 0:
                return self.transition(
                    collection, "ready", reason="all pending documents processed"
                )
            return False
        except Exception:
            return False

    def detect_config_drift(self, collection: str) -> bool:
        """Check if embedding config has changed since last indexing.

        Returns True and transitions to 'stale' if drift is detected.
        """
        if not self.enabled:
            return False
        try:
            row = self._pg.execute(
                """SELECT state, embedding_model, chunk_size, chunk_overlap
                   FROM corpus_state WHERE collection = %s""",
                (collection,),
            ).fetchone()
            if not row or row[0] != "ready":
                return False

            stored_model, stored_chunk, stored_overlap = row[1], row[2], row[3]
            if (stored_model != EMBEDDING_MODEL
                    or stored_chunk != CHUNK_SIZE
                    or stored_overlap != CHUNK_OVERLAP):
                self.transition(
                    collection,
                    "stale",
                    reason=(
                        f"config drift: model={stored_model}→{EMBEDDING_MODEL}, "
                        f"chunk={stored_chunk}→{CHUNK_SIZE}, "
                        f"overlap={stored_overlap}→{CHUNK_OVERLAP}"
                    ),
                )
                return True
            return False
        except Exception:
            return False

    def close(self) -> None:
        if self._pg:
            try:
                self._pg.close()
            except Exception:
                pass


# Initialise the state machine (gracefully degrades if no PG)
corpus = CorpusStateMachine(POSTGRES_URI, vk, CORPUS_PUBSUB_CHANNEL)

# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------


def set_status(task_id: str, status: str, **extra: Any) -> None:
    key = f"{STATUS_PREFIX}{task_id}"
    data = {"status": status, "updated_at": time.time(), **extra}
    vk.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()})
    vk.expire(key, STATUS_TTL)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def _screen_fetch_url(url: str) -> None:
    """SSRF screen for one fetch hop (ADR-009).

    Raises ValueError unless the URL's scheme is allow-listed and EVERY address
    its host resolves to is permitted. Error messages may name the host (so an
    operator can act on them) but never echo the full URL — a presigned URL
    carries its signature in the query string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in FETCH_SCHEMES:
        raise ValueError(
            f"URL scheme {scheme!r} is not fetchable (INGESTION_FETCH_SCHEMES="
            f"{','.join(sorted(FETCH_SCHEMES))})"
        )
    host = parsed.hostname
    if not host:
        raise ValueError("source URL has no host")
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"source host does not resolve: {host!r}") from exc
    for info in infos:
        # sockaddr[0]; scoped IPv6 link-locals carry a %zone suffix — strip it.
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if (ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            # Never legitimate ingestion targets (cloud metadata/IMDS is
            # link-local) — not overridable via the CIDR allowlist.
            raise ValueError(f"source host {host!r} resolves to a blocked address ({ip})")
        if not ip.is_global and not any(ip in net for net in FETCH_ALLOWED_NETS):
            raise ValueError(
                f"source host {host!r} resolves to a non-public address ({ip}) "
                f"not covered by INGESTION_FETCH_ALLOWED_CIDRS"
            )


def fetch_url(file_url: str) -> bytes:
    """Fetch an http(s) source, screening every redirect hop (ADR-009)."""
    url = file_url
    for _ in range(MAX_FETCH_REDIRECTS + 1):
        _screen_fetch_url(url)
        # follow_redirects=False: each Location target is re-screened above, so
        # an allowed public URL cannot bounce the worker into IMDS/private space.
        resp = http.get(url, follow_redirects=False, timeout=60.0)
        # has_redirect_location, not is_redirect: httpx's is_redirect is true
        # for ANY 3xx (incl. 304 Not Modified, which has no Location); only a
        # real redirect with a Location header should be followed — everything
        # else falls through to the status-code error below.
        if resp.has_redirect_location:
            url = urljoin(url, resp.headers["location"])
            continue
        if not resp.is_success:
            # Report only the status, never the URL (signature in query string;
            # str(exc) lands in logs and the task status hash). Don't ingest a
            # 4xx/5xx error-page body either.
            raise ValueError(f"source fetch failed: HTTP {resp.status_code}")
        return resp.content
    raise ValueError(f"source fetch exceeded {MAX_FETCH_REDIRECTS} redirects")


def read_source(file_url: str) -> bytes:
    """Resolve a task's ``file_url`` to raw bytes.

    Routing (ADR-007, hardening ADR-009):
      * ``http://`` / ``https://``  → screened HTTP fetch (scheme allowlist,
        blocked/non-public address screening, per-redirect re-screening).
      * bare path or ``file://``    → local file (covers CSI-mounted NFS/SMB).
      * any other scheme (``s3://``, ``gs://``, ``az://``, ``smb://``, …) →
        resolved via fsspec, but ONLY when the scheme is allow-listed in
        ``INGESTION_SOURCE_SCHEMES``. A scheme that is neither http(s)/local nor
        allow-listed is rejected (not silently read as a local path).
    """
    scheme = file_url.split("://", 1)[0].lower() if "://" in file_url else ""
    if scheme in ("http", "https"):
        return fetch_url(file_url)
    if scheme in ("", "file"):
        if scheme == "file":
            # Parse per RFC 8089 so the authority is stripped correctly:
            # file:///p and file://localhost/p both mean /p. A non-empty remote
            # host is unsupported (we read locally, not over a network scheme).
            parsed = urlparse(file_url)
            if parsed.netloc not in ("", "localhost"):
                raise ValueError(f"remote file:// host not supported: {parsed.netloc!r}")
            path = unquote(parsed.path)
        else:
            path = file_url
        resolved = Path(path).resolve()  # canonicalize .. and symlinks first
        rp = str(resolved)
        if any(rp == d or rp.startswith(d + "/") for d in _LOCAL_DENY_PREFIXES):
            raise ValueError(f"local source path not permitted: {rp}")
        # Open once and validate the LIVE handle (not a pre-checked path): a
        # symlink swapped in between a stat and a re-open (TOCTOU) on a writable
        # mount could otherwise redirect the read at a denied target. O_NOFOLLOW
        # refuses a symlink final component; fstat on the open fd rejects
        # devices (/dev/zero, /dev/urandom → unbounded read), FIFOs (O_NONBLOCK
        # keeps the open from hanging), sockets, and directories.
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(rp, flags)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError(f"local source is a symlink: {rp}") from exc
            raise
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f"local source is not a regular file: {rp}")
            # O_NONBLOCK's only job was keeping a FIFO open from hanging; clear
            # it before reading — some network filesystems return EAGAIN on
            # regular-file reads, which BufferedReader would surface as
            # BlockingIOError instead of retrying.
            fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) & ~os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as f:
                fd = -1  # ownership moved to the file object
                return f.read()
        finally:
            if fd != -1:
                os.close(fd)
    if scheme in SOURCE_SCHEMES:
        try:
            import fsspec  # lazy; provided via ingestionWorker.sources.pipPackages
            with fsspec.open(file_url, "rb") as f:
                return f.read()
        except ImportError as exc:
            raise ValueError(
                f"scheme {scheme!r} is allow-listed but its fsspec backend is not "
                f"installed; add the matching package to "
                f"ingestionWorker.sources.pipPackages ({exc})"
            ) from exc
    raise ValueError(
        f"unsupported or disabled source scheme {scheme!r}: set "
        f"ingestionWorker.sources.enabled=true and add the scheme to "
        f"ingestionWorker.sources.schemes (current allow-list: {sorted(SOURCE_SCHEMES)})"
    )


def extract_text(file_url: str) -> str:
    """Resolve the source document and return Tika-extracted text."""
    src = read_source(file_url)
    resp = http.put(
        urljoin(TIKA_URL, "/tika"),
        headers={"Accept": "text/plain"},
        content=src,
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.text


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Generate embeddings via Ollama API.

    The configured task-instruction prefix is prepended to the embedding input
    only; the unprefixed chunk text is what gets stored in the Qdrant payload.
    """
    embeddings: list[list[float]] = []
    for chunk in chunks:
        resp = http.post(
            urljoin(OLLAMA_URL, "/api/embed"),
            json={"model": EMBEDDING_MODEL, "input": f"{EMBEDDING_CONTENT_PREFIX}{chunk}"},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings.append(data["embeddings"][0])
    return embeddings


def upsert_vectors(
    task_id: str, chunks: list[str], embeddings: list[list[float]], metadata: dict[str, Any]
) -> None:
    """Upsert chunk vectors into Qdrant."""
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point_id = hashlib.sha256(f"{task_id}:{i}".encode()).hexdigest()[:32]
        # Qdrant requires UUID or unsigned integer IDs; use a deterministic UUID-like hex
        points.append(
            {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "text": chunk,
                    "chunk_index": i,
                    "task_id": task_id,
                    "source": metadata.get("filename", ""),
                    **{k: v for k, v in metadata.items() if k != "filename"},
                },
            }
        )

    resp = http.put(
        urljoin(QDRANT_URL, f"/collections/{COLLECTION_NAME}/points"),
        json={"points": points},
        headers=qdrant_headers,
        timeout=120.0,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Process a single ingestion task
# ---------------------------------------------------------------------------


def process_task(task_id: str, fields: dict[str, str]) -> None:
    file_url = fields.get("file_url", "")
    filename = fields.get("filename", "unknown")
    collection = fields.get("collection", COLLECTION_NAME)
    metadata = {"filename": filename, "collection": collection}

    log.info("Processing task %s: %s", task_id, filename)
    set_status(task_id, "processing", filename=filename)

    # Corpus SM: detect config drift before processing
    corpus.detect_config_drift(collection)

    # Corpus SM: ensure collection is in 'ingesting' state
    state = corpus.get_state(collection)
    if state and state["state"] in ("empty", "ready", "stale", "failed"):
        corpus.transition(
            collection, "ingesting",
            reason=f"new document: {filename}", task_id=task_id,
        )
    corpus.increment_pending(collection)

    # Stage 1: Extract
    set_status(task_id, "extracting", filename=filename)
    text = extract_text(file_url)
    if not text.strip():
        set_status(task_id, "failed", error="Empty text after extraction", filename=filename)
        corpus.fail_document(collection)
        log.warning("Task %s: empty extraction for %s", task_id, filename)
        return

    # Stage 2: Chunk
    set_status(task_id, "chunking", filename=filename)
    chunks = chunk_text(text)
    log.info("Task %s: %d chunks from %s", task_id, len(chunks), filename)

    # Stage 3: Embed
    set_status(task_id, "embedding", filename=filename, chunk_count=len(chunks))
    embeddings = embed_chunks(chunks)

    # Stage 4: Upsert
    set_status(task_id, "upserting", filename=filename, chunk_count=len(chunks))
    upsert_vectors(task_id, chunks, embeddings, metadata)

    set_status(task_id, "done", filename=filename, chunk_count=len(chunks))
    corpus.complete_document(collection, len(chunks))
    corpus.check_ready(collection)
    log.info("Task %s: completed (%d chunks)", task_id, len(chunks))


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------


def ensure_consumer_group() -> None:
    try:
        vk.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        log.info("Created consumer group %s on stream %s", CONSUMER_GROUP, STREAM_NAME)
    except valkey.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
        log.debug("Consumer group %s already exists", CONSUMER_GROUP)


def claim_pending() -> None:
    """Claim messages that have been pending for too long (dead consumer)."""
    min_idle_ms = 60_000  # 1 minute
    try:
        pending = vk.xpending_range(STREAM_NAME, CONSUMER_GROUP, min="-", max="+", count=BATCH_SIZE)
        for entry in pending:
            if entry["time_since_delivered"] > min_idle_ms:
                vk.xclaim(
                    STREAM_NAME,
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    min_idle_time=min_idle_ms,
                    message_ids=[entry["message_id"]],
                )
                log.info("Claimed stale message %s", entry["message_id"])
    except Exception:
        log.debug("No pending messages to claim")


def run() -> None:
    ensure_consumer_group()
    Path(HEALTH_FILE).touch()
    log.info(
        "Worker %s started (group=%s, stream=%s, corpus_sm=%s)",
        CONSUMER_NAME, CONSUMER_GROUP, STREAM_NAME,
        "enabled" if corpus.enabled else "disabled",
    )

    while not _shutdown:
        # Periodically claim abandoned messages
        claim_pending()

        # Read new messages
        try:
            messages = vk.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
        except valkey.ConnectionError:
            log.warning("Valkey connection lost, retrying in 5s")
            time.sleep(5)
            continue

        if not messages:
            continue

        for stream_name, entries in messages:
            for msg_id, fields in entries:
                task_id = fields.get("task_id", msg_id)
                collection = fields.get("collection", COLLECTION_NAME)
                retries = 0
                while retries <= MAX_RETRIES:
                    try:
                        process_task(task_id, fields)
                        vk.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                        break
                    except Exception as exc:
                        retries += 1
                        if retries > MAX_RETRIES:
                            log.error(
                                "Task %s failed after %d retries: %s",
                                task_id,
                                MAX_RETRIES,
                                exc,
                            )
                            set_status(task_id, "failed", error=str(exc))
                            corpus.fail_document(collection)
                            corpus.check_ready(collection)
                            vk.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                        else:
                            log.warning(
                                "Task %s retry %d/%d: %s",
                                task_id,
                                retries,
                                MAX_RETRIES,
                                exc,
                            )
                            time.sleep(2**retries)

        # Update health marker
        Path(HEALTH_FILE).touch()

    # Clean shutdown
    corpus.close()
    try:
        Path(HEALTH_FILE).unlink()
    except FileNotFoundError:
        pass
    log.info("Worker %s stopped", CONSUMER_NAME)


if __name__ == "__main__":
    run()

