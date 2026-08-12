# Optional prebuilt image for the ai-stack ingestion worker.
#
# By default the chart ships worker.py via a ConfigMap and installs the Python
# dependencies at pod startup with an initContainer (ingestionWorker.buildDeps=true),
# which keeps the chart self-contained but requires PyPI egress on every start.
#
# For air-gapped or hardened deployments, bake the dependencies into an image
# instead and disable the runtime install:
#
#   docker build -t <registry>/ai-stack-ingestion-worker:<tag> files/ingestion-worker
#   docker push  <registry>/ai-stack-ingestion-worker:<tag>
#
#   # values.yaml
#   ingestionWorker:
#     buildDeps: false
#     image:
#       repository: <registry>/ai-stack-ingestion-worker
#       tag: "<tag>@sha256:..."   # digest-pinned per ADR-002 (tag is the single source of truth)
#
# worker.py is still mounted from the ConfigMap at runtime (single source of
# truth), so this image only needs to provide the importable dependencies; the
# baked copy below is for running the worker outside the chart.
ARG PYTHON_VERSION=3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc
FROM python:${PYTHON_VERSION}

WORKDIR /app
# requirements.txt is a hashed universal lock (make ingestion-worker-lock);
# --require-hashes makes the bake fail closed on any tampered/substituted dist.
# Baking fsspec source backends (ingestionWorker.sources) into this image?
# Append them to requirements.in, recompile the lock, then build.
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY worker.py ./

# Match the chart's restricted securityContext (runAsNonRoot, runAsUser 1000).
USER 1000

ENTRYPOINT ["python", "/app/worker.py"]
