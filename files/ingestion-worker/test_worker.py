"""Unit tests for the ingestion worker's Qdrant interaction.

Focus: the collection-bootstrap fix (the worker creates the Qdrant collection on
first use, deriving the vector size from the live embedding), per-task collection
routing (upsert writes to the task's collection, not a module global), and per-
tenant attribution (user_id / tenant_id payload tags + keyword indexes for
retrieval isolation and GDPR erasure). The HTTP layer is mocked with respx; no
Qdrant, Valkey, Tika, Ollama, or Postgres instance is required. See
docs/operations/RUNBOOK-remediation.md B2 and B3.
"""

import json

import httpx
import pytest
import respx

import worker

QURL = worker.QDRANT_URL  # set from QDRANT_URI in conftest.py


@pytest.fixture(autouse=True)
def _clear_ensured_cache() -> None:
    """Isolate the per-process collection-existence cache between tests."""
    worker._ensured_collections.clear()
    yield
    worker._ensured_collections.clear()


@respx.mock
def test_ensure_collection_creates_on_404() -> None:
    """A missing collection is created with the live embedding dimension + Cosine,
    and the tenancy payload fields are indexed (keyword) for filtered reads/deletes."""
    get = respx.get(f"{QURL}/collections/docs").mock(return_value=httpx.Response(404))
    put = respx.put(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(200, json={"result": True})
    )
    idx = respx.put(f"{QURL}/collections/docs/index").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    worker.ensure_qdrant_collection("docs", 768)

    assert get.called
    assert put.called
    body = json.loads(put.calls.last.request.content)
    assert body == {"vectors": {"size": 768, "distance": "Cosine"}}
    # Keyword index created for each tenancy field (user_id, tenant_id).
    assert idx.call_count == 2
    indexed = {json.loads(c.request.content)["field_name"] for c in idx.calls}
    assert indexed == {"user_id", "tenant_id"}
    assert all(json.loads(c.request.content)["field_schema"] == "keyword" for c in idx.calls)


@respx.mock
def test_ensure_collection_existing_is_not_recreated_but_indexed() -> None:
    """An existing collection is not re-created, but its tenancy indexes are ensured
    (so a cluster upgraded over a pre-existing collection still gets indexed)."""
    get = respx.get(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )
    create = respx.put(f"{QURL}/collections/docs").mock(return_value=httpx.Response(200))
    idx = respx.put(f"{QURL}/collections/docs/index").mock(return_value=httpx.Response(200))

    worker.ensure_qdrant_collection("docs", 768)

    assert get.called
    assert not create.called  # already exists -> no re-create
    assert idx.call_count == 2  # but indexes are ensured (upgrade-safe)


@respx.mock
def test_ensure_collection_tolerates_concurrent_create() -> None:
    """If a peer worker wins the create race, our losing create is not an error."""
    respx.get(f"{QURL}/collections/docs").mock(
        side_effect=[
            httpx.Response(404),  # our initial check: absent
            httpx.Response(200, json={"result": {}}),  # peer created it before our PUT
        ]
    )
    respx.put(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(409, json={"status": {"error": "already exists"}})
    )
    respx.put(f"{QURL}/collections/docs/index").mock(return_value=httpx.Response(200))

    # Must not raise (indexes are ensured after the peer-create recheck).
    worker.ensure_qdrant_collection("docs", 768)


@respx.mock
def test_ensure_collection_raises_on_unexpected_status() -> None:
    """A non-404 read error is surfaced, not swallowed."""
    respx.get(f"{QURL}/collections/docs").mock(return_value=httpx.Response(500))

    try:
        worker.ensure_qdrant_collection("docs", 768)
    except httpx.HTTPStatusError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected HTTPStatusError on a 500 from Qdrant")


@respx.mock
def test_upsert_uses_per_task_collection() -> None:
    """Points are written to the task's collection, not the module-global default."""
    respx.get(f"{QURL}/collections/team-a").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )
    respx.put(f"{QURL}/collections/team-a/index").mock(return_value=httpx.Response(200))
    points = respx.put(f"{QURL}/collections/team-a/points").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )

    worker.upsert_vectors(
        "team-a",
        "task1",
        ["chunk text"],
        [[0.1, 0.2, 0.3]],
        {"filename": "f.txt", "collection": "team-a"},
    )

    assert points.called
    body = json.loads(points.calls.last.request.content)
    assert body["points"][0]["payload"]["text"] == "chunk text"
    assert body["points"][0]["payload"]["source"] == "f.txt"
    assert body["points"][0]["vector"] == [0.1, 0.2, 0.3]


