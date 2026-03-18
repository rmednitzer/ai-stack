# ai-stack How-To Guide

Practical, task-oriented guide for deploying, operating, and maintaining the ai-stack Helm chart. For architecture overview and configuration reference, see [README.md](README.md).

---

## Table of Contents

1. [Installation](#1-installation)
   - [Lab environment](#11-lab-environment)
   - [Production environment](#12-production-environment)
   - [Air-gapped / offline install](#13-air-gapped--offline-install)
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
5. [External LLM Providers](#5-external-llm-providers)
   - [Add OpenAI](#51-add-openai)
   - [Add Azure OpenAI](#52-add-azure-openai)
   - [Add Anthropic (Claude)](#53-add-anthropic-claude)
   - [Use an external secret manager](#54-use-an-external-secret-manager)
6. [MCP Tool Integration (MCPO)](#6-mcp-tool-integration-mcpo)
   - [Enable MCPO](#61-enable-mcpo)
   - [Configure MCP servers](#62-configure-mcp-servers)
7. [Ingress and TLS](#7-ingress-and-tls)
   - [Expose Open WebUI with NGINX](#71-expose-open-webui-with-nginx)
   - [Expose Open WebUI with Contour](#72-expose-open-webui-with-contour)
   - [Automated TLS with cert-manager](#73-automated-tls-with-cert-manager)
8. [Authentication with Authelia (SSO / OIDC)](#8-authentication-with-authelia-sso--oidc)
   - [Enable Authelia](#81-enable-authelia)
   - [Create users](#82-create-users)
   - [Enable MFA (two-factor)](#83-enable-mfa-two-factor)
   - [Expose Authelia via ingress](#84-expose-authelia-via-ingress)
   - [Verify OIDC integration](#85-verify-oidc-integration)
9. [Networking and Security](#9-networking-and-security)
   - [Network policies](#91-network-policies)
   - [Pod security](#92-pod-security)
   - [Secret management](#93-secret-management)
   - [Rotate secrets](#94-rotate-secrets)
10. [Observability](#10-observability)
    - [Enable OpenTelemetry](#101-enable-opentelemetry)
    - [Enable Prometheus ServiceMonitors](#102-enable-prometheus-servicemonitors)
    - [PII redaction](#103-pii-redaction)
11. [Backup and Restore](#11-backup-and-restore)
    - [Enable Veeam K10 backups](#111-enable-veeam-k10-backups)
    - [Manage backup policies](#112-manage-backup-policies)
    - [Restore from backup](#113-restore-from-backup)
12. [Scaling](#12-scaling)
    - [Horizontal Pod Autoscaling](#121-horizontal-pod-autoscaling)
    - [Manual scaling](#122-manual-scaling)
    - [Resource tuning](#123-resource-tuning)
13. [Upgrading](#13-upgrading)
    - [Upgrade the chart](#131-upgrade-the-chart)
    - [Upgrade individual component images](#132-upgrade-individual-component-images)
    - [Upgrade with zero downtime](#133-upgrade-with-zero-downtime)
14. [GitOps with ArgoCD](#14-gitops-with-argocd)
    - [Deploy the lab application](#141-deploy-the-lab-application)
    - [Deploy the production application](#142-deploy-the-production-application)
    - [Customizing the application manifests](#143-customizing-the-application-manifests)
    - [Ignore differences](#144-ignore-differences)
    - [Disaster recovery](#145-disaster-recovery)
15. [EU Compliance](#15-eu-compliance)
    - [AI transparency disclosure](#151-ai-transparency-disclosure)
    - [Data retention](#152-data-retention)
    - [External API provider governance](#153-external-api-provider-governance)
    - [Encryption at rest](#154-encryption-at-rest)
    - [Compliance documentation](#155-compliance-documentation)
16. [Troubleshooting](#16-troubleshooting)
    - [Pods stuck in Pending](#161-pods-stuck-in-pending)
    - [Ollama out of memory](#162-ollama-out-of-memory)
    - [Open WebUI cannot reach Ollama](#163-open-webui-cannot-reach-ollama)
    - [NetworkPolicy blocking traffic](#164-networkpolicy-blocking-traffic)
    - [PVC stuck in Pending](#165-pvc-stuck-in-pending)
    - [Secrets not generated](#166-secrets-not-generated)
    - [Helm test failures](#167-helm-test-failures)
17. [Uninstall](#17-uninstall)

---

## 1. Installation

### 1.1 Lab Environment

Lab mode deploys a single-replica stack with relaxed resource limits, suitable for development and evaluation.

**Prerequisites:**

- Kubernetes 1.30+ (VMware Tanzu v1.30.10 recommended)
- Helm 3.12+
- At least 8 GB RAM available in the cluster
- A default StorageClass (or use `emptyDir` for ephemeral testing)

**Install:**

```bash
# Create the namespace and install with lab defaults
helm install ai-stack . -n ai-stack --create-namespace
```

### 1.2 Production Environment

Production mode enables HA replicas, autoscaling, TLS ingress, backups, and observability.

**Additional prerequisites:**

- VMware Tanzu v1.30.10 (or compatible Kubernetes 1.30+ distribution)
- Prometheus Operator CRDs (for ServiceMonitor resources)
- cert-manager (for automated TLS provisioning)
- An ingress controller (Contour or NGINX)

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
docker pull ghcr.io/open-webui/open-webui:v0.8.10
docker tag ghcr.io/open-webui/open-webui:v0.8.10 registry.internal/open-webui:v0.8.10
docker push registry.internal/open-webui:v0.8.10
# Repeat for all images...
```

2. **Override image repositories** in your values file:

```yaml
openwebui:
  image:
    repository: registry.internal/open-webui
    tag: "v0.8.10"
ollama:
  image:
    repository: registry.internal/ollama
    tag: "0.18.1"
# ... repeat for all components
```

3. **Configure image pull secrets** if your registry requires authentication:

```yaml
global:
  imagePullSecrets:
    - name: my-registry-secret
```

4. **Pre-download Ollama models** and load them into the PVC, since `ollama pull` requires internet access. See [Section 3](#3-working-with-models).

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

For larger models (requires more RAM):

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

RAG allows the AI to answer questions using your own documents. The stack includes all components needed: Tika (document parsing), Qdrant (vector storage), and Ollama (embeddings).

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

## 5. External LLM Providers

Add cloud-hosted models alongside local Ollama inference. Users see all models in the Open WebUI model picker.

### 5.1 Add OpenAI

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: openai
      baseUrl: "https://api.openai.com/v1"
      apiKey: "sk-..."
```

### 5.2 Add Azure OpenAI

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: azure-openai
      baseUrl: "https://<resource>.openai.azure.com/openai/deployments/<deployment>"
      apiKey: "<your-azure-key>"
```

### 5.3 Add Anthropic (Claude)

```yaml
externalAPIs:
  enabled: true
  providers:
    - name: anthropic
      baseUrl: "https://api.anthropic.com/v1"
      apiKey: "sk-ant-..."
```

**Note:** Anthropic API integration requires Open WebUI v0.6+ with the Anthropic API translation layer, or a Pipelines function for protocol translation.

### 5.4 Use an External Secret Manager

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

## 6. MCP Tool Integration (MCPO)

MCPO bridges Model Context Protocol (MCP) servers to OpenAPI endpoints that Open WebUI can consume as tools.

### 6.1 Enable MCPO

```yaml
mcpo:
  enabled: true
```

### 6.2 Configure MCP Servers

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

## 7. Ingress and TLS

### 7.1 Expose Open WebUI with NGINX

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

### 7.2 Expose Open WebUI with Contour

```yaml
openwebui:
  ingress:
    enabled: true
    className: "contour"
    annotations:
      projectcontour.io/websocket-routes: "/"
      projectcontour.io/response-timeout: "300s"
      projectcontour.io/max-request-body-size: "50m"
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
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

### 7.3 Automated TLS with cert-manager

Add the cert-manager annotation to your ingress:

```yaml
openwebui:
  ingress:
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

This automatically provisions and renews TLS certificates from Let's Encrypt.

---

## 8. Authentication with Authelia (SSO / OIDC)

Authelia is an optional OIDC identity provider that replaces Open WebUI's built-in authentication with SSO and optional MFA. When enabled, Open WebUI is automatically configured as an OIDC client.

### 8.1 Enable Authelia

```yaml
authelia:
  enabled: true
  domain: "example.com"
  oidc:
    clientId: "openwebui"
    issuerUrl: "https://auth.example.com"
```

The chart auto-generates secrets for JWT, session, storage encryption, and the OIDC client secret. Open WebUI's `OAUTH_*` environment variables are injected automatically.

### 8.2 Create users

Authelia uses a file-based authentication backend by default. Generate a password hash and mount a custom `users_database.yml`:

```bash
# Generate an Argon2 password hash
docker run --rm ghcr.io/authelia/authelia:4.39 \
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

### 8.3 Enable MFA (two-factor)

```yaml
authelia:
  enabled: true
  defaultPolicy: "two_factor"
```

Users will be prompted to register a TOTP device on their first login.

### 8.4 Expose Authelia via ingress

Authelia must be reachable by user browsers for OIDC redirects:

```yaml
authelia:
  ingress:
    enabled: true
    className: "nginx"
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

### 8.5 Verify OIDC integration

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

## 9. Networking and Security

### 9.1 Network Policies

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

### 9.2 Pod Security

All pods run with PSA restricted baseline:

- `runAsNonRoot: true`
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

### 9.3 Secret Management

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

### 9.4 Rotate Secrets

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

## 10. Observability

### 10.1 Enable OpenTelemetry

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

### 10.2 Enable Prometheus ServiceMonitors

**Prerequisite:** Prometheus Operator CRDs must be installed.

```yaml
global:
  serviceMonitor:
    enabled: true
    labels:
      release: prometheus  # Match your Prometheus operator selector
```

### 10.3 PII Redaction

The OTel Collector automatically redacts:

- Email addresses
- Social security numbers (Austrian VSNR format)
- Credit card numbers

To add custom redaction patterns:

```yaml
otelCollector:
  redaction:
    enabled: true
    blockedPatterns:
      # Default patterns
      - '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
      - '\b\d{4}\s?\d{6}\b'
      - '\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
      # Custom: phone numbers
      - '\+?\d{1,3}[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}'
```

---

## 11. Backup and Restore

The chart integrates with [Veeam K10](https://www.veeam.com/kubernetes-backup.html) for application-aware backup and restore of all stateful components.

### 11.1 Enable Veeam K10 Backups

When `global.backup.enabled=true`, the chart creates a K10 Policy custom resource that defines the backup schedule and retention for all ai-stack PVCs and application data:

```yaml
global:
  backup:
    enabled: true
    schedule: "0 2 * * *"    # Daily at 02:00 UTC
    retention:
      daily: 7
      weekly: 4
      monthly: 12
```

**Prerequisites:**

- Veeam K10 installed in the cluster (namespace `kasten-io`)
- A K10 Location Profile configured for your backup target (S3, NFS, etc.)

### 11.2 Manage Backup Policies

Backup policies can be managed via the K10 dashboard or directly as Policy CRDs:

```bash
# View the auto-created policy
kubectl get policies.config.kio.kasten.io -n kasten-io

# Access the K10 dashboard
kubectl port-forward -n kasten-io svc/gateway 8080:8000
# Open http://localhost:8080/k10/
```

From the K10 dashboard you can:

- Monitor backup status and history
- Trigger on-demand backups
- Adjust retention policies
- Configure export to external storage

### 11.3 Restore from Backup

Use the K10 dashboard or CLI to restore from a backup restore point:

```bash
# List available restore points
kubectl get restorepoints.apps.kio.kasten.io -n kasten-io

# Trigger a restore via the K10 dashboard (recommended)
# Or create a RestoreAction CRD for automated recovery
```

For full cluster disaster recovery, K10 supports cross-cluster restore when combined with an exported Location Profile.

---

## 12. Scaling

### 12.1 Horizontal Pod Autoscaling

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

pipelines:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 4
```

Verify HPA status:

```bash
kubectl get hpa -n ai-stack
```

### 12.2 Manual Scaling

For components without HPA:

```bash
# Scale Tika for heavy document processing
kubectl scale -n ai-stack deploy/ai-stack-tika --replicas=3
```

**Note:** Stateful components (Ollama, Qdrant) use ReadWriteOnce PVCs and cannot be scaled beyond 1 replica without operator support (e.g., Qdrant distributed mode) or shared storage.

### 12.3 Resource Tuning

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

## 13. Upgrading

### 13.1 Upgrade the Chart

```bash
# Review what will change
helm diff upgrade ai-stack . -n ai-stack  # requires helm-diff plugin

# Apply the upgrade
helm upgrade ai-stack . -n ai-stack

# With production overlay
helm upgrade ai-stack . -n ai-stack -f values.yaml -f values-prod.yaml
```

Secrets annotated with `helm.sh/resource-policy: keep` survive upgrades. PVCs are also retained.

### 13.2 Upgrade Individual Component Images

To update a single component without changing the chart:

```bash
helm upgrade ai-stack . -n ai-stack \
  --set ollama.image.tag="0.18.0"
```

Or update the tag in your values file and run `helm upgrade`.

### 13.3 Upgrade with Zero Downtime

For stateless components with multiple replicas, rolling updates happen automatically. Ensure:

1. `replicaCount >= 2` or HPA is enabled with `minReplicas >= 2`
2. Pod Disruption Budgets are configured (automatic for Ollama and Qdrant)
3. Readiness probes are passing before old pods are terminated

```bash
# Watch the rollout
kubectl rollout status -n ai-stack deploy/ai-stack-openwebui
```

---

## 14. GitOps with ArgoCD

Manage ai-stack declaratively with ArgoCD. The repo ships two ready-to-use Application manifests under `argocd/`.

**Prerequisites:**

- ArgoCD v3.3.2+ installed in the cluster (namespace `argocd`)
- Repository credentials configured in ArgoCD (Settings > Repositories) so ArgoCD can pull from `https://github.com/rmednitzer/ai-stack.git`

### 14.1 Deploy the Lab Application

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

### 14.2 Deploy the Production Application

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

### 14.3 Customizing the Application Manifests

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

### 14.4 Ignore Differences

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

### 14.5 Disaster Recovery

Both applications set `revisionHistoryLimit` (5 for lab, 10 for production) so you can roll back to a previous sync:

```bash
# List sync history
argocd app history ai-stack-prod

# Roll back to a specific revision
argocd app rollback ai-stack-prod <HISTORY_ID>
```

The `resources-finalizer.argocd.argoproj.io` finalizer ensures all managed resources are cleaned up if the Application is deleted. Secrets and PVCs annotated with `helm.sh/resource-policy: keep` are still retained.

---

## 15. EU Compliance

This section covers EU regulatory compliance tasks. For the full compliance
framework analysis, see [EU_COMPLIANCE_CHECK.md](EU_COMPLIANCE_CHECK.md). For
detailed templates and procedures, see [docs/compliance/](docs/compliance/).

### 15.1 AI Transparency Disclosure

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

### 15.2 Data Retention

GDPR Art. 5(1)(e) requires storage limitation. Define and enforce retention
periods for all personal data categories. See
[docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) §1
for recommended retention periods and automated purge scripts.

### 15.3 External API Provider Governance

When enabling external LLM providers (`externalAPIs.enabled=true`), complete
the pre-enablement checklist in
[docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) §2,
including:

- Data Processing Agreement (DPA) with each provider
- International transfer assessment (SCCs, adequacy decision)
- ROPA update (PA-06 in [docs/compliance/ROPA_TEMPLATE.md](docs/compliance/ROPA_TEMPLATE.md))
- Privacy notice update

### 15.4 Encryption at Rest

NIS2 Art. 21(2)(h) requires cryptography policies. Ensure PVCs containing
personal data use an encrypted StorageClass. See
[docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) §3.

```yaml
# Use an encrypted storage class
global:
  storageClass: "tanzu-default-storage"
```

### 15.5 Compliance Documentation

Complete the following before production deployment:

| Document | Location | Status |
|----------|----------|--------|
| Data Protection Impact Assessment | [docs/compliance/DPIA_TEMPLATE.md](docs/compliance/DPIA_TEMPLATE.md) | Template — complete before deployment |
| Records of Processing Activities | [docs/compliance/ROPA_TEMPLATE.md](docs/compliance/ROPA_TEMPLATE.md) | Template — complete before deployment |
| Incident Response Playbook | [docs/compliance/INCIDENT_RESPONSE.md](docs/compliance/INCIDENT_RESPONSE.md) | Template — fill contact directory |
| Data Subject Rights Procedures | [docs/compliance/DSAR_PROCEDURES.md](docs/compliance/DSAR_PROCEDURES.md) | Template — establish intake channels |
| EU Operations Guide | [docs/compliance/EU_OPERATIONS_GUIDE.md](docs/compliance/EU_OPERATIONS_GUIDE.md) | Reference — review all sections |
| Security Policy / CVD | [SECURITY.md](SECURITY.md) | Template — set security contact email |
| EU Compliance Check | [EU_COMPLIANCE_CHECK.md](EU_COMPLIANCE_CHECK.md) | Complete — review and track gaps |

---

## 16. Troubleshooting

### 16.1 Pods Stuck in Pending

```bash
kubectl describe pod -n ai-stack <pod-name>
```

Common causes:

- **Insufficient resources:** Increase node capacity or reduce resource requests
- **No matching node selector/tolerations:** Check `global.nodeSelector` and `global.tolerations`

### 16.2 Ollama Out of Memory

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

### 16.3 Open WebUI Cannot Reach Ollama

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

### 16.4 NetworkPolicy Blocking Traffic

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

### 16.5 PVC Stuck in Pending

```bash
kubectl describe pvc -n ai-stack <pvc-name>
```

Common causes:

- **No StorageClass:** Set `global.storageClass` to a valid class
- **Insufficient storage capacity:** Check available storage in the cluster
- **Access mode mismatch:** Ensure the StorageClass supports `ReadWriteOnce`

### 16.6 Secrets Not Generated

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

### 16.7 Helm Test Failures

```bash
# Run tests with verbose output
helm test ai-stack -n ai-stack --logs

# Check the test pod logs
kubectl logs -n ai-stack ai-stack-connection-test
```

Tests verify TCP and HTTP connectivity to all enabled services.

---

## 17. Uninstall

```bash
# Remove the Helm release (PVCs are retained)
helm uninstall ai-stack -n ai-stack

# To also delete PVCs and all data (irreversible):
kubectl delete pvc -n ai-stack -l app.kubernetes.io/part-of=ai-stack

# Delete the namespace
kubectl delete namespace ai-stack
```

**Warning:** Deleting PVCs destroys all stored models, documents, vector embeddings, and configuration. Back up first if needed.
