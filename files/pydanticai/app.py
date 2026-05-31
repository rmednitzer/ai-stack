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
    if API_KEY and authorization != f"Bearer {API_KEY}":
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


async def _run_agent(prompt: str) -> str:
    result = await runner.run(prompt)
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
    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="no user message provided")
    prompt = _text(user_msgs[-1].content)
    try:
        output = await _run_agent(prompt)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent run failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    model_id = req.model or OPENAI_MODEL_ID
    created = int(time.time())
    cid = f"chatcmpl-{uuid.uuid4().hex}"

    if req.stream:
        def _sse():
            chunk = {
                "id": cid, "object": "chat.completion.chunk", "created": created,
                "model": model_id,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": output}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            stop = {
                "id": cid, "object": "chat.completion.chunk", "created": created,
                "model": model_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(stop)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_sse(), media_type="text/event-stream")

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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