@respx.mock
def test_upsert_empty_is_noop() -> None:
    """No embeddings means no Qdrant traffic at all (not even a create)."""
    worker.upsert_vectors("docs", "task1", [], [], {"filename": "f.txt"})
    assert respx.calls.call_count == 0


@respx.mock
def test_ensure_collection_memoized() -> None:
    """A confirmed collection is cached: a second ensure issues no further GET."""
    get = respx.get(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )
    respx.put(f"{QURL}/collections/docs/index").mock(return_value=httpx.Response(200))

    worker.ensure_qdrant_collection("docs", 768)
    worker.ensure_qdrant_collection("docs", 768)

    assert get.call_count == 1


@respx.mock
def test_invalid_collection_rejected_without_http() -> None:
    """A producer-supplied name with path/query/whitespace chars is refused early.

    Validation happens before any URL is built, so neither ensure nor upsert can
    interpolate it into a Qdrant request (no GET/PUT is issued at all).
    """
    for bad in ("a/b", "docs?x=1", "../aliases", "has space", "a#frag", ""):
        with pytest.raises(ValueError):
            worker.ensure_qdrant_collection(bad, 768)
        with pytest.raises(ValueError):
            worker.upsert_vectors(bad, "t", ["c"], [[0.1, 0.2]], {"filename": "f"})

    assert respx.calls.call_count == 0


# --- B3: per-tenant attribution (payload tags + indexes + erasure foundation) ---


def test_build_metadata_includes_validated_tenancy() -> None:
    """Producer-supplied user_id / tenant_id are carried into the payload + created_at."""
    md = worker._build_metadata(
        "doc.pdf", "docs", {"user_id": "u-42", "tenant_id": "acme", "ignored": "x"}
    )
    assert md["filename"] == "doc.pdf"
    assert md["collection"] == "docs"
    assert md["user_id"] == "u-42"
    assert md["tenant_id"] == "acme"
    assert isinstance(md["created_at"], str) and md["created_at"]
    assert "ignored" not in md  # only known tenancy fields are promoted


def test_build_metadata_omits_absent_tenancy() -> None:
    """With no tenancy tags the payload is unchanged except for created_at (back-compat)."""
    md = worker._build_metadata("doc.pdf", "docs", {})
    assert set(md) == {"filename", "collection", "created_at"}


def test_build_metadata_rejects_bad_identifier() -> None:
    """A tenancy id with control characters or over length is refused."""
    with pytest.raises(ValueError):
        worker._build_metadata("doc.pdf", "docs", {"user_id": "bad\nid"})
    with pytest.raises(ValueError):
        worker._build_metadata("doc.pdf", "docs", {"tenant_id": "x" * 257})


@respx.mock
def test_create_payload_indexes_is_best_effort() -> None:
    """An index failure is logged, not raised (the filter still works, just slower)."""
    idx = respx.put(f"{QURL}/collections/docs/index").mock(return_value=httpx.Response(400))
    worker._create_payload_indexes("docs")  # must not raise
    assert idx.call_count == 2


@respx.mock
def test_upsert_payload_carries_tenancy() -> None:
    """user_id / tenant_id in metadata land in the Qdrant point payload (erasure key)."""
    respx.get(f"{QURL}/collections/docs").mock(return_value=httpx.Response(200, json={"result": {}}))
    respx.put(f"{QURL}/collections/docs/index").mock(return_value=httpx.Response(200))
    points = respx.put(f"{QURL}/collections/docs/points").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )

    worker.upsert_vectors(
        "docs",
        "task1",
        ["chunk"],
        [[0.1, 0.2]],
        {"filename": "f.txt", "collection": "docs", "user_id": "u-42", "tenant_id": "acme"},
    )

    payload = json.loads(points.calls.last.request.content)["points"][0]["payload"]
    assert payload["user_id"] == "u-42"
    assert payload["tenant_id"] == "acme"
