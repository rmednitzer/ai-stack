"""
ai-stack Pydantic AI agentic runtime — an MIT-licensed alternative to the
LangGraph component.

Surfaces:
  * GET  /health                 — liveness/readiness
  * GET  /v1/models              — OpenAI-compatible model list (for Open WebUI)
  * POST /v1/chat/completions    — OpenAI-compatible chat (streaming + non-stream)
  * POST /run                    — simple {"prompt": ...} agent invocation

Pipeline: FastAPI -> DBOSAgent (durable, Postgres-checkpointed) -> Pydantic AI
Agent -> Ollama (OpenAI-compatible) inference, with optional SearXNG web-search
and Qdrant retrieval tools (durable @DBOS.step I/O) and OpenTelemetry tracing.

Durability degrades gracefully: with no POSTGRES_URI the agent still runs, just
without checkpointing/resume.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "llama3.2")
OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "pydanticai-agent")
SYSTEM_PROMPT = os.environ.get(
    "AGENT_SYSTEM_PROMPT",
    "You are a helpful assistant running on a self-hosted, EU-regulated AI stack.",
)
QDRANT_URI = os.environ.get("QDRANT_URI", "").rstrip("/")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
SEARXNG_QUERY_URL = os.environ.get("SEARXNG_QUERY_URL", "")
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "nomic-embed-text")
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
POSTGRES_URI = os.environ.get("POSTGRES_URI", "")
API_KEY = os.environ.get("PYDANTICAI_API_KEY", "")
REQUEST_TIMEOUT = float(os.environ.get("AGENT_HTTP_TIMEOUT", "60"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("pydanticai")

if not API_KEY:
    # The bearer-token gate (_check_auth) is a no-op when PYDANTICAI_API_KEY is
    # empty — every request to the agentic endpoints is accepted. Surface it so
    # an accidentally-blank Secret is not a silent open door.
    log.warning(
        "PYDANTICAI_API_KEY is empty — agentic endpoints are UNAUTHENTICATED; "
        "set an API key (and front the route with Authelia) before exposing them"
    )


# ---------------------------------------------------------------------------
# OpenTelemetry (best-effort; uses the chart-injected OTEL_* env vars)
# ---------------------------------------------------------------------------
def _setup_otel() -> bool:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create(
                {"service.name": os.environ.get("OTEL_SERVICE_NAME", "pydanticai")}
            )
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        return True
    except Exception as exc:  # noqa: BLE001 — telemetry must never break the app
        log.warning("OTel setup skipped: %s", exc)
        return False


_OTEL = _setup_otel()

# ---------------------------------------------------------------------------
# Model + agent (Ollama via its OpenAI-compatible API)
# ---------------------------------------------------------------------------
model = OpenAIChatModel(
    AGENT_MODEL,
    provider=OpenAIProvider(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama"),
)
agent = Agent(model, name="ai-stack-agent", instructions=SYSTEM_PROMPT, instrument=_OTEL)

_http = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

# ---------------------------------------------------------------------------
# Durable execution via DBOS (checkpointed in the shared PostgreSQL).
# Defined before tools so tool I/O can be wrapped as durable @DBOS.step calls,
# and before DBOS.launch() (called in the lifespan).
# ---------------------------------------------------------------------------
DURABLE = bool(POSTGRES_URI)
if DURABLE:
    from dbos import DBOS, DBOSConfig

    _dbos_config: DBOSConfig = {
        "name": "ai-stack-pydanticai",
        "system_database_url": POSTGRES_URI,
    }
    DBOS(config=_dbos_config)

    def durable_step(fn):
        """Register an I/O function as a durable DBOS step."""
        return DBOS.step()(fn)

    log.info("Durable execution enabled (DBOS + PostgreSQL)")
else:
    def durable_step(fn):  # passthrough when no Postgres
        return fn

    log.warning("POSTGRES_URI not set — running non-durable (no checkpointing)")


# ---------------------------------------------------------------------------
# Tool I/O (durable steps) + tool registration (only when backend configured)
# ---------------------------------------------------------------------------
@durable_step
async def _searxng_search(query: str) -> str:
    url = SEARXNG_QUERY_URL.replace("<query>", query)
    resp = await _http.get(url)
    resp.raise_for_status()
    hits = resp.json().get("results", [])[:RAG_TOP_K]
    return (
        "\n\n".join(
            f"{h.get('title', '')}\n{h.get('url', '')}\n{h.get('content', '')}" for h in hits
        )
        or "No results."
    )


@durable_step
async def _qdrant_retrieve(query: str) -> str:
    emb = await _http.post(
        f"{OLLAMA_BASE_URL}/api/embed", json={"model": EMBEDDING_MODEL, "input": query}
    )
    emb.raise_for_status()
    vector = emb.json()["embeddings"][0]
    headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}
    resp = await _http.post(
        f"{QDRANT_URI}/collections/{QDRANT_COLLECTION}/points/query",
        json={"query": vector, "limit": RAG_TOP_K, "with_payload": True},
        headers=headers,
    )
    resp.raise_for_status()
    points = resp.json().get("result", {}).get("points", [])
    return "\n\n".join(p.get("payload", {}).get("text", "") for p in points) or "No matches."


if SEARXNG_QUERY_URL:

    @agent.tool_plain
    async def web_search(query: str) -> str:
        """Search the public web via SearXNG and return the top results."""
        return await _searxng_search(query)


if QDRANT_URI:

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Retrieve relevant document chunks from the Qdrant vector store."""
        return await _qdrant_retrieve(query)


