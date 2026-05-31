# Optional prebuilt image for the ai-stack Pydantic AI runtime.
#
# By default the chart mounts app.py from a ConfigMap and installs dependencies
# at startup with an initContainer (pydanticai.buildDeps=true) — self-contained
# but requires PyPI egress on every start. For air-gapped/hardened clusters,
# bake the dependencies into an image and disable the runtime install:
#
#   docker build -t <registry>/ai-stack-pydanticai:<tag> files/pydanticai
#   docker push  <registry>/ai-stack-pydanticai:<tag>
#
#   # values.yaml
#   pydanticai:
#     buildDeps: false
#     image:
#       repository: <registry>/ai-stack-pydanticai
#       tag: "<tag>"
#       digest: "sha256:..."   # pin per ADR-002
#
# app.py is still mounted from the ConfigMap at runtime (single source of truth);
# the baked copy below is for running the service outside the chart.
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

WORKDIR /app
COPY requirements.txt ./
RUN uv pip install --system --no-cache --require-hashes -r requirements.txt

COPY app.py ./

# Match the chart's restricted securityContext (runAsNonRoot, runAsUser 1000).
USER 1000
EXPOSE 8000

ENTRYPOINT ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
