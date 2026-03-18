# Data Protection Impact Assessment — ai-stack

**GDPR Art. 35 | AI Act Art. 27 (Fundamental Rights Impact Assessment)**

*This is a template. Complete all sections before production deployment.*

---

## 1. Assessment Metadata

| Field | Value |
|-------|-------|
| **Organisation** | *[Your organisation name]* |
| **Assessment date** | *[YYYY-MM-DD]* |
| **Assessor(s)** | *[Name, role]* |
| **DPO consulted** | *[Name, date] (GDPR Art. 35(2))* |
| **Review date** | *[Next review — at least annually or on material change]* |
| **Version** | *[1.0]* |
| **Status** | *[Draft / Under review / Approved]* |

---

## 2. Processing Description (Art. 35(7)(a))

### 2.1 System Overview

The ai-stack is an AI inference and tooling platform comprising:

| Component | Function | Data Processed |
|-----------|----------|----------------|
| Open WebUI | User interface, authentication, conversation storage | User credentials, chat history, uploaded files |
| Ollama | Local LLM inference | User prompts (transient), model weights |
| Qdrant | Vector database for RAG | Document embeddings, metadata |
| Tika | Document extraction | Uploaded documents (transient) |
| SearXNG | Web search for RAG | Search queries (transient) |
| Pipelines | Function/tool calling | Varies by pipeline function |
| OTel Collector | Observability | Telemetry data (PII-redacted) |

### 2.2 Categories of Data Subjects

- [ ] Employees / internal users
- [ ] Customers / clients
- [ ] Partners / contractors
- [ ] Members of the public
- [ ] Other: *[specify]*

### 2.3 Categories of Personal Data

- [ ] Identity data (name, email, username)
- [ ] Authentication credentials (passwords, tokens)
- [ ] Conversation content (prompts, AI responses)
- [ ] Uploaded documents (may contain any category of personal data)
- [ ] Vector embeddings derived from personal data
- [ ] Cross-conversation memories (user facts stored as embeddings)
- [ ] Behavioural data (usage patterns, session logs)
- [ ] Special category data (Art. 9): *[specify if applicable]*
- [ ] Criminal offence data (Art. 10): *[specify if applicable]*

### 2.4 Purposes of Processing

| Purpose | Legal Basis (Art. 6(1)) | Description |
|---------|------------------------|-------------|
| AI-assisted chat | *[e.g., (a) consent / (b) contract / (f) legitimate interest]* | Users interact with LLMs for *[specify use case]* |
| Document retrieval (RAG) | *[legal basis]* | Users upload documents for AI-augmented search and Q&A |
| Cross-conversation memory | *[legal basis]* | Platform stores user facts across sessions for context |
| Observability/logging | *[(f) legitimate interest]* | System monitoring with PII redaction |
| *[Add additional purposes]* | | |

### 2.5 Data Flows

```
User → [Ingress/TLS] → Open WebUI → Ollama (local inference)
                                   → Qdrant (vector storage)
                                   → Tika (document extraction)
                                   → SearXNG (web search)
                                   → Pipelines (function calling)
                                   → External APIs (opt-in, cloud providers)
                         ↓
                    OTel Collector (PII-redacted telemetry)
```

**External data transfers** (only when `externalAPIs.enabled=true`):

| Provider | Destination | Transfer Mechanism | Safeguard |
|----------|-------------|-------------------|-----------|
| *[e.g., OpenAI]* | *[e.g., US]* | API call (HTTPS) | *[e.g., SCCs, DPA]* |

### 2.6 Data Retention

| Data Category | Retention Period | Deletion Method |
|---------------|-----------------|-----------------|
| User accounts | *[specify]* | Admin deletion via Open WebUI |
| Conversations | *[specify]* | *[see §7 data retention controls]* |
| Vector embeddings | *[specify]* | Qdrant collection deletion |
| Uploaded documents | *[specify]* | Open WebUI file management |
| Cross-conversation memories | *[specify]* | Open WebUI memory management |
| Telemetry/logs | *[specify]* | OTel pipeline TTL / log rotation |

---

## 3. Necessity and Proportionality (Art. 35(7)(b))

### 3.1 Necessity Assessment

For each purpose, confirm that AI processing is necessary:

| Purpose | Why AI processing is necessary | Alternatives considered |
|---------|-------------------------------|----------------------|
| *[purpose]* | *[justification]* | *[alternatives rejected and why]* |

### 3.2 Proportionality Assessment

- [ ] Data collected is limited to what is necessary (data minimisation)
- [ ] Retention periods are defined and enforced
- [ ] Access is restricted to authorised users (authentication required)
- [ ] Local inference is used by default (no external data transfer)
- [ ] PII redaction is applied to telemetry data
- [ ] External API providers are opt-in only

### 3.3 Data Minimisation Measures

| Measure | Status | Notes |
|---------|--------|-------|
| Authentication required | Implemented | `WEBUI_AUTH=true` |
| Per-user data isolation | Implemented | Open WebUI user scope |
| PII redaction in telemetry | Implemented | OTel Collector patterns |
| Local-first inference | Implemented | Ollama on-premises |
| Telemetry opt-out | Implemented | `DO_NOT_TRACK=true` |
| Document processing ephemeral | Implemented | Tika tmpfs mount |

---

## 4. Risk Assessment (Art. 35(7)(c))

### 4.1 Risk Matrix