# DBOSAgent must be constructed before DBOS.launch().
if DURABLE:
    from pydantic_ai.durable_exec.dbos import DBOSAgent

    runner = DBOSAgent(agent)
else:
    runner = agent


# ---------------------------------------------------------------------------
# FastAPI surface
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    prompt: str
    thread_id: str | None = None  # reserved for multi-turn/session use


class RunResponse(BaseModel):
    output: str
    durable: bool


class ChatMessage(BaseModel):
    role: str
    content: Any  # str, or OpenAI content-parts list


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False


def _check_auth(authorization: str | None) -> None:
    # Constant-time comparison so the bearer-token check is not a timing oracle
    # on the only auth gate for the agentic endpoints. Compare bytes so a
    # non-ASCII Authorization header is rejected (401), not a TypeError (500).
    if API_KEY and not hmac.compare_digest(
        (authorization or "").encode(), f"Bearer {API_KEY}".encode()
    ):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _text(content: Any) -> str:
    """Coerce OpenAI message content (str or list of parts) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return str(content)


def _to_history(messages: list[ChatMessage]) -> tuple[str, list[Any]]:
    """Split an OpenAI-style messages array into (latest_user_prompt, history).

    The trailing user turn becomes the new prompt; everything before it is
    converted to Pydantic AI ``ModelRequest``/``ModelResponse`` history so
    multi-turn chats from Open WebUI keep their context (system + prior turns)
    instead of being treated as a fresh stateless prompt.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        UserPromptPart,
    )

    if not messages or messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="last message must be from 'user'")
    prompt = _text(messages[-1].content)

    history: list[Any] = []
    for m in messages[:-1]:
        text = _text(m.content)
        if not text:
            continue
        if m.role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=text)]))
        elif m.role == "system":
            history.append(ModelRequest(parts=[SystemPromptPart(content=text)]))
        else:  # user (and any other inbound role) -> user prompt
            history.append(ModelRequest(parts=[UserPromptPart(content=text)]))
    return prompt, history


async def _run_agent(prompt: str, history: list[Any] | None = None) -> str:
    result = await runner.run(prompt, message_history=history or None)
    return str(result.output)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if DURABLE:
        DBOS.launch()
    yield
    await _http.aclose()


app = FastAPI(title="ai-stack Pydantic AI runtime", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _check_auth(authorization)
    return {
        "object": "list",
        "data": [{"id": OPENAI_MODEL_ID, "object": "model", "owned_by": "ai-stack"}],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatRequest, authorization: str | None = Header(default=None)
):
    """OpenAI-compatible chat completion so Open WebUI can use the agent as a model."""
    _check_auth(authorization)
    prompt, history = _to_history(req.messages)

    model_id = req.model or OPENAI_MODEL_ID
    created = int(time.time())
    cid = f"chatcmpl-{uuid.uuid4().hex}"

    def _chunk(delta: dict[str, Any], finish: str | None) -> str:
        payload = {
            "id": cid, "object": "chat.completion.chunk", "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    if req.stream:
        # True token streaming via Pydantic AI's run_stream(). DBOS durable
        # execution checkpoints whole steps and is incompatible with streaming
        # partial output, so when DURABLE we fall back to running to completion
        # and emitting the result as a single chunk (still valid SSE).
        async def _sse():
            yield _chunk({"role": "assistant"}, None)
            try:
                if DURABLE:
                    output = await _run_agent(prompt, history)
                    yield _chunk({"content": output}, None)
                else:
                    async with agent.run_stream(
                        prompt, message_history=history or None
                    ) as result:
                        async for text in result.stream_text(delta=True):
                            if text:
                                yield _chunk({"content": text}, None)
            except Exception:  # noqa: BLE001 — surface a generic final SSE error
                # Detail is logged server-side only; never echo exception text to
                # the client (information exposure).
                log.exception("agent stream failed")
                yield _chunk({"content": "\n[error: agent run failed]"}, None)
                yield _chunk({}, "stop")
                yield "data: [DONE]\n\n"
                return
            yield _chunk({}, "stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(_sse(), media_type="text/event-stream")

    try:
        output = await _run_agent(prompt, history)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent run failed")
        raise HTTPException(status_code=502, detail="agent run failed") from exc

    return {
        "id": cid,
        "object": "chat.completion",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": output},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest, authorization: str | None = Header(default=None)) -> RunResponse:
    _check_auth(authorization)
    try:
        return RunResponse(output=await _run_agent(req.prompt), durable=DURABLE)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent run failed")
        raise HTTPException(status_code=502, detail="agent run failed") from exc
