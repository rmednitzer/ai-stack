"""
ai-stack Pydantic AI agentic runtime — an MIT-licensed alternative to the
LangGraph component.

Pipeline:
    FastAPI  ->  DBOSAgent (durable, Postgres-checkpointed)  ->  Pydantic AI Agent
    ->  Ollama (OpenAI-compatible) for inference
        + optional SearXNG web-search and Qdrant retrieval tools
        + OpenTelemetry tracing (via the chart's injected OTEL_* env)

This is a deliberately small *reference* you extend: add your own tools
(decorate I/O tools with `@DBOS.step` for full durability), structured output
types, MCP servers, etc. See docs/components/pydanticai.md.

Durability degrades gracefully: with no POSTGRES_URI the agent still runs, just
without checkpointing/resume.
"""

import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "llama3.2")
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
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("pydanticai")


# ---------------------------------------------------------------------------
# OpenTelemetry (best-effort; uses the chart-injected OTEL_* env vars)
# ---------------------------------------------------------------------------
def _setup_otel() -> bool:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
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
# Model: Ollama via its OpenAI-compatible API
# ---------------------------------------------------------------------------
model = OpenAIChatModel(
    AGENT_MODEL,
    provider=OpenAIProvider(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama"),
)

# instrument=True emits OpenTelemetry spans when a tracer provider is configured.
agent = Agent(
    model,
    name="ai-stack-agent",
    instructions=SYSTEM_PROMPT,
    instrument=_OTEL,
)

# Shared async HTTP client for tools.
_http = httpx.AsyncClient(timeout=60.0)


# ---------------------------------------------------------------------------
# Optional tools — registered only when their backing service is configured.
# For full durability of tool I/O under DBOS, wrap the body in @DBOS.step.
# ---------------------------------------------------------------------------
if SEARXNG_QUERY_URL:

    @agent.tool_plain
    async def web_search(query: str) -> str:
        """Search the public web via SearXNG and return the top results."""
        url = SEARXNG_QUERY_URL.replace("<query>", query)
        resp = await _http.get(url)
        resp.raise_for_status()
        hits = resp.json().get("results", [])[:RAG_TOP_K]
        return (
            "\n\n".join(
                f"{h.get('title', '')}\n{h.get('url', '')}\n{h.get('content', '')}"
                for h in hits
            )
            or "No results."
        )


if QDRANT_URI:

    @agent.tool_plain
    async def search_knowledge_base(query: str) -> str:
        """Retrieve relevant document chunks from the Qdrant vector store."""
        emb = await _http.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": EMBEDDING_MODEL, "input": query},
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


# ---------------------------------------------------------------------------
# Durable execution via DBOS (checkpointed in the shared PostgreSQL).
# DBOSAgent must be constructed before DBOS.launch() (called in the lifespan).
# ---------------------------------------------------------------------------
DURABLE = bool(POSTGRES_URI)
runner = agent
if DURABLE:
    from dbos import DBOS, DBOSConfig
    from pydantic_ai.durable_exec.dbos import DBOSAgent

    dbos_config: DBOSConfig = {
        "name": "ai-stack-pydanticai",
        "system_database_url": POSTGRES_URI,
    }
    DBOS(config=dbos_config)
    runner = DBOSAgent(agent)
    log.info("Durable execution enabled (DBOS + PostgreSQL)")
else:
    log.warning("POSTGRES_URI not set — running non-durable (no checkpointing)")


# ---------------------------------------------------------------------------
# FastAPI surface
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    prompt: str
    thread_id: str | None = None  # reserved for multi-turn/session use


class RunResponse(BaseModel):
    output: str
    durable: bool


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


@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest, authorization: str | None = Header(default=None)) -> RunResponse:
    # Optional bearer-token auth (defense in depth; NetworkPolicy already gates ingress).
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    try:
        result = await runner.run(req.prompt)
        return RunResponse(output=str(result.output), durable=DURABLE)
    except Exception as exc:  # noqa: BLE001
        log.exception("agent run failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
