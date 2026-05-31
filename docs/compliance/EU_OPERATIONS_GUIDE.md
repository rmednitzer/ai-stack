# EU Compliance Operations Guide — ai-stack

Operational guidance for deployers operating the ai-stack in EU-regulated
environments. Covers data retention, external API governance, encryption,
content marking, security assessments, operator training, and cookie consent.

---

## 1. Data Retention Policy (GDPR Art. 5(1)(e))

GDPR requires that personal data is kept no longer than necessary. The ai-stack
does not enforce automated retention by default — deployers must implement
retention policies appropriate to their use case.

### 1.1 Recommended Retention Periods

| Data Category | Suggested Maximum | Component | Purge Method |
|---------------|-------------------|-----------|-------------|
| User conversations | 12 months (or per policy) | Open WebUI | Admin API or scheduled script |
| Vector embeddings | Matches source document retention | Qdrant | Collection point deletion with time filter |
| Uploaded documents | 12 months (or per policy) | Open WebUI | File management API |
| Cross-conversation memories | Until user deletes | Open WebUI | User self-service or admin purge |
| LangGraph checkpoints | 90 days (or per policy) | PostgreSQL | `DELETE WHERE created_at < NOW() - INTERVAL '90 days'` |
| Telemetry/logs | 30 days (logs), 90 days (metrics) | OTel pipeline | Configure exporter TTL |
| PVC snapshots | Per retention policy | External storage | Configure Velero retention |

### 1.2 Automated Purge Script

Create a CronJob or scheduled script to enforce retention:

```bash
#!/bin/bash
# Example: purge conversations older than 12 months
CUTOFF=$(date -u -d '12 months ago' +%Y-%m-%dT%H:%M:%SZ)

# Purge old Qdrant points (by timestamp metadata)
kubectl exec -n ai-stack deploy/ai-stack-qdrant -- \
  curl -s -X POST "http://localhost:6333/collections/documents/points/delete" \
    -H "Content-Type: application/json" \
    -d "{\"filter\": {\"must\": [{\"key\": \"created_at\", \"range\": {\"lt\": \"$CUTOFF\"}}]}}"

# Purge old LangGraph checkpoints (if enabled)
kubectl exec -n ai-stack deploy/ai-stack-postgres -- \
  psql -U langgraph -d langgraph -c \
    "DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL '12 months';"
```

### 1.3 Helm Configuration

The chart provides a configurable banner to remind users of data retention:

```yaml
openwebui:
  env:
    # Inform users about data retention (AI Act Art. 50 + GDPR transparency)
    WEBUI_BANNER_TEXT: "AI-powered assistant. Conversations are retained for [X months]. See our privacy notice at [URL]."
    WEBUI_BANNER_DISMISSIBLE: "true"
```

---

## 2. External API Provider Governance (GDPR Art. 28, Art. 44–49)

When `externalAPIs.enabled=true`, user prompts are sent to third-party cloud
providers. This creates processor relationships and potential international
data transfers.

### 2.1 Pre-Enablement Checklist

Before enabling any external API provider in production:

- [ ] **Data Processing Agreement (DPA)** — Obtain a signed DPA from the
      provider covering GDPR Art. 28 requirements
- [ ] **International transfer assessment** — If provider processes data
      outside the EU/EEA, ensure adequate safeguards:
  - EU adequacy decision (Art. 45)
  - Standard Contractual Clauses (Art. 46(2)(c))
  - Binding Corporate Rules (Art. 47)
- [ ] **Transfer Impact Assessment (TIA)** — Document the assessment of
      third-country data protection laws
- [ ] **Provider data retention policy** — Review and document how long
      the provider retains prompt data
- [ ] **Update ROPA** — Add the external API as a recipient in the Records
      of Processing Activities (PA-06)
- [ ] **Update DPIA** — Reassess risk with external data transfer
- [ ] **Inform data subjects** — Update privacy notice to disclose the
      external processor

### 2.2 Provider DPA Status

