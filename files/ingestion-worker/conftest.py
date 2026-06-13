"""Pytest configuration for the ingestion worker.

worker.py reads TIKA_SERVER_URL / OLLAMA_BASE_URL / QDRANT_URI at import time, so
they must be present before the module is imported. POSTGRES_URI is deliberately
left unset: the corpus state machine then stays disabled (its __init__ returns
early without connecting), and the Valkey client is lazy, so importing the module
performs no network I/O. The HTTP layer is mocked with respx in the tests.
"""

import os

os.environ.setdefault("TIKA_SERVER_URL", "http://tika.test:9998")
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama.test:11434")
os.environ.setdefault("QDRANT_URI", "http://qdrant.test:6333")
