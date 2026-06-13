"""Unit tests for the Pydantic AI runtime's per-tenant retrieval filter (B3).

Verifies that the knowledge-base retrieval scopes to the caller's user_id /
tenant_id (matched against the payload tags the ingestion worker writes), so one
tenant cannot read another's documents, and that the identity is threaded from the
agent run all the way into the Qdrant query filter. The HTTP layer is respx-mocked;
no Ollama / Qdrant / Postgres instance is required. See
docs/operations/RUNBOOK-remediation.md B3.
"""

import asyncio
import json

import httpx
import respx

import app

EMBED = f"{app.OLLAMA_BASE_URL}/api/embed"
QUERY = f"{app.QDRANT_URI}/collections/{app.QDRANT_COLLECTION}/points/query"


def _mock_embed_and_query() -> respx.Route:
    respx.post(EMBED).mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})
    )
    return respx.post(QUERY).mock(
        return_value=httpx.Response(200, json={"result": {"points": []}})
    )


@respx.mock
def test_retrieve_unfiltered_without_identity() -> None:
    """No identity -> no filter (backward compatible)."""
    q = _mock_embed_and_query()
    asyncio.run(app._qdrant_retrieve("hello"))
    body = json.loads(q.calls.last.request.content)
    assert "filter" not in body


@respx.mock
def test_retrieve_filters_by_user_and_tenant() -> None:
    """Both ids present -> a must-match on each."""
    q = _mock_embed_and_query()
    asyncio.run(app._qdrant_retrieve("hello", "u-42", "acme"))
    body = json.loads(q.calls.last.request.content)
    assert body["filter"] == {
        "must": [
            {"key": "user_id", "match": {"value": "u-42"}},
            {"key": "tenant_id", "match": {"value": "acme"}},
        ]
    }


@respx.mock
def test_retrieve_filters_by_user_only() -> None:
    """A single id present -> a single must-match (no empty tenant clause)."""
    q = _mock_embed_and_query()
    asyncio.run(app._qdrant_retrieve("hello", "u-42", None))
    body = json.loads(q.calls.last.request.content)
    assert body["filter"] == {"must": [{"key": "user_id", "match": {"value": "u-42"}}]}


@respx.mock
def test_agent_threads_deps_into_filter() -> None:
    """End-to-end: agent.run(deps=...) -> tool -> _qdrant_retrieve -> filtered query.

    Uses pydantic-ai's TestModel (no network/model) which calls the registered
    knowledge-base tool; the identity carried in deps must reach the Qdrant filter.
    """
    from pydantic_ai.models.test import TestModel

    q = _mock_embed_and_query()

    async def _go() -> None:
        with app.agent.override(model=TestModel()):
            await app.agent.run(
                "find my docs", deps=app.AgentDeps(user_id="u-42", tenant_id="acme")
            )

    asyncio.run(_go())
    assert q.called
    must = json.loads(q.calls.last.request.content)["filter"]["must"]
    assert {"key": "user_id", "match": {"value": "u-42"}} in must
    assert {"key": "tenant_id", "match": {"value": "acme"}} in must