| Provider | DPA Available | Transfer Mechanism | Data Retention | Reviewed |
|----------|-------------|-------------------|----------------|----------|
| OpenAI | [openai.com/dpa] | SCCs | 30 days (API) | *[date]* |
| Anthropic | [anthropic.com/dpa] | SCCs | 30 days (API) | *[date]* |
| Azure OpenAI | [Microsoft DPA] | EU data residency option | Per config | *[date]* |
| Google Gemini | [Google Cloud DPA] | SCCs / EU processing | Per config | *[date]* |
| Mistral | EU-based | N/A (EU processor) | Per config | *[date]* |
| *[Custom]* | *[status]* | *[mechanism]* | *[period]* | *[date]* |

### 2.3 GPAI Model Documentation (AI Act Art. 53)

When integrating general-purpose AI models from external providers, deployers
must obtain and maintain:

1. **Technical documentation** from the GPAI provider (Art. 53(1)(b))
2. **Model capabilities and limitations** information
3. **Intended use** documentation
4. **Copyright compliance** policy (Art. 53(1)(c))

Request this documentation from each provider before deployment. Store it
alongside this guide for audit purposes.

---

## 3. Encryption at Rest (NIS2 Art. 21(2)(h))

NIS2 requires policies and procedures regarding cryptography and encryption.
The ai-stack enforces TLS in transit (prod profile) but encryption at rest
depends on the underlying storage infrastructure.

### 3.1 Requirements

| PVC | Contains Personal Data? | Encryption Required? |
|-----|------------------------|---------------------|
| `ai-stack-openwebui` | Yes (conversations, user data) | Yes |
| `ai-stack-qdrant` | Yes (vector embeddings from documents) | Yes |
| `ai-stack-ollama` | No (model weights only) | Recommended |
| `ai-stack-postgres` | Yes (if LangGraph enabled — agent state) | Yes |

| `ai-stack-backup` | Yes (contains copies of above) | Yes |

### 3.2 Implementation Options

| Method | Scope | Configuration |
|--------|-------|---------------|
| **StorageClass encryption** | All PVCs using the class | Set `global.storageClass` to an encrypted StorageClass (e.g., `gp3-encrypted` on AWS, `zfs-encrypted` on ZFS) |
| **LUKS dm-crypt** | Node-level | Encrypt the underlying block device |
| **KMS-backed encryption** | Cloud provider | AWS EBS encryption, GCP CMEK, Azure Disk Encryption |
| **ZFS native encryption** | Pool-level | `zfs create -o encryption=aes-256-gcm -o keylocation=... pool/dataset` |

### 3.3 Verification

```bash
# Verify StorageClass has encryption parameters
kubectl get storageclass <class-name> -o yaml | grep -i encrypt

# AWS: verify EBS volume encryption
aws ec2 describe-volumes --volume-ids <vol-id> --query 'Volumes[].Encrypted'

# ZFS: verify encryption
zfs get encryption <pool/dataset>
```

---

## 4. AI Content Marking (AI Act Art. 50(2))

AI Act Art. 50(2) requires that AI-generated content is marked in a
machine-readable format. This is a medium-term implementation target.

### 4.1 Current State

The ai-stack does not currently apply machine-readable watermarks or metadata
to AI-generated outputs. Open WebUI displays AI responses in a chat interface
that visually distinguishes AI from human messages, but no metadata is
embedded in exported content.

### 4.2 Implementation Roadmap

| Phase | Action | Timeline |
|-------|--------|----------|
| 1 | Monitor AI Office codes of practice for Art. 50(2) implementation guidance | Ongoing |
| 2 | Evaluate C2PA (Coalition for Content Provenance and Authenticity) integration for exported content | When C2PA tooling matures for text |
| 3 | Add `ai-generated: true` metadata to any content exported from the platform | Near-term (low effort) |

### 4.3 Interim Measure

For text content generated by the platform and published externally, deployers
should:

1. Include a disclosure statement (per Art. 50(4)): *"This content was generated
   with the assistance of an AI system."*
2. Maintain an internal log of AI-generated content published externally

---

