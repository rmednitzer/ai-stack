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


# --- ADR-018: useful agent defaults (bounded runs, temperature, prompt) ---


def test_usage_limits_default_to_bounded() -> None:
    """Runs are bounded, not unlimited (ADR-018).

    pydantic-ai's implicit request cap is 50 and its token/tool-call caps are
    unbounded; the agent ships a tighter request bound and a tool-call cap so a
    tool-using loop cannot run away on local inference. The total-token cap is
    opt-in (None = unbounded) to avoid truncating long answers by default.
    """
    assert app.USAGE_LIMITS.request_limit == 12
    assert app.USAGE_LIMITS.tool_calls_limit == 8
    assert app.USAGE_LIMITS.total_tokens_limit is None


def test_default_temperature_is_low() -> None:
    """A low default temperature favours grounded, tool-using answers (ADR-018)."""
    assert app.AGENT_TEMPERATURE == 0.2
    assert app._MODEL_SETTINGS is not None
    assert app._MODEL_SETTINGS["temperature"] == 0.2


def test_optional_int_env_semantics() -> None:
    """Unset -> code default; explicitly empty -> None (unbounded); value -> int."""
    import os
    from unittest import mock

    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AGENT_X_LIMIT", None)
        assert app._optional_int_env("AGENT_X_LIMIT", 7) == 7
    with mock.patch.dict(os.environ, {"AGENT_X_LIMIT": ""}):
        assert app._optional_int_env("AGENT_X_LIMIT", 7) is None
    with mock.patch.dict(os.environ, {"AGENT_X_LIMIT": "3"}):
        assert app._optional_int_env("AGENT_X_LIMIT", 7) == 3


def test_default_system_prompt_is_grounded_and_transparent() -> None:
    """The default prompt is tool-aware, grounded, and AI-transparent (ADR-018)."""
    prompt = app.SYSTEM_PROMPT.lower()
    assert "tool" in prompt  # instructs tool use
    assert "ai" in prompt  # AI-transparency (AI Act)
    assert "human" in prompt  # "do not claim to be human"
