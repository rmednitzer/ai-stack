# Records of Processing Activities — ai-stack

**GDPR Art. 30**

*Pre-filled with ai-stack processing activities. Complete organisation-specific fields before deployment.*

---

## Controller Information (Art. 30(1))

| Field | Value |
|-------|-------|
| **Controller name** | *[Your organisation]* |
| **Contact details** | *[Address, email, phone]* |
| **Joint controller (if any)** | *[Name, contact]* |
| **DPO contact** | *[Name, email]* |
| **Representative (if outside EU)** | *[Name, contact]* |

---

## Processing Activities

### PA-01: AI-Assisted Chat

| Field | Value |
|-------|-------|
| **Purpose** | AI-assisted question answering and conversation |
| **Legal basis** | *[Art. 6(1)(a) consent / (b) contract / (f) legitimate interest]* |
| **Categories of data subjects** | *[employees / customers / public]* |
| **Categories of personal data** | User identity (name, email), conversation content (prompts, AI responses), session metadata |
| **Recipients** | Internal: platform administrators. External: *[none / external API providers if enabled]* |
| **Transfers to third countries** | *[None if local-only / Provider jurisdiction if externalAPIs enabled]* |
| **Safeguards for transfers** | *[N/A / SCCs / adequacy decision]* |
| **Retention period** | *[specify — e.g., 12 months, then archived/deleted]* |
| **Technical & organisational measures** | TLS, authentication, NetworkPolicy, PSA restricted, PII redaction in telemetry |

### PA-02: Document Retrieval (RAG)

| Field | Value |
|-------|-------|
| **Purpose** | Document upload, extraction, embedding, and AI-augmented retrieval |
| **Legal basis** | *[specify]* |
| **Categories of data subjects** | *[document subjects — may include employees, customers, third parties]* |
| **Categories of personal data** | Uploaded documents (may contain any PII), vector embeddings, document metadata |
| **Recipients** | Internal: authenticated users with access. External: none (processing is local) |
| **Transfers to third countries** | None (Tika, Ollama, Qdrant are local) |
| **Retention period** | *[specify — embeddings in Qdrant, documents in Open WebUI]* |
| **Technical & organisational measures** | Tika runs on tmpfs, embeddings in access-controlled Qdrant, per-user scope |

### PA-03: Cross-Conversation Memory

| Field | Value |
|-------|-------|
| **Purpose** | Storing user facts across conversations for improved context |
| **Legal basis** | *[specify — likely Art. 6(1)(a) consent or (f) legitimate interest]* |
| **Categories of data subjects** | Platform users |
| **Categories of personal data** | User-derived facts stored as vector embeddings |
| **Recipients** | Internal: the user themselves (memories are per-user) |
| **Transfers to third countries** | None |
| **Retention period** | *[specify — until user deletes or admin purges]* |
| **Technical & organisational measures** | Per-user isolation, user can view and delete memories via UI |

### PA-04: User Authentication & Account Management

| Field | Value |
|-------|-------|
| **Purpose** | User registration, login, session management |
| **Legal basis** | Art. 6(1)(b) contract performance |
| **Categories of data subjects** | Platform users |
| **Categories of personal data** | Name, email, hashed password, session tokens |
| **Recipients** | Internal: platform administrators |
| **Transfers to third countries** | None |
| **Retention period** | *[specify — duration of account + N days after deletion]* |
| **Technical & organisational measures** | Password hashing, session management via Valkey, HTTPS |

### PA-05: System Observability & Logging

| Field | Value |
|-------|-------|
| **Purpose** | Platform monitoring, performance analysis, incident detection |
| **Legal basis** | Art. 6(1)(f) legitimate interest (security monitoring) |
| **Categories of data subjects** | Platform users (indirectly via telemetry) |
| **Categories of personal data** | Request metadata, performance metrics. PII redacted (email, SSN, CC patterns blocked) |
| **Recipients** | Internal: platform operators |
| **Transfers to third countries** | None (OTel endpoint is internal) |
| **Retention period** | *[specify — e.g., 30 days for logs, 90 days for metrics]* |
| **Technical & organisational measures** | PII redaction via OTel Collector, internal-only endpoint, `DO_NOT_TRACK=true` |

### PA-06: External API Inference *(conditional — only when externalAPIs.enabled=true)*

| Field | Value |
|-------|-------|
| **Purpose** | Cloud-hosted LLM inference for user queries |
| **Legal basis** | *[specify — must have basis for transferring prompts to third party]* |
| **Categories of data subjects** | Platform users |
| **Categories of personal data** | User prompts, conversation context sent to provider API |
| **Recipients** | External API provider: *[OpenAI / Anthropic / Azure / etc.]* |
| **Transfers to third countries** | *[specify per provider — e.g., US for OpenAI]* |
| **Safeguards for transfers** | *[SCCs / DPA / adequacy decision]* |
| **Retention period** | *[per provider data retention policy]* |
| **Technical & organisational measures** | HTTPS, API key in Secret, rate limiting, DPA with provider |

### PA-07: Agentic Workflows *(conditional — only when langgraph.enabled=true)*

| Field | Value |
|-------|-------|
| **Purpose** | Multi-step AI agent task execution with persistent state |
| **Legal basis** | *[specify]* |
| **Categories of data subjects** | Platform users, subjects of agent-processed data |
| **Categories of personal data** | Agent state, tool call inputs/outputs, conversation checkpoints |
| **Recipients** | Internal: authenticated users |
| **Transfers to third countries** | None (PostgreSQL is local) |
| **Retention period** | *[specify — checkpoint retention in PostgreSQL]* |
| **Technical & organisational measures** | PostgreSQL TLS (prod), per-user scope, audit via OTel |

---

## Processor Records (Art. 30(2))

*Complete if your organisation acts as a processor for another controller.*

| Field | Value |
|-------|-------|
| **Processor name** | *[Your organisation]* |
| **Controller name(s)** | *[Each controller you process for]* |
| **Categories of processing** | *[as above, per controller agreement]* |
| **Transfers to third countries** | *[as above]* |
| **Technical & organisational measures** | *[as above]* |

---

*Template version: 2.0 | Based on GDPR Art. 30 and EDPB recommendations.*