## 5. Security Assessment Programme (NIS2 Art. 21(2)(f))

NIS2 requires policies and procedures to assess the effectiveness of
cybersecurity risk-management measures.

### 5.1 Recommended Assessment Cadence

| Assessment Type | Frequency | Scope |
|----------------|-----------|-------|
| **Vulnerability scanning** | Continuous (CI) | Container images via Grype (automated in CI pipeline) |
| **Configuration review** | Monthly | Helm values, NetworkPolicies, RBAC, secrets |
| **Penetration testing** | Annually | External and internal testing of deployed stack |
| **Red team exercise** | Annually | Full attack simulation including AI-specific vectors |
| **Dependency audit** | Continuous | Dependabot PRs reviewed for security implications |
| **SBOM review** | Per release | CycloneDX SBOM validated in CI |

### 5.2 AI-Specific Security Testing

| Test | Purpose | Tool/Method |
|------|---------|------------|
| Prompt injection testing | Verify system prompt integrity | Manual + automated prompt injection datasets |
| Model output filtering | Verify content safety controls | Red-teaming with harmful prompt datasets |
| Data exfiltration testing | Verify network isolation prevents data leaks | NetworkPolicy audit + penetration testing |
| Credential exposure testing | Verify secrets are not leaked in logs/responses | OTel trace inspection, log review |

---

## 6. Operator Training (NIS2 Art. 21(2)(g))

NIS2 requires basic cyber hygiene practices and cybersecurity training.

### 6.1 Required Training

| Role | Training Topics | Frequency |
|------|----------------|-----------|
| **Platform administrators** | Kubernetes security, Helm chart configuration, secret management, incident response, DSAR fulfilment | Annual + on onboarding |
| **End users** | AI transparency (the system is AI), data handling guidelines, prompt hygiene (avoid entering unnecessary PII), memory management | On onboarding |
| **Security team** | Incident response playbook, NIS2/GDPR notification procedures, AI-specific attack vectors | Annual |
| **Management** | Regulatory obligations overview, liability under NIS2 Art. 32 (management body accountability) | Annual |

### 6.2 NIS2 Management Accountability

NIS2 Art. 20(2) requires management bodies to:
- Approve cybersecurity risk-management measures
- Oversee their implementation
- Undergo training to identify risks and assess practices

**Action:** Ensure management has reviewed and approved the ai-stack security
controls documented in [ENTERPRISE_EVALUATION.md](../enterprise/ENTERPRISE_EVALUATION.md).

---

## 7. Cookie Consent (ePrivacy Art. 5(3) / Austrian TKG 2021 § 165)

### 7.1 Assessment

Open WebUI, as a web application, may set cookies for:
- Session management (functional — typically exempt from consent)
- Authentication tokens (functional — typically exempt)
- User preferences (functional — typically exempt)
- Analytics/tracking (requires consent — but disabled by default via
  `DO_NOT_TRACK=true` and `ANONYMIZED_TELEMETRY=false`)

### 7.2 Verification Steps

1. Deploy the stack in a test environment
2. Open browser developer tools → Application → Cookies
3. Catalogue all cookies set by Open WebUI
4. Classify each as strictly necessary vs. non-essential
5. If non-essential cookies are found, implement a consent mechanism

### 7.3 Consent Implementation

If non-essential cookies are identified:

- **Option A:** Configure Open WebUI to disable non-essential cookies
  (preferred — data minimisation)
- **Option B:** Deploy a cookie consent banner via ingress-level injection
  or Open WebUI custom HTML injection
- **Option C:** Use a third-party consent management platform

### 7.4 Current Mitigation

The chart disables all optional telemetry by default:

```yaml
DO_NOT_TRACK: "true"
SCARF_NO_ANALYTICS: "true"
ANONYMIZED_TELEMETRY: "false"
```

This significantly reduces the likelihood of non-essential cookies, but
a per-deployment audit is still recommended.

---

*Guide version: 2.0 | Based on GDPR, AI Act, NIS2, ePrivacy, and Austrian TKG 2021.*
