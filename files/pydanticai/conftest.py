"""Pytest configuration for the Pydantic AI runtime.

app.py reads QDRANT_URI / OLLAMA_BASE_URL at import time. POSTGRES_URI is left
unset so DBOS (durable execution) is never imported and the agent runs in-process;
the HTTP layer (Ollama embed + Qdrant query) is mocked with respx, so no Ollama,
Qdrant, or Postgres instance is required.
"""

import os

# Force durable execution off for tests regardless of the developer's environment:
# with POSTGRES_URI set, app.py imports `dbos` (not a test dependency), which would
# make the suite fail/flap depending on the local shell. Remove it before import.
os.environ.pop("POSTGRES_URI", None)
os.environ.setdefault("QDRANT_URI", "http://qdrant.test:6333")
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama.test:11434")