| Risk | Likelihood | Severity | Residual Risk | Mitigation |
|------|-----------|----------|---------------|------------|
| Unauthorised access to conversations | *[Low/Med/High]* | *[Low/Med/High]* | *[Low/Med/High]* | Authentication, NetworkPolicy, RBAC |
| Data leakage via external API providers | *[assess]* | *[assess]* | *[assess]* | External APIs disabled by default; DPA required |
| AI hallucination causing harm | *[assess]* | *[assess]* | *[assess]* | Human oversight, transparency disclosure |
| PII in vector embeddings | *[assess]* | *[assess]* | *[assess]* | Access control, embedding not directly reversible |
| Model memorisation of training data | *[assess]* | *[assess]* | *[assess]* | Local models only; no fine-tuning on user data by default |
| Cross-conversation memory profiling | *[assess]* | *[assess]* | *[assess]* | Memory feature can be disabled; user can delete memories |
| Breach of telemetry data | *[assess]* | *[assess]* | *[assess]* | PII redaction, internal-only OTel endpoint |
| Automated decision-making (Art. 22) | *[assess]* | *[assess]* | *[assess]* | *[see §4.2]* |

### 4.2 Automated Decision-Making (GDPR Art. 22)

Does the system produce decisions with legal or similarly significant effects?

- [ ] **No** — The system is used as an assistive tool with human oversight. *[Document how human oversight is maintained.]*
- [ ] **Yes** — Art. 22 safeguards must be implemented:
  - [ ] Right to human intervention
  - [ ] Right to express point of view
  - [ ] Right to contest the decision
  - [ ] Suitable measures to safeguard rights and freedoms

### 4.3 Fundamental Rights Impact (AI Act Art. 27)

*Complete this section if the AI system is classified as high-risk under AI Act Art. 6.*

| Fundamental Right | Impact Assessment | Mitigation |
|-------------------|-------------------|------------|
| Non-discrimination (CFR Art. 21) | *[assess bias risk in model outputs]* | *[e.g., model evaluation, human review]* |
| Privacy (CFR Art. 7) | *[covered by GDPR analysis above]* | *[see §4.1]* |
| Data protection (CFR Art. 8) | *[covered by GDPR analysis above]* | *[see §4.1]* |
| Freedom of expression (CFR Art. 11) | *[assess content filtering impact]* | *[document content policy]* |
| Right to effective remedy (CFR Art. 47) | *[assess contestability of AI outputs]* | *[human oversight, complaint mechanism]* |
| *[Add rights relevant to your use case]* | | |

---

## 5. Safeguards and Measures (Art. 35(7)(d))

### 5.1 Technical Measures (implemented by ai-stack)

| Measure | GDPR Article | Status |
|---------|-------------|--------|
| TLS encryption in transit | Art. 32(1)(a) | Enabled in prod profile |
| Default-deny NetworkPolicy | Art. 32(1)(b) | Enabled by default |
| PSA restricted security context | Art. 32(1)(b) | Enforced |
| Per-component service accounts | Art. 32(1)(b) | Implemented |
| PII redaction in telemetry | Art. 5(1)(c) | OTel Collector |
| Authentication required | Art. 32(1)(b) | `WEBUI_AUTH=true` |
| Read-only root filesystem | Art. 32(1)(b) | Most components |
| Secret auto-generation | Art. 32(1)(a) | 64-byte keys |
| Backup and disaster recovery | Art. 32(1)(c) | Veeam K10 backup policies |
| Health monitoring | Art. 32(1)(d) | OTel + Prometheus |
| AI transparency disclosure | AI Act Art. 50(1) | `WEBUI_BANNER_TEXT` |

### 5.2 Organisational Measures (deployer responsibility)

| Measure | Status | Owner |
|---------|--------|-------|
| DPO designation (if required) | *[Appointed / Not required]* | *[Name]* |
| Staff training on data protection | *[Planned / Complete]* | *[Name]* |
| Incident response procedure | *[Documented / In progress]* | *[Name]* |
| Data subject rights procedures | *[Documented / In progress]* | *[Name]* |
| Regular access reviews | *[Scheduled / Ad hoc]* | *[Name]* |
| Processor agreements (DPAs) | *[Complete / In progress]* | *[Name]* |

---

## 6. Consultation

### 6.1 DPO Consultation (Art. 35(2))

| Date | DPO Name | Advice Given | Action Taken |
|------|----------|-------------|--------------|
| *[date]* | *[name]* | *[summary]* | *[action]* |

### 6.2 Data Subject Views (Art. 35(9))

*Where appropriate, document consultation with data subjects or their representatives.*

| Date | Method | Outcome |
|------|--------|---------|
| *[date]* | *[survey / focus group / user testing]* | *[summary]* |

### 6.3 Prior Consultation with Supervisory Authority (Art. 36)

*Required if the DPIA indicates high residual risk that cannot be mitigated.*

- [ ] Not required — residual risks are acceptable after mitigation
- [ ] Required — prior consultation with *[DPA name]* initiated on *[date]*

---

## 7. Decision

| Outcome | Approved By | Date |
|---------|------------|------|
| *[Proceed / Proceed with conditions / Do not proceed]* | *[Name, role]* | *[date]* |

**Conditions (if applicable):**

1. *[condition]*
2. *[condition]*

---

## 8. Review Schedule

This DPIA must be reviewed:
- At least annually
- When the processing changes materially
- When new risks are identified
- When the regulatory landscape changes

| Review Date | Reviewer | Changes Made |
|------------|----------|-------------|
| *[date]* | *[name]* | *[Initial assessment]* |

---

*Template version: 1.0 | Based on GDPR Art. 35, AI Act Art. 27, and EDPB Guidelines on DPIAs (WP 248 rev.01)*
