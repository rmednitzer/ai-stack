"""Pytest configuration for the Pydantic AI runtime.

app.py reads QDRANT_URI / OLLAMA_BASE_URL at import time. POSTGRES_URI is left
unset so DBOS (durable execution) is never imported and the agent runs in-process;
the HTTP layer (Ollama embed + Qdrant query) is mocked with respx, so no Ollama,
Qdrant, or Postgres instance is required.
"""

import os

os.environ.setdefault("QDRANT_URI", "http://qdrant.test:6333")
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama.test:11434")
