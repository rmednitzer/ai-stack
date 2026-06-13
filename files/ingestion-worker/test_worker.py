"""Unit tests for the ingestion worker's Qdrant interaction.

Focus: the collection-bootstrap fix (the worker now creates the Qdrant collection
on first use, deriving the vector size from the live embedding) and the per-task
collection routing (upsert writes to the task's collection, not a module global).
The HTTP layer is mocked with respx; no Qdrant, Valkey, Tika, Ollama, or Postgres
instance is required. See docs/operations/RUNBOOK-remediation.md B2.
"""

import json

import httpx
import respx

import worker

QURL = worker.QDRANT_URL  # set from QDRANT_URI in conftest.py


@respx.mock
def test_ensure_collection_creates_on_404() -> None:
    """A missing collection is created with the live embedding dimension + Cosine."""
    get = respx.get(f"{QURL}/collections/docs").mock(return_value=httpx.Response(404))
    put = respx.put(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    worker.ensure_qdrant_collection("docs", 768)

    assert get.called
    assert put.called
    body = json.loads(put.calls.last.request.content)
    assert body == {"vectors": {"size": 768, "distance": "Cosine"}}


@respx.mock
def test_ensure_collection_noop_when_present() -> None:
    """An existing collection is left untouched (no create call)."""
    get = respx.get(f"{QURL}/collections/docs").mock(
        return_value=httpx.Response(200, json={"result": {}})
    )
    put = respx.put(f"{QURL}/collections/docs")

    worker.ensure_qdrant_collection("docs", 768)

    assert get.called
    assert not put.called


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

    # Must not raise.
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
