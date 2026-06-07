# ai-stack How-To Guide

Practical, task-oriented guide for deploying, operating, and maintaining the ai-stack Helm chart. For architecture overview and configuration reference, see [README.md](README.md).

---

## Table of Contents

1. [Installation](#1-installation)
   - [Lab environment](#11-lab-environment)
   - [Production environment](#12-production-environment)
   - [Air-gapped / offline install](#13-air-gapped--offline-install)
   - [Air-gapped install with Zarf](#14-air-gapped-install-with-zarf)
2. [Day-1 Setup](#2-day-1-setup)
   - [Pull your first models](#21-pull-your-first-models)
   - [Access Open WebUI](#22-access-open-webui)
   - [Create your admin account](#23-create-your-admin-account)
   - [Verify the deployment](#24-verify-the-deployment)
3. [Working with Models](#3-working-with-models)
   - [List available models](#31-list-available-models)
   - [Pull additional models](#32-pull-additional-models)
   - [Remove a model](#33-remove-a-model)
   - [Set a default model](#34-set-a-default-model)
4. [RAG (Retrieval-Augmented Generation)](#4-rag-retrieval-augmented-generation)
   - [Upload documents via the UI](#41-upload-documents-via-the-ui)
   - [Configure the embedding model](#42-configure-the-embedding-model)
   - [Tune chunking and retrieval](#43-tune-chunking-and-retrieval)
   - [Enable web search](#44-enable-web-search)
5. [Async Document Ingestion](#5-async-document-ingestion)
   - [Enable the ingestion worker](#51-enable-the-ingestion-worker)
   - [Enqueue documents programmatically](#52-enqueue-documents-programmatically)
   - [Monitor ingestion status](#53-monitor-ingestion-status)
6. [External LLM Providers](#6-external-llm-providers)
   - [Add OpenAI](#61-add-openai)
   - [Add Azure OpenAI](#62-add-azure-openai)
   - [Add Anthropic (Claude)](#63-add-anthropic-claude)
   - [Use an external secret manager](#64-use-an-external-secret-manager)
7. [GPU Acceleration](#7-gpu-acceleration)
   - [Enable GPU for Ollama](#71-enable-gpu-for-ollama)
   - [Verify GPU access](#72-verify-gpu-access)
8. [Agentic Workloads (LangGraph)](#8-agentic-workloads-langgraph-or-pydantic-ai)
   - [Enable LangGraph with PostgreSQL](#81-enable-langgraph-with-postgresql)
   - [Deploy a custom graph](#82-deploy-a-custom-graph)
   - [Test the LangGraph API](#83-test-the-langgraph-api)
9. [MCP Tool Integration (MCPO)](#9-mcp-tool-integration-mcpo)
   - [Enable MCPO](#91-enable-mcpo)
   - [Configure MCP servers](#92-configure-mcp-servers)
10. [PostgreSQL Modes](#10-postgresql-modes)
    - [Standalone (lab)](#101-standalone-lab)
    - [CloudNativePG (production HA)](#102-cloudnativepg-production-ha)
    - [External managed database](#103-external-managed-database)
11. [Ingress and TLS](#11-ingress-and-tls)
    - [Expose Open WebUI with NGINX](#111-expose-open-webui-with-nginx)
    - [Expose Open WebUI with Envoy Gateway](#112-expose-open-webui-with-envoy-gateway)
    - [Automated TLS with cert-manager](#113-automated-tls-with-cert-manager)
12. [Authentication with Authelia (SSO / OIDC)](#12-authentication-with-authelia-sso--oidc)
    - [Enable Authelia](#121-enable-authelia)
    - [Create users](#122-create-users)
    - [Enable MFA (two-factor)](#123-enable-mfa-two-factor)
    - [Use PostgreSQL as storage backend](#124-use-postgresql-as-storage-backend)
    - [Expose Authelia via ingress](#125-expose-authelia-via-ingress)
    - [Verify OIDC integration](#126-verify-oidc-integration)
13. [Networking and Security](#13-networking-and-security)
    - [Network policies](#131-network-policies)
    - [Pod security](#132-pod-security)
    - [Secret management](#133-secret-management)
    - [Rotate secrets](#134-rotate-secrets)
14. [Observability](#14-observability)
    - [Enable OpenTelemetry](#141-enable-opentelemetry)
    - [Enable Prometheus ServiceMonitors](#142-enable-prometheus-servicemonitors)
    - [PII redaction](#143-pii-redaction)
15. [Scaling](#15-scaling)
    - [Horizontal Pod Autoscaling](#151-horizontal-pod-autoscaling)
    - [Manual scaling](#152-manual-scaling)
    - [Resource tuning](#153-resource-tuning)
16. [Upgrading](#16-upgrading)
    - [Upgrade the chart](#161-upgrade-the-chart)
    - [Upgrade individual component images](#162-upgrade-individual-component-images)
    - [Upgrade with zero downtime](#163-upgrade-with-zero-downtime)
17. [GitOps with ArgoCD](#17-gitops-with-argocd)
    - [Deploy the lab application](#171-deploy-the-lab-application)
    - [Deploy the production application](#172-deploy-the-production-application)
    - [Customizing the application manifests](#173-customizing-the-application-manifests)
    - [Ignore differences](#174-ignore-differences)
    - [Disaster recovery](#175-disaster-recovery)
18. [EU Compliance](#18-eu-compliance)
    - [AI transparency disclosure](#181-ai-transparency-disclosure)
    - [Data retention](#182-data-retention)
    - [External API provider governance](#183-external-api-provider-governance)
    - [Encryption at rest](#184-encryption-at-rest)
    - [Compliance documentation](#185-compliance-documentation)
19. [Troubleshooting](#19-troubleshooting)
    - [Pods stuck in Pending](#191-pods-stuck-in-pending)
    - [Ollama out of memory](#192-ollama-out-of-memory)
    - [Open WebUI cannot reach Ollama](#193-open-webui-cannot-reach-ollama)
    - [NetworkPolicy blocking traffic](#194-networkpolicy-blocking-traffic)
    - [PVC stuck in Pending](#195-pvc-stuck-in-pending)
    - [Secrets not generated](#196-secrets-not-generated)
    - [Helm test failures](#197-helm-test-failures)
    - [GPU not detected](#198-gpu-not-detected)
20. [Uninstall](#20-uninstall)

---

## 1. Installation

### 1.1 Lab Environment

Lab mode deploys a single-replica stack with relaxed resource limits, suitable for development and evaluation.

**Prerequisites:**

- Kubernetes 1.27+ cluster (minikube, kind, k3s, or managed)
- Helm 3.12+
- At least 8 GB RAM available in the cluster
- A default StorageClass (or use `emptyDir` for ephemeral testing)

**Install:**

```bash
# Create the namespace and install with lab defaults
helm install ai-stack . -n ai-stack --create-namespace
```

**Lab with GPU:**

```bash
helm install ai-stack . -n ai-stack --create-namespace \
  --set ollama.gpu.enabled=true
```

### 1.2 Production Environment

Production mode enables HA replicas, autoscaling, TLS ingress, and observability.

**Additional prerequisites:**

- NVIDIA GPU Operator (for Ollama GPU acceleration)
- Prometheus Operator CRDs (for ServiceMonitor resources)
- cert-manager (for automated TLS provisioning)
- An ingress controller (Envoy Gateway or NGINX)

**Install:**

```bash
helm install ai-stack . -n ai-stack --create-namespace \
  -f values.yaml -f values-prod.yaml
```

**Customize before installing:**

1. Copy `values-prod.yaml` to `values-prod-override.yaml`
2. Edit your overrides (hostname, storage class, resource limits)
3. Install with both files:

```bash
helm install ai-stack . -n ai-stack --create-namespace \
  -f values.yaml -f values-prod.yaml -f values-prod-override.yaml
```

### 1.3 Air-gapped / Offline Install

For environments without internet access:

1. **Mirror container images** to your internal registry:

```bash
# List all images used by the chart
helm template ai-stack . | grep "image:" | sort -u

# Pull, tag, and push each image to your registry
docker pull ghcr.io/open-webui/open-webui:v0.9.5
docker tag ghcr.io/open-webui/open-webui:v0.9.5 registry.internal/open-webui:v0.9.5
docker push registry.internal/open-webui:v0.9.5
# Repeat for all images...
```

2. **Override image repositories** in your values file:

```yaml
openwebui:
  image:
    repository: registry.internal/open-webui
    tag: "v0.9.5"
ollama:
  image:
    repository: registry.internal/ollama
    tag: "0.24.0"
# ... repeat for all components
```

3. **Configure image pull secrets** if your registry requires authentication:

```yaml
global:
  imagePullSecrets:
    - name: my-registry-secret
```

4. **Pre-download Ollama models** and load them into the PVC, since `ollama pull` requires internet access. See [Section 3](#3-working-with-models).

### 1.4 Air-gapped Install with Zarf

[Zarf](https://zarf.dev/) automates air-gapped deployments by packaging the Helm chart, all container images, and configuration into a single signed, declarative tarball. This eliminates the manual image mirroring described in [Section 1.3](#13-air-gapped--offline-install).

The repository includes a `zarf.yaml` package definition with the core stack as a required component and optional components (LangGraph, MCPO, OTel Collector) that can be selected at deploy time.

**Prerequisites:**

- [Zarf CLI](https://docs.zarf.dev/getting-started/) installed on the build machine (internet-connected)
- Zarf initialized on the target cluster (`zarf init`)
- Kubernetes 1.27+ on the target cluster

**Step 1 — Build the package (internet-connected machine):**

```bash
cd ai-stack/
zarf package create --confirm
```

This produces a file like `zarf-package-ai-stack-amd64-1.0.0.tar.zst` (~15-25 GB depending on selected components). Zarf automatically pulls all images listed in `zarf.yaml` and bundles them alongside the Helm chart.

**Step 2 — Transfer the package:**

Copy the `.tar.zst` file to the air-gapped environment via USB, S3 bucket, or any out-of-band transfer method.

**Step 3 — Initialize Zarf on the target cluster (one-time):**

If Zarf has not been initialized on the target cluster yet:

```bash
zarf init --confirm
```

This deploys an in-cluster registry and injector that Zarf uses to serve images.

**Step 4 — Deploy:**

```bash
# Deploy with defaults (core stack only)
zarf package deploy zarf-package-ai-stack-amd64-1.0.0.tar.zst --confirm

# Deploy with optional components
zarf package deploy zarf-package-ai-stack-amd64-1.0.0.tar.zst \
  --components="ai-stack,langgraph,mcpo" --confirm
```

Zarf pushes the images to the in-cluster registry and runs `helm install` with the image references rewritten to point at the local registry.

**Step 5 — Load Ollama models:**

Zarf handles images, but Ollama models must still be loaded manually in an air-gapped cluster. On the internet-connected machine:

```bash
# Pull the model locally
ollama pull llama3.2
ollama pull nomic-embed-text

# Export to a tarball
# Models are stored under ~/.ollama/models/
tar czf ollama-models.tar.gz -C ~/.ollama models/
```

On the air-gapped cluster:

```bash
# Copy the models into the Ollama PVC
kubectl cp ollama-models.tar.gz ai-stack/ai-stack-ollama-0:/tmp/
kubectl exec -n ai-stack ai-stack-ollama-0 -- \
  tar xzf /tmp/ollama-models.tar.gz -C /root/.ollama/
kubectl exec -n ai-stack ai-stack-ollama-0 -- rm /tmp/ollama-models.tar.gz

# Restart Ollama to pick up the models
kubectl rollout restart -n ai-stack deploy/ai-stack-ollama
```

**Upgrading:**

Build a new package with the updated chart/images and redeploy:

```bash
zarf package deploy zarf-package-ai-stack-amd64-<new-version>.tar.zst --confirm
```

Zarf performs a `helm upgrade` under the hood.

---

## 2. Day-1 Setup

### 2.1 Pull Your First Models

After installation, Ollama starts with no models. Pull a chat model and an embedding model:

```bash
# Chat model
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull llama3.2

# Embedding model (required for RAG)
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull nomic-embed-text
```

For larger models (requires more RAM/VRAM):

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull qwen3:14b
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull deepseek-r1:14b
```

### 2.2 Access Open WebUI

**Port-forward (lab):**

```bash
kubectl port-forward -n ai-stack svc/ai-stack-openwebui 8080:8080
# Open http://localhost:8080
```

**Via ingress (production):**

If ingress is configured, access via the hostname defined in your values (e.g., `https://ai.example.com`).

### 2.3 Create Your Admin Account

On first access, Open WebUI prompts you to create an admin account. This account controls:

- User management and permissions
- Model access control
- System settings and configuration
- Pipeline and tool management

**Important:** The first account created automatically becomes the admin. Do this immediately after deployment in production.

### 2.4 Verify the Deployment

```bash
# All pods should be Running
kubectl get pods -n ai-stack

# NetworkPolicies should be present for each component
kubectl get networkpolicies -n ai-stack

# Secrets should be auto-generated
kubectl get secrets -n ai-stack -l app.kubernetes.io/part-of=ai-stack

# ServiceAccounts per component
kubectl get serviceaccounts -n ai-stack

# Run Helm tests (connectivity checks)
helm test ai-stack -n ai-stack
```

---

## 3. Working with Models

### 3.1 List Available Models

```bash
# List models loaded in Ollama
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama list
```

### 3.2 Pull Additional Models

```bash
# Pull any model from the Ollama library
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull <model-name>

# Examples
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull mistral
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull codellama:13b
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull llama3.2-vision:11b
```

**Model storage:** Models are stored in the Ollama PVC (`/root/.ollama`). Ensure the PVC is large enough — a 14B parameter model typically requires 9-10 GB of storage. The default lab PVC is 50 GB; production is 200 GB.

### 3.3 Remove a Model

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama rm <model-name>
```

### 3.4 Set a Default Model

In Open WebUI, go to **Admin Panel > Settings > Models** and configure the default model. Users can still select other available models from the model picker.

---

## 4. RAG (Retrieval-Augmented Generation)

RAG allows the AI to answer questions using your own documents. The stack includes all components needed: Tika (document parsing), Qdrant (vector storage), and Ollama (embeddings). For the conversational + RAG flow at a glance, see [docs/architecture/REFERENCE.md §2](docs/architecture/REFERENCE.md#2-conversational--rag-flow-open-webui).

### 4.1 Upload Documents via the UI

1. Open the Open WebUI chat interface
2. Click the **+** button or drag and drop files into the chat
3. Supported formats: PDF, DOCX, PPTX, XLSX, TXT, HTML, Markdown, and more (via Tika)
4. Documents are automatically extracted, chunked, embedded, and stored in Qdrant

### 4.2 Configure the Embedding Model

The default embedding model is `nomic-embed-text`. To change it:

```yaml
openwebui:
  env:
    RAG_EMBEDDING_MODEL: "bge-m3"
```

Then pull the new model:

```bash
kubectl exec -n ai-stack deploy/ai-stack-ollama -- ollama pull bge-m3
```

Upgrade the release:

```bash
helm upgrade ai-stack . -n ai-stack
```

**Note:** Changing the embedding model requires re-embedding all existing documents, as vector dimensions and representations differ between models.

### 4.3 Tune Chunking and Retrieval

Adjust these parameters in your values override:

```yaml
openwebui:
  env:
    # Larger chunks = more context per retrieval, but fewer distinct matches
    RAG_CHUNK_SIZE: "1500"
    # Overlap prevents splitting relevant content at chunk boundaries
    RAG_CHUNK_OVERLAP: "100"
    # Number of top matching chunks to include in the prompt
    RAG_TOP_K: "5"
    # Minimum similarity score (0.0 = return all, higher = stricter)
    RAG_RELEVANCE_THRESHOLD: "0.0"
```

**Guidelines:**

| Scenario | Chunk Size | Overlap | Top K |
|----------|-----------|---------|-------|
| Short, factual documents | 500-800 | 50 | 3-5 |
| Long technical documents | 1500-2000 | 100-200 | 5-8 |
| Legal/regulatory text | 1000-1500 | 200 | 8-10 |
| Code repositories | 800-1200 | 100 | 5-7 |

### 4.4 Enable Web Search

Web search via SearXNG is enabled by default. It allows the AI to search the internet for answers when document retrieval is insufficient.

To use web search in a conversation, type a question and enable the "Web Search" toggle in the chat interface, or configure it as the default behavior in Admin Panel settings.

---

## 5. Async Document Ingestion

For bulk document processing or integration with external systems, use the async ingestion worker instead of the UI upload.

### 5.1 Enable the Ingestion Worker

```yaml
ingestionWorker:
  enabled: true
valkey:
  persistence:
    enabled: true  # Persist task queue across restarts
```

```bash
helm upgrade ai-stack . -n ai-stack
```

### 5.2 Enqueue Documents Programmatically

Connect to Valkey and submit tasks via `XADD`:

```bash
# Port-forward to Valkey
kubectl port-forward -n ai-stack svc/ai-stack-valkey 6379:6379

# Submit an ingestion task
redis-cli -p 6379 XADD ingestion:documents '*' \
  task_id "doc-001" \
  file_url "https://example.com/report.pdf" \
  filename "report.pdf" \
  collection "documents"     # optional; tags the corpus state machine (not the upsert target)
```

Or from within the cluster (e.g., from a script or application):

```python
import redis

r = redis.Redis(host='ai-stack-valkey', port=6379)
r.xadd('ingestion:documents', {
    'task_id': 'doc-001',
    'file_url': 'https://example.com/report.pdf',
    'filename': 'report.pdf',
    'collection': 'documents',  # optional; corpus-state-machine key + payload tag (not upsert routing)
})
```

### 5.3 Monitor Ingestion Status

```bash
# Check status of a specific task
redis-cli -p 6379 HGETALL ingestion:status:doc-001

# List recent messages in the stream
redis-cli -p 6379 XRANGE ingestion:documents - + COUNT 10

# Check consumer group lag
redis-cli -p 6379 XINFO GROUPS ingestion:documents
```

Status values advance through `processing` → `extracting` → `chunking` → `embedding` → `upserting` → `done` (or `failed`). A task not yet picked up has no status hash. See the [ingestion-worker spec](docs/components/ingestion-worker-spec.md) for the full task/status contract, retry semantics, and the corpus state machine.

### 5.4 Ingest from object stores and network shares

The worker accepts three kinds of `file_url` (full contract: [spec §2.1](docs/components/ingestion-worker-spec.md)):

- **`http(s)://`** — including **presigned** S3 / GCS / Azure URLs (works out of the box, no credentials in the worker).
- **Local paths** — mount an **NFS / SMB** share into the worker with the CSI driver and enqueue its path. Recommended and lowest-risk: the kubelet does the mount, so the default-deny NetworkPolicy does not apply and no credentials reach the worker.
- **Native scheme URLs** (`s3://`, `gs://`, `az://`, `smb://`, `sftp://`, …) via **opt-in** fsspec connectors ([ADR-007](docs/architecture/ADR-007-ingestion-source-connectors.md)):

  ```yaml
  ingestionWorker:
    sources:
      enabled: true
      schemes: [s3]                       # deny-by-default: only these are honored
      pipPackages: [fsspec, s3fs]         # install only the backends you use
      existingSecret: ingest-cloud-creds  # AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / …
  ```

  Then enqueue `file_url: s3://my-bucket/reports/q3.pdf`. Native **non-HTTPS**
  protocols (SMB/NFS/SFTP) additionally require you to open the matching
  NetworkPolicy egress — the chart does not open it for you.

---

## 6. External LLM Providers

Add cloud-hosted models alongside local Ollama inference. Users see all models in the Open WebUI model picker.

### 6.1 Add OpenAI

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: openai
      baseUrl: "https://api.openai.com/v1"
      apiKey: "sk-..."
```

### 6.2 Add Azure OpenAI

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: azure-openai
      baseUrl: "https://<resource>.openai.azure.com/openai/deployments/<deployment>"
      apiKey: "<your-azure-key>"
```

### 6.3 Add Anthropic (Claude)

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: anthropic
      baseUrl: "https://api.anthropic.com/v1"
      apiKey: "sk-ant-..."
```

**Note:** Anthropic integration uses its OpenAI-compatible endpoint, configured like any other `externalAPIs` provider. The pinned Open WebUI image speaks to OpenAI-compatible providers directly, so no separate translation layer is required.

### 6.4 Use an External Secret Manager

For production, never store API keys in values files. Use existing Kubernetes Secrets (created by ESO, Vault, or manually):

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: openai
      baseUrl: "https://api.openai.com/v1"
      existingSecret:
        name: "openai-api-key"    # Must exist in the release namespace
        key: "api-key"            # Key within the Secret
```

---

## 7. GPU Acceleration

### 7.1 Enable GPU for Ollama

**Prerequisites:** NVIDIA GPU Operator must be installed in the cluster.

```yaml
ollama:
  gpu:
    enabled: true
    count: 1                      # Number of GPUs to allocate
    resourceName: nvidia.com/gpu  # Resource name from GPU operator
```

```bash
helm upgrade ai-stack . -n ai-stack
```

### 7.2 Verify GPU Access

```bash
# Check Ollama GPU detection
kubectl exec -n ai-stack deploy/ai-stack-ollama -- nvidia-smi
```

---

## 8. Agentic Workloads (LangGraph or Pydantic AI)

The chart ships two interchangeable agentic runtimes — **LangGraph** (graph-based; the `langgraph-server` image is Elastic License 2.0, and production self-hosting needs a commercial key) and **Pydantic AI** (durable execution via DBOS; fully MIT/Apache-2.0, see §8.4). Both enable stateful, multi-step workflows with tool calling and checkpoint persistence, and share the same Ollama/Qdrant/SearXNG/MCPO/PostgreSQL integrations. For the design rationale, integration patterns, and anti-patterns, see [docs/architecture/REFERENCE.md §3 Agentic flow](docs/architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).

### 8.1 Enable LangGraph with PostgreSQL

LangGraph requires PostgreSQL for checkpoint storage:

```yaml
langgraph:
  enabled: true
postgres:
  enabled: true
  mode: standalone  # Use 'cnpg' for production HA
```

```bash
helm upgrade ai-stack . -n ai-stack
```

### 8.2 Deploy a Custom Graph

**Option A: Custom image (recommended)**

1. Create your graph code following the [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
2. Build the image:

```bash
langgraph build -t my-registry/my-graphs:latest
docker push my-registry/my-graphs:latest
```

3. Override the image in values:

```yaml
langgraph:
  image:
    repository: my-registry/my-graphs
    tag: "latest"
```

**Option B: Volume mount**

Place graph code in the `/deps/graphs` persistent volume:

```bash
kubectl cp my-graph.py ai-stack/ai-stack-langgraph-<pod>:/deps/graphs/
```

### 8.3 Test the LangGraph API

```bash
# Port-forward
kubectl port-forward -n ai-stack svc/ai-stack-langgraph 8000:8000

# Health check
curl http://localhost:8000/ok

# List available assistants
curl http://localhost:8000/assistants \
  -H "x-api-key: $(kubectl get secret -n ai-stack ai-stack-langgraph-secret -o jsonpath='{.data.api-key}' | base64 -d)"
```

### 8.4 Pydantic AI (MIT alternative)

For a fully **MIT/Apache-2.0** agentic runtime, enable Pydantic AI instead of (or alongside) LangGraph. It uses DBOS for durable execution, checkpointed in the same PostgreSQL:

```yaml
pydanticai:
  enabled: true
postgres:
  enabled: true   # DBOS checkpoints durable runs here; without it, runs are non-durable
```

```bash
helm upgrade ai-stack . -n ai-stack
```

Test it:

```bash
kubectl port-forward -n ai-stack svc/ai-stack-pydanticai 8000:8000

# Health
curl http://localhost:8000/health

# Run the agent (bearer token from the auto-generated secret)
curl -X POST http://localhost:8000/run \
  -H "Authorization: Bearer $(kubectl get secret -n ai-stack ai-stack-pydanticai-secret -o jsonpath='{.data.api-key}' | base64 -d)" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello and name three EU AI Act obligations."}'
```

The agent also speaks the **OpenAI-compatible API** (`GET /v1/models`, `POST /v1/chat/completions`, streaming and non-streaming), so it can be registered directly in Open WebUI's model picker — set `pydanticai.exposeToOpenWebUI=true` and the chart wires the `/v1` endpoint, API key, and NetworkPolicy egress automatically. The model appears as `pydanticai.env.OPENAI_MODEL_ID`.

The agent lives in `files/pydanticai/app.py` as a reference — extend it with your own tools (`@DBOS.step` for durable I/O), structured outputs, or MCP servers. See [docs/components/pydanticai.md](docs/components/pydanticai.md).

---

## 9. MCP Tool Integration (MCPO)

MCPO bridges Model Context Protocol (MCP) servers to OpenAPI endpoints that Open WebUI can consume as tools. The same MCPO instance is the recommended tool surface for LangGraph agents — see [docs/architecture/REFERENCE.md §3](docs/architecture/REFERENCE.md#3-agentic-flow-langgraph-or-pydantic-ai).

### 9.1 Enable MCPO

```yaml
mcpo:
  enabled: true
```

### 9.2 Configure MCP Servers

Add MCP server definitions in your values:

```yaml
mcpo:
  enabled: true
  config:
    mcpServers:
      # Local filesystem access
      filesystem:
        command: "npx"
        args:
          - "-y"
          - "@modelcontextprotocol/server-filesystem"
          - "/data"
      # Remote SSE-based MCP server
      remote-tools:
        url: "https://mcp.example.com/sse"
        type: "sse"
```

After deploying, configure Open WebUI to use the MCPO endpoint as an OpenAPI tool source under **Admin Panel > Settings > Tools**.

---

## 10. PostgreSQL Modes

PostgreSQL is **enabled by default**. It backs Open WebUI's high-availability
state (its own `openwebui` database, set via `openwebui.databaseName`) as well as
LangGraph and Pydantic AI (durable execution via DBOS), and optionally Authelia.
The three provisioning modes below cover lab through enterprise. Set
`postgres.enabled=false` only for an ephemeral single-pod lab, where Open WebUI
falls back to a local SQLite file (see [§15 Scaling](#15-scaling) for the
single-replica caveat that implies).

### 10.1 Standalone (Lab)

Single-instance PostgreSQL — no HA, suitable for development:

```yaml
postgres:
  enabled: true
  mode: standalone
```

### 10.2 CloudNativePG (Production HA)

**Prerequisites:** Install the CloudNativePG operator (v1.25+):

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg cnpg/cloudnative-pg -n cnpg-system --create-namespace
```

Then configure:

```yaml
postgres:
  enabled: true
  mode: cnpg
  tls:
    mode: require
  cnpg:
    instances: 3          # 1 primary + 2 replicas
    storage:
      size: 50Gi
    pooler:
      enabled: true       # PgBouncer connection pooling
    monitoring:
      enabled: true       # Prometheus metrics
```

CNPG provides:

- Streaming replication with automated failover
- Rolling updates without downtime
- Automated TLS certificate provisioning
- PgBouncer connection pooling
- Prometheus metrics endpoint

### 10.3 External Managed Database

Use your own PostgreSQL (RDS, Cloud SQL, Supabase, etc.):

```yaml
postgres:
  enabled: true
  mode: external
  database: "langgraph"
  user: "langgraph"
  tls:
    mode: require
  external:
    host: "my-rds.abc123.us-east-1.rds.amazonaws.com"
    port: 5432
    existingSecret:
      name: "rds-password"
      key: "password"
```

---

## 11. Ingress and TLS

### 11.1 Expose Open WebUI with NGINX

```yaml
openwebui:
  ingress:
    enabled: true
    className: "nginx"
    annotations:
      nginx.ingress.kubernetes.io/proxy-body-size: "50m"
      nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    hosts:
      - host: ai.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: ai-tls
        hosts:
          - ai.example.com
```

### 11.2 Expose Open WebUI with Envoy Gateway

```yaml
openwebui:
  ingress:
    enabled: true
    className: "envoy"
    annotations:
      gateway.envoyproxy.io/tls-terminate: "true"
      gateway.envoyproxy.io/timeout: "300s"
      gateway.envoyproxy.io/request-body-max-size: "50m"
      gateway.envoyproxy.io/rate-limit-local: "60"
      gateway.envoyproxy.io/rate-limit-burst: "20"
    hosts:
      - host: ai.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: ai-tls
        hosts:
          - ai.example.com
```

### 11.3 Automated TLS with cert-manager

Add the cert-manager annotation to your ingress:

```yaml
openwebui:
  ingress:
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

This automatically provisions and renews TLS certificates from Let's Encrypt.

---

## 12. Authentication with Authelia (SSO / OIDC)

Authelia is an optional OIDC identity provider that replaces Open WebUI's built-in authentication with SSO and optional MFA. When enabled, Open WebUI is automatically configured as an OIDC client.

### 12.1 Enable Authelia

```yaml
authelia:
  enabled: true
  domain: "example.com"
  oidc:
    clientId: "openwebui"
    issuerUrl: "https://auth.example.com"
```

The chart auto-generates secrets for JWT, session, storage encryption, and the OIDC client secret. Open WebUI's `OAUTH_*` environment variables are injected automatically.

### 12.2 Create users

Authelia uses a file-based authentication backend by default. Generate a password hash and mount a custom `users_database.yml`:

```bash
# Generate an Argon2 password hash
docker run --rm ghcr.io/authelia/authelia:4.39.20 \
  authelia crypto hash generate argon2 --password 'your-password'
```

Create a `users_database.yml`:

```yaml
users:
  admin:
    displayname: "Admin User"
    email: admin@example.com
    password: "$argon2id$v=19$m=65536,t=3,p=4$..."  # paste hash here
    groups:
      - admins
```

Mount it by overriding the ConfigMap or using a Helm post-renderer.

### 12.3 Enable MFA (two-factor)

```yaml
authelia:
  enabled: true
  defaultPolicy: "two_factor"
```

Users will be prompted to register a TOTP device on their first login.

### 12.4 Use PostgreSQL as storage backend

For production, switch from SQLite to PostgreSQL:

```yaml
authelia:
  enabled: true
  storage: "postgres"
postgres:
  enabled: true
```

Authelia creates its tables in a dedicated `authelia` schema within the shared PostgreSQL database.

### 12.5 Expose Authelia via ingress

Authelia must be reachable by user browsers for OIDC redirects:

```yaml
authelia:
  ingress:
    enabled: true
    className: "envoy"
    hosts:
      - host: auth.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: auth-tls
        hosts:
          - auth.example.com
```

### 12.6 Verify OIDC integration

After deploying, verify the OIDC discovery endpoint and login flow:

```bash
# Check Authelia health
kubectl exec -n ai-stack deploy/ai-stack-authelia -- wget -qO- http://localhost:9091/api/health

# Verify OIDC discovery
kubectl port-forward -n ai-stack svc/ai-stack-authelia 9091:9091
curl -s http://localhost:9091/.well-known/openid-configuration | jq .issuer
```

Open WebUI should redirect to Authelia's login page when accessed.

---

## 13. Networking and Security

### 13.1 Network Policies

The chart deploys **default-deny** NetworkPolicies with per-component allowlists. This means:

- All inbound traffic is denied unless explicitly allowed
- All outbound traffic is denied unless explicitly allowed
- Each component only communicates with the services it needs

To verify:

```bash
kubectl get networkpolicies -n ai-stack
kubectl describe networkpolicy ai-stack-openwebui -n ai-stack
```

To disable (not recommended for production):

```yaml
global:
  networkPolicy:
    enabled: false
```

### 13.2 Pod Security

All pods run with PSA restricted baseline:

- `runAsNonRoot: true` (except Ollama — GPU exception)
- `readOnlyRootFilesystem: true` (where supported)
- `allowPrivilegeEscalation: false`
- `capabilities: drop: [ALL]`
- `seccompProfile: RuntimeDefault`

Enforce at the namespace level:

```bash
kubectl label namespace ai-stack \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### 13.3 Secret Management

Secrets are auto-generated on first install with 64-byte random keys and annotated with `helm.sh/resource-policy: keep` to survive upgrades.

**View generated secrets:**

```bash
kubectl get secrets -n ai-stack -l app.kubernetes.io/part-of=ai-stack

# Decode a specific secret value
kubectl get secret -n ai-stack ai-stack-qdrant-secret \
  -o jsonpath='{.data.api-key}' | base64 -d
```

**Use external secrets (production):**

Override auto-generated secrets with your own values:

```yaml
qdrant:
  apiKey: "my-externally-managed-key"
```

Or reference pre-existing Kubernetes Secrets (e.g., from External Secrets Operator or Vault CSI):

```yaml
externalAPIs:
  providers:
    - name: openai
      existingSecret:
        name: "vault-openai-secret"
        key: "api-key"
```

### 13.4 Rotate Secrets

1. Generate new secret values
2. Update the Kubernetes Secret directly:

```bash
kubectl create secret generic ai-stack-qdrant-secret \
  -n ai-stack \
  --from-literal=api-key="$(openssl rand -base64 48)" \
  --dry-run=client -o yaml | kubectl apply -f -
```

3. Restart affected pods to pick up the new secret:

```bash
kubectl rollout restart -n ai-stack deploy/ai-stack-qdrant
kubectl rollout restart -n ai-stack deploy/ai-stack-openwebui
```

---

## 14. Observability

### 14.1 Enable OpenTelemetry

```yaml
global:
  otel:
    enabled: true
    endpoint: "http://otel-collector.observability.svc.cluster.local:4317"
```

This deploys an OTel Collector and injects `OTEL_*` environment variables into all component pods. The collector pipeline includes:

- OTLP gRPC and HTTP receivers
- Batch processing and memory limiting
- Kubernetes metadata enrichment
- GenAI semantic convention processing
- PII redaction (GDPR compliance)

### 14.2 Enable Prometheus ServiceMonitors

**Prerequisite:** Prometheus Operator CRDs must be installed.

```yaml
global:
  serviceMonitor:
    enabled: true
    labels:
      release: prometheus  # Match your Prometheus operator selector
```

### 14.3 PII Redaction

The OTel Collector ships a `redaction` processor that masks two classes of
sensitive data **by default** (`otelCollector.redaction.enabled: true`), before
any telemetry leaves the cluster:

**PII** — email addresses, Austrian social-security numbers (VSNR), and
credit-card numbers.

**Credential shapes** (these ride along in MCPO / Open Terminal tool traffic) —
`Authorization: Bearer` tokens, JWTs, PEM private-key blocks, and
OpenAI / AWS / GitHub / GitLab / Google / Slack / Stripe API-key patterns.

The full RE2 pattern list is in `values.yaml` under
`otelCollector.redaction.blockedPatterns`. The processor runs ahead of every
exporter, so even the lab-only `debug` exporter receives redacted data. To add
your own pattern, **append** to the list — keep the shipped defaults:

```yaml
otelCollector:
  redaction:
    enabled: true
    blockedPatterns:
      # ... keep the shipped PII + credential defaults from values.yaml ...
      # Custom: phone numbers
      - '\+?\d{1,3}[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}'
```

---

## 15. Scaling

> **Open WebUI is replica-safe by default.** Running more than one Open WebUI
> pod requires its session and config state to live in shared backends, which
> the chart wires automatically: a stable `WEBUI_SECRET_KEY` (so every replica
> signs tokens identically), `DATABASE_URL` → the shared PostgreSQL, and the
> Valkey-backed websocket manager. These are active because `postgres.enabled`
> and `valkey.enabled` default to `true`. If you set `postgres.enabled=false`
> (ephemeral single-pod lab), Open WebUI falls back to a local SQLite file and
> **must not** be scaled beyond one replica — extra pods would each get their own
> database and users would hit login loops. See
> [docs/components/openwebui.md §High availability](docs/components/openwebui.md#high-availability).

### 15.1 Horizontal Pod Autoscaling

HPA is available for stateless components. Enable in your values:

```yaml
openwebui:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

tika:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 4
```

Verify HPA status:

```bash
kubectl get hpa -n ai-stack
```

### 15.2 Manual Scaling

For components without HPA:

```bash
# Scale Tika for heavy document processing
kubectl scale -n ai-stack deploy/ai-stack-tika --replicas=3

# Scale ingestion workers for bulk ingestion
kubectl scale -n ai-stack deploy/ai-stack-ingestion-worker --replicas=4
```

**Note:** Stateful components (Ollama, Qdrant) use ReadWriteOnce PVCs and cannot be scaled beyond 1 replica without operator support (e.g., Qdrant distributed mode) or shared storage.

### 15.3 Resource Tuning

Adjust resource requests and limits per component. Example for a high-traffic production deployment:

```yaml
openwebui:
  resources:
    requests:
      cpu: "1"
      memory: 2Gi
    limits:
      cpu: "4"
      memory: 8Gi

ollama:
  resources:
    requests:
      cpu: "4"
      memory: 16Gi
    limits:
      cpu: "16"
      memory: 64Gi
```

**Tip:** Set requests to match actual steady-state usage and limits to handle peak load. Monitor with Prometheus/Grafana to right-size over time.

---

## 16. Upgrading

### 16.1 Upgrade the Chart

```bash
# Review what will change
helm diff upgrade ai-stack . -n ai-stack  # requires helm-diff plugin

# Apply the upgrade
helm upgrade ai-stack . -n ai-stack

# With production overlay
helm upgrade ai-stack . -n ai-stack -f values.yaml -f values-prod.yaml
```

Secrets annotated with `helm.sh/resource-policy: keep` survive upgrades. PVCs are also retained.

### 16.2 Upgrade Individual Component Images

To update a single component without changing the chart:

```bash
helm upgrade ai-stack . -n ai-stack \
  --set ollama.image.tag="0.24.0"
```

Or update the tag in your values file and run `helm upgrade`.

### 16.3 Upgrade with Zero Downtime

For stateless components with multiple replicas, rolling updates happen automatically. Ensure:

1. `replicaCount >= 2` or HPA is enabled with `minReplicas >= 2`
2. Pod Disruption Budgets are configured (automatic for Ollama and Qdrant)
3. Readiness probes are passing before old pods are terminated

```bash
# Watch the rollout
kubectl rollout status -n ai-stack deploy/ai-stack-openwebui
```

---

## 17. GitOps with ArgoCD

Manage ai-stack declaratively with ArgoCD. The repo ships a dedicated `AppProject` and two ready-to-use Application manifests under `argocd/`.

**Prerequisites:**

- ArgoCD installed in the cluster (namespace `argocd`)
- Repository credentials configured in ArgoCD (Settings > Repositories) so ArgoCD can pull from `https://github.com/rmednitzer/ai-stack.git`

**Apply the AppProject first** — both Applications reference the dedicated, least-privilege `ai-stack` project (scoped to this repository and the `ai-stack` namespace; cluster-scoped resources other than `Namespace` are denied):

```bash
kubectl apply -f argocd/appproject.yaml
```

The chart's workloads carry `argocd.argoproj.io/sync-wave` annotations, so a first sync rolls out in dependency order (Secrets/ServiceAccounts → datastores/backing services → app workloads → HPA/PDB), reducing first-sync crash-loops.

### 17.1 Deploy the Lab Application

The lab application enables **automated sync** with self-healing and pruning — changes pushed to `main` are applied automatically.

```bash
kubectl apply -f argocd/application-lab.yaml
```

Key settings in `argocd/application-lab.yaml`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `syncPolicy.automated.selfHeal` | `true` | Reverts manual drift automatically |
| `syncPolicy.automated.prune` | `true` | Deletes resources removed from the chart |
| `valueFiles` | `values.yaml` | Uses default (lab) values only |
| `CreateNamespace` | `true` | ArgoCD creates the `ai-stack` namespace |

Verify the application synced successfully:

```bash
# ArgoCD CLI
argocd app get ai-stack-lab

# Or via kubectl
kubectl get application ai-stack-lab -n argocd -o jsonpath='{.status.sync.status}'
```

### 17.2 Deploy the Production Application

The production application uses **manual sync** for change-control compliance. ArgoCD detects when the repo is out-of-sync, but an operator must explicitly trigger the sync.

```bash
kubectl apply -f argocd/application-prod.yaml
```

Key settings in `argocd/application-prod.yaml`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `syncPolicy.automated` | *(omitted)* | Manual sync required |
| `valueFiles` | `values.yaml`, `values-prod.yaml` | Layers production overrides |
| `CreateNamespace` | `false` | Namespace managed externally |
| `ApplyOutOfSyncOnly` | `true` | Only syncs changed resources |

**Sync workflow:**

```bash
# 1. Check what changed
argocd app diff ai-stack-prod

# 2. Sync after review
argocd app sync ai-stack-prod

# 3. Monitor rollout
argocd app wait ai-stack-prod --health
```

The production manifest also configures **Slack notifications** via `argocd-notifications` for sync success, failure, and health degradation events. Update the annotation values to match your Slack channel:

```yaml
notifications.argoproj.io/subscribe.on-sync-succeeded.slack: ai-stack-alerts
notifications.argoproj.io/subscribe.on-sync-failed.slack: ai-stack-alerts
notifications.argoproj.io/subscribe.on-health-degraded.slack: ai-stack-alerts
```

### 17.3 Customizing the Application Manifests

**Change the target branch or repo:**

```yaml
spec:
  source:
    repoURL: https://github.com/your-org/ai-stack.git
    targetRevision: release/v2   # Branch, tag, or commit SHA
```

**Add per-cluster overrides** without forking the chart:

```yaml
spec:
  source:
    helm:
      valueFiles:
        - values.yaml
        - values-prod.yaml
      parameters:
        - name: openwebui.ingress.hosts[0].host
          value: ai.my-cluster.example.com
        - name: ollama.gpu.enabled
          value: "true"
```

**Use a dedicated AppProject** (recommended for production):

```yaml
spec:
  project: ai-stack  # Instead of "default"
```

Create the AppProject to restrict allowed namespaces, cluster resources, and source repos:

```bash
argocd proj create ai-stack \
  --src https://github.com/rmednitzer/ai-stack.git \
  --dest https://kubernetes.default.svc,ai-stack \
  --allow-cluster-resource /Namespace
```

### 17.4 Ignore Differences

Both manifests ignore diffs on:

- **Deployment replicas** — prevents HPA-managed replica counts from showing as drift
- **Secret data** — prevents Helm-generated secrets from triggering constant out-of-sync status

Add additional ignore rules as needed:

```yaml
ignoreDifferences:
  - group: ""
    kind: ConfigMap
    jsonPointers:
      - /data/custom-key
```

### 17.5 Disaster Recovery

Both applications set `revisionHistoryLimit` (5 for lab, 10 for production) so you can roll back to a previous sync:

```bash
# List sync history
argocd app history ai-stack-prod

# Roll back to a specific revision
argocd app rollback ai-stack-prod <HISTORY_ID>
```

The `resources-finalizer.argocd.argoproj.io` finalizer ensures all managed resources are cleaned up if the Application is deleted. Secrets and PVCs annotated with `helm.sh/resource-policy: keep` are still retained.

---

## 18. EU Compliance

This section covers EU regulatory compliance tasks. For the full compliance
framework analysis, see [EU_COMPLIANCE_CHECK.md](docs/compliance/EU_COMPLIANCE_CHECK.md). For
detailed templates and procedures, see [docs/compliance/](docs/compliance/).

### 18.1 AI Transparency Disclosure

AI Act Art. 50(1) requires informing users when they interact with an AI
system. The chart includes a configurable banner:

```yaml
# values.yaml or values-prod.yaml
openwebui:
  env:
    WEBUI_BANNER_TEXT: "You are interacting with an AI-powered assistant. Responses are generated by a large language model and may not always be accurate."
    WEBUI_BANNER_DISMISSIBLE: "true"
```

Customise the text for your deployment. Set `WEBUI_BANNER_TEXT: ""` to disable.

### 18.2 Data Retention

GDPR Art. 5(1)(e) requires storage limitation. Define and enforce retention
periods for all personal data categories. See
[EU_OPERATIONS_GUIDE §1 Data Retention Policy](docs/compliance/EU_OPERATIONS_GUIDE.md#1-data-retention-policy-gdpr-art-51e)
for recommended retention periods and automated purge scripts.

### 18.3 External API Provider Governance

When enabling external LLM providers (`externalAPIs.enabled=true`), complete
the pre-enablement checklist in
[EU_OPERATIONS_GUIDE §2 External API Provider Governance](docs/compliance/EU_OPERATIONS_GUIDE.md#2-external-api-provider-governance-gdpr-art-28-art-4449),
including:

- Data Processing Agreement (DPA) with each provider
- International transfer assessment (SCCs, adequacy decision)
- ROPA update (PA-06 in [docs/compliance/ROPA_TEMPLATE.md](docs/compliance/ROPA_TEMPLATE.md))
- Privacy notice update

### 18.4 Encryption at Rest

NIS2 Art. 21(2)(h) requires cryptography policies. Ensure PVCs containing
personal data use an encrypted StorageClass. See
[EU_OPERATIONS_GUIDE §3 Encryption at Rest](docs/compliance/EU_OPERATIONS_GUIDE.md#3-encryption-at-rest-nis2-art-212h).

```yaml
# Use an encrypted storage class
global:
  storageClass: "gp3-encrypted"  # or "zfs-encrypted", etc.
```

### 18.5 Compliance Documentation

Complete the following before production deployment:

| Document | Location | Status |
|----------|----------|--------|
| Data Protection Impact Assessment | [docs/compliance/DPIA_TEMPLATE.md](docs/compliance/DPIA_TEMPLATE.md) | Template — complete before deployment |
| Records of Processing Activities | [docs/compliance/ROPA_TEMPLATE.md](docs/compliance/ROPA_TEMPLATE.md) | Template — complete before deployment |
| Incident Response Playbook | [docs/compliance/INCIDENT_RESPONSE.md](docs/compliance/INCIDENT_RESPONSE.md) | Template — fill contact directory |
| Data Subject Rights Procedures | [docs/compliance/DSAR_PROCEDURES.md](docs/compliance/DSAR_PROCEDURES.md) | Template — establish intake channels |
| EU Operations Guide | [docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) | Reference — review all sections |
| Security Policy / CVD | [SECURITY.md](SECURITY.md) | Template — set security contact email |
| EU Compliance Check | [EU_COMPLIANCE_CHECK.md](docs/compliance/EU_COMPLIANCE_CHECK.md) | Complete — review and track gaps |

---

## 19. Troubleshooting

### Quick Reference — Symptom → Diagnosis

Start with the first-line command below, then jump to the linked subsection for the full treatment.

| Symptom | Most likely cause | First-line command | See |
|---------|------------------|--------------------|-----|
| Pod stuck in `Pending` | Insufficient resources, GPU unavailable, unschedulable | `kubectl describe pod -n ai-stack <pod>` | [§19.1](#191-pods-stuck-in-pending) |
| Ollama pod OOMKilled | Model larger than memory limit | `kubectl describe pod -n ai-stack -l app.kubernetes.io/component=ollama \| grep -A2 OOM` | [§19.2](#192-ollama-out-of-memory) |
| Open WebUI returns "model not found" / connection refused | Ollama pod not ready or DNS / NetworkPolicy blocking | `kubectl exec -n ai-stack deploy/ai-stack-openwebui -- wget -qO- http://ai-stack-ollama:11434/` | [§19.3](#193-open-webui-cannot-reach-ollama) |
| Cross-component traffic fails with services present | NetworkPolicy default-deny allowlist too strict | `kubectl get networkpolicies -n ai-stack -o wide` | [§19.4](#194-networkpolicy-blocking-traffic) |
| PVC stuck in `Pending` | Missing StorageClass, no capacity, access-mode mismatch | `kubectl describe pvc -n ai-stack <pvc>` | [§19.5](#195-pvc-stuck-in-pending) |
| Secret missing after upgrade | Secrets are only generated on install | `kubectl get secrets -n ai-stack -l app.kubernetes.io/part-of=ai-stack` | [§19.6](#196-secrets-not-generated) |
| `helm test` failing | Enabled service unreachable over TCP/HTTP | `helm test ai-stack -n ai-stack --logs` | [§19.7](#197-helm-test-failures) |
| Ollama running on CPU despite GPU enabled | NVIDIA device plugin missing or resource not advertised | `kubectl describe node <node> \| grep nvidia` | [§19.8](#198-gpu-not-detected) |

### 19.1 Pods Stuck in Pending

```bash
kubectl describe pod -n ai-stack <pod-name>
```

Common causes:

- **Insufficient resources:** Increase node capacity or reduce resource requests
- **No matching node selector/tolerations:** Check `global.nodeSelector` and `global.tolerations`
- **GPU requested but unavailable:** Ensure the NVIDIA GPU Operator is installed and GPUs are free

### 19.2 Ollama Out of Memory

Ollama may OOM when loading large models. Solutions:

1. **Increase memory limits:**

```yaml
ollama:
  resources:
    limits:
      memory: 64Gi  # Match model requirements
```

2. **Use smaller quantized models:** `llama3.2:3b` instead of `llama3.2:70b`

3. **Reduce keep-alive time** to unload idle models faster:

```yaml
ollama:
  env:
    OLLAMA_KEEP_ALIVE: "1m"
```

### 19.3 Open WebUI Cannot Reach Ollama

1. Check Ollama is running: `kubectl get pods -n ai-stack -l app.kubernetes.io/component=ollama`
2. Check the service exists: `kubectl get svc -n ai-stack -l app.kubernetes.io/component=ollama`
3. Test DNS resolution from Open WebUI pod:

```bash
kubectl exec -n ai-stack deploy/ai-stack-openwebui -- \
  wget -qO- http://ai-stack-ollama:11434/
```

4. Check NetworkPolicy allows the connection:

```bash
kubectl describe networkpolicy -n ai-stack | grep -A 5 ollama
```

### 19.4 NetworkPolicy Blocking Traffic

Symptom: Components cannot communicate even though services exist.

1. Verify policies are correct:

```bash
kubectl get networkpolicies -n ai-stack -o wide
```

2. Temporarily disable to confirm it's a policy issue (lab only):

```bash
helm upgrade ai-stack . -n ai-stack --set global.networkPolicy.enabled=false
```

3. If traffic works with policies disabled, check the specific component's policy rules in `templates/common/networkpolicies.yaml`.

### 19.5 PVC Stuck in Pending

```bash
kubectl describe pvc -n ai-stack <pvc-name>
```

Common causes:

- **No StorageClass:** Set `global.storageClass` to a valid class
- **Insufficient storage capacity:** Check available storage in the cluster
- **Access mode mismatch:** Ensure the StorageClass supports `ReadWriteOnce`

### 19.6 Secrets Not Generated

Secrets are only generated on `helm install`, not on `helm upgrade`. If secrets are missing:

```bash
# Check if secrets exist
kubectl get secrets -n ai-stack -l app.kubernetes.io/part-of=ai-stack

# If missing, they may have been accidentally deleted.
# Uninstall and reinstall (data in PVCs is preserved):
helm uninstall ai-stack -n ai-stack
helm install ai-stack . -n ai-stack
```

**Important:** PVCs with `helm.sh/resource-policy: keep` are not deleted on uninstall.

### 19.7 Helm Test Failures

```bash
# Run tests with verbose output
helm test ai-stack -n ai-stack --logs

# Check the test pod logs
kubectl logs -n ai-stack ai-stack-connection-test
```

Tests verify TCP and HTTP connectivity to all enabled services.

### 19.8 GPU Not Detected

```bash
# Check NVIDIA device plugin is running
kubectl get pods -n gpu-operator

# Check node GPU resources
kubectl describe node <node-name> | grep nvidia

# Check Ollama logs for GPU detection
kubectl logs -n ai-stack deploy/ai-stack-ollama | grep -i gpu
```

Ensure:

- NVIDIA GPU Operator is installed and healthy
- Node has `nvidia.com/gpu` resources advertised
- The pod's `resources.limits` includes `nvidia.com/gpu: 1`

---

## 20. Uninstall

```bash
# Remove the Helm release (PVCs are retained)
helm uninstall ai-stack -n ai-stack

# To also delete PVCs and all data (irreversible):
kubectl delete pvc -n ai-stack -l app.kubernetes.io/part-of=ai-stack

# Delete the namespace
kubectl delete namespace ai-stack
```

**Warning:** Deleting PVCs destroys all stored models, documents, vector embeddings, and configuration. Back up first if needed.
