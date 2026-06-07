# EU Legal Framework Compliance Check — ai-stack

**Date:** 2026-06-07 (re-validated)
**Chart version:** 2.10.0 | **appVersion:** 2026.5
**Assessor:** Automated (Claude Code)
**Scope:** EU regulatory framework applicability and gap analysis

---

## 1. Applicable Regulations

Based on the ai-stack's profile — an AI inference and tooling platform processing
personal data, deployed for EU-regulated on-premises and hybrid operations — the
following EU regulations apply:

| Regulation | Confidence | Key Basis | Effective |
|------------|------------|-----------|-----------|
| **GDPR** (Reg. 2016/679) | Certain | Art. 2 — processes personal data of EU residents | 2018-05-25 |
| **AI Act** (Reg. 2024/1689) | Certain | Art. 50 — AI systems interacting with humans | 2024-08-01 (phased) |
| **NIS2** (Dir. 2022/2555) | Likely | Art. 21 — digital infrastructure operators | 2024-10-17 |
| **CRA** (Reg. 2024/2847) | Likely | Art. 13 — products with digital elements | 2024-12-10 (entry into force; main obligations apply 2027-12-11) |
| **ePrivacy** (Dir. 2002/58/EC) | Likely | Art. 5 — electronic communications confidentiality | In force |
| **Austrian DSG** (BGBl. I Nr. 165/1999) | Certain | National GDPR supplement | In force |

---

## 2. Regulation-by-Regulation Analysis

### 2.1 GDPR (General Data Protection Regulation)

The ai-stack processes the following categories of personal data:
- User accounts (authentication credentials, profile data)
- Conversation history (user prompts, AI responses)
- Uploaded documents (may contain arbitrary PII)
- Vector embeddings (derived from personal data via RAG)
- Cross-conversation memories (`ENABLE_MEMORIES=true`)
- Telemetry/observability data (potentially containing PII)

#### Current Controls

| GDPR Article | Requirement | Status | Evidence |
|-------------|-------------|--------|----------|
| **Art. 5(1)(c)** | Data minimisation | Partial | OTel PII redaction (email, SSN, CC patterns); but no data retention limits on conversations or embeddings |
| **Art. 5(1)(e)** | Storage limitation | Addressed | Data retention guidance and purge scripts in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §1 |
| **Art. 13** | Information to data subjects | Gap | No privacy notice template or consent mechanism in chart |
| **Art. 15** | Right of access | Addressed | DSAR procedures in [docs/compliance/DSAR_PROCEDURES.md](DSAR_PROCEDURES.md) |
| **Art. 17** | Right to erasure | Gap | No automated deletion workflow; manual Qdrant/PostgreSQL purge required |
| **Art. 22** | Automated decision-making | Attention | If AI outputs are used for decisions with legal/significant effects, Art. 22 safeguards required |
| **Art. 25** | Data protection by design/default | Strong | Default-deny networking, PSA restricted, auth required, telemetry opt-out, local-first inference, optional Authelia OIDC/MFA for enterprise SSO |
| **Art. 28** | Processor agreements | Addressed | DPA guidance, provider checklist, and GPAI documentation requirements in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2 |
| **Art. 30** | Records of processing | Addressed | ROPA template in [docs/compliance/ROPA_TEMPLATE.md](ROPA_TEMPLATE.md) |
| **Art. 32** | Security of processing | Strong | Encryption-in-transit (TLS in prod), access control (built-in + optional Authelia OIDC/MFA), network isolation, read-only filesystem, PII redaction |
| **Art. 33/34** | Breach notification | Addressed | Incident response playbook in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) |
| **Art. 35** | DPIA | Addressed | DPIA template in [docs/compliance/DPIA_TEMPLATE.md](DPIA_TEMPLATE.md) |
| **Art. 44-49** | International transfers | Addressed | Transfer assessment checklist and provider DPA status table in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2 |

#### Gaps Requiring Action

1. **Data Retention Policy (Art. 5(1)(e))** — Addressed: Retention periods, automated purge scripts, and Helm configuration guidance documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §1. Deployers must configure and schedule retention enforcement appropriate to their use case.

2. **Data Subject Rights (Art. 15-20)** — Addressed: DSAR procedures documented in [docs/compliance/DSAR_PROCEDURES.md](DSAR_PROCEDURES.md). Deployers must implement operational workflows based on these procedures.

3. **DPIA (Art. 35)** — Addressed: DPIA template provided in [docs/compliance/DPIA_TEMPLATE.md](DPIA_TEMPLATE.md). Deployers must complete it before production deployment.

4. **Records of Processing Activities (Art. 30)** — Addressed: ROPA template provided in [docs/compliance/ROPA_TEMPLATE.md](ROPA_TEMPLATE.md).

5. **Processor Agreements (Art. 28)** — Addressed: DPA pre-enablement checklist, provider DPA status table, and international transfer assessment guidance documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2. Deployers must obtain signed DPAs before enabling `externalAPIs`.

6. **Breach Notification (Art. 33/34)** — Addressed: Incident response playbook provided in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).

---

### 2.2 AI Act (Regulation 2024/1689)

#### Classification

The ai-stack deploys and integrates multiple AI systems. Classification depends on use case:

| Component | AI Act Classification | Basis | Obligations | Deadline |
|-----------|----------------------|-------|-------------|----------|
| Ollama (local LLM inference) | **Limited risk** (Art. 50) | AI system interacting with natural persons | Transparency: users must know they interact with AI | 2026-08-02 |
| Open WebUI (chat interface) | **Deployer** (Art. 26) | Deploys AI system to end users | Transparency, monitoring, logging (high-risk only) | 2026-08-02 |
| LangGraph (agentic runtime) | **Limited risk** (Art. 50) | Autonomous AI agent actions | Transparency about AI-generated content | 2026-08-02 |
| Ollama + external models | **GPAI considerations** (Art. 53) | If integrating general-purpose AI models | Documentation, downstream information | 2025-08-02 |
| Any Annex III use case | **High-risk** (Art. 6) | If used for HR, credit, law enforcement, etc. | Full conformity assessment | 2026-08-02 |

> **Open-source note:** The AI Act's open-source exemption (Art. 2(12)) does **not** apply to Art. 50 transparency obligations. AI systems released under FOSS licences are still subject to Art. 50 when placed on the market or put into service (Art. 2(12), second subparagraph). This means local Ollama models with open-source weights must still comply with Art. 50 disclosure requirements.

#### Current Controls

| AI Act Article | Requirement | Status | Evidence |
|---------------|-------------|--------|----------|
| **Art. 50(1)** | Inform users they interact with AI | Addressed | Configurable `WEBUI_BANNER_TEXT` in values.yaml with default AI disclosure text |
| **Art. 50(2)** | Machine-readable marking of AI-generated content | Gap | No watermarking or C2PA metadata applied to AI outputs |
| **Art. 50(4)** | Deep fake disclosure | N/A | Not applicable unless generating synthetic media for public dissemination |
| **Art. 13** | Transparency — provider obligation to inform deployers (high-risk) | Conditional | Tier labels and boundary annotations provide governance metadata; full compliance depends on use case. Note: Art. 13 is a provider obligation; deployers consume this information per Art. 26(9) |
| **Art. 26** | Deployer obligations (high-risk) | Conditional | Monitoring via OTel, human oversight via Open WebUI; completeness depends on use case |
| **Art. 27** | Fundamental rights impact assessment | Gap | No FRIA template provided; required for public bodies, private entities providing public services, and deployers under Annex III points 5(b)/(c) — not all high-risk deployers |
| **Art. 53** | GPAI provider obligations | Addressed | GPAI downstream documentation requirements and provider checklist in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2.3 |
| **Art. 73** | Serious incident reporting (provider obligation) | Addressed | Incident response playbook in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) covers AI-specific incidents. Note: Art. 73 applies to providers of high-risk AI systems; deployers report to providers per Art. 26(5) |

#### Gaps Requiring Action

1. **Art. 50(1) Transparency Disclosure** — Addressed: Configurable `WEBUI_BANNER_TEXT` in values.yaml provides an AI disclosure banner by default.

2. **Art. 50(2) Content Marking** — AI-generated text, images, audio, and video must be marked in a machine-readable format. No C2PA, watermarking, or metadata injection is implemented. Deployers must address this at the application layer.

3. **GPAI Downstream Documentation (Art. 53)** — Addressed: Guidance for obtaining and maintaining model documentation from GPAI providers (Art. 53(1)(b)), including technical documentation, capabilities/limitations, intended use, and copyright compliance, documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2.3.

4. **Fundamental Rights Impact Assessment (Art. 27)** — Art. 27(1) requires a FRIA for deployers that are public bodies, private entities providing public services, or deployers of systems under Annex III points 5(b) (creditworthiness) and 5(c) (risk assessment/pricing for life and health insurance). Not all Annex III high-risk deployers are subject to this obligation.

5. **Incident Reporting (Art. 73)** — Addressed: Incident response playbook in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) covers AI-specific serious incident reporting. Note: Art. 73 is a provider obligation; as a deployer platform, reporting flows through providers per Art. 26(5), with deployers informing providers of serious incidents.

---

### 2.3 NIS2 (Directive 2022/2555)

NIS2 applicability depends on whether the deploying organization falls within Annex I/II sectors and size thresholds. If the ai-stack is deployed by an essential or important entity (e.g., digital infrastructure provider, healthcare, energy), NIS2 Art. 21 cybersecurity risk-management measures apply directly.

**Note:** NIS2 is a directive — Austrian transposition via the Netz- und Informationssystemsicherheitsgesetz (NISG) 2024 must be checked for national specifics.

#### Current Controls (mapped to Art. 21(2))

| NIS2 Art. 21(2) | Requirement | Status | Evidence |
|-----------------|-------------|--------|----------|
| **(a)** Risk analysis & IS security policies | Strong | Tier classification, boundary annotations, governance-as-code |
| **(b)** Incident handling | Strong | OTel observability for detection; incident response playbook in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) |
| **(c)** Business continuity & DR | Good | PVC snapshots with external DR (Velero), PDB, HA in prod profile |
| **(d)** Supply chain security | Strong | CycloneDX SBOM, Syft deep SBOMs, Renovate (digest-pinned images) + Dependabot (GitHub Actions), license compliance matrix |
| **(e)** Security in acquisition/development | Strong | PSA restricted, default-deny networking, CI validation (Helm lint, kubeconform, SBOM) |
| **(f)** Effectiveness assessment | Good | Penetration testing cadence, AI-specific security testing, and assessment programme documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §5 |
| **(g)** Cyber hygiene & training | Addressed | Operator training requirements and role-based training matrix documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §6 |
| **(h)** Cryptography & encryption | Addressed | Encryption-at-rest requirements, PVC classification, and implementation options documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §3 |
| **(i)** Access control & asset management | Strong | Per-component ServiceAccounts, RBAC, `automountServiceAccountToken: false` |
| **(j)** MFA/continuous auth | Strong | Open WebUI built-in auth; optional Authelia OIDC/MFA for enterprise SSO (`authelia.defaultPolicy: two_factor`) |

#### Gaps Requiring Action

1. **Incident Response Procedure (Art. 21(2)(b))** — Addressed: Incident response playbook provided in [docs/compliance/INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) covering detection, triage, containment, eradication, and notification workflows.

2. **Encryption at Rest (Art. 21(2)(h))** — Addressed: PVC classification, encryption-at-rest requirements, and implementation options (StorageClass encryption, LUKS, KMS) documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §3.

3. **Security Effectiveness Assessment (Art. 21(2)(f))** — Addressed: Security assessment cadence, AI-specific security testing programme, and penetration testing recommendations documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §5.

4. **Cyber Hygiene Training (Art. 21(2)(g))** — Addressed: Role-based training requirements for platform administrators, end users, security team, and management documented in [docs/compliance/EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §6.

---

### 2.4 Cyber Resilience Act (CRA, Regulation 2024/2847)

The CRA applies to "products with digital elements" placed on the EU market. Whether the ai-stack Helm chart constitutes a product with digital elements depends on how it is distributed:

- **If distributed commercially** (even as part of a service): CRA Art. 13 obligations apply to the manufacturer, including cybersecurity risk assessment, vulnerability handling, SBOM, CE marking, and a minimum 5-year support period.
- **If distributed as free/open-source software not in the course of a commercial activity**: Outside CRA scope per Art. 3(22) definition of "making available on the market" (requires commercial activity). See Recitals 17-20 for guidance on what constitutes commercial activity for FOSS.
- **Open-source software stewards**: If a legal entity systematically supports FOSS intended for commercial activities, limited obligations apply under Art. 24 (security policies, vulnerability cooperation, SBOM).
- **Component-level obligations**: Even under the FOSS exclusion, due diligence on third-party components (Art. 13(5)) applies to integrators.

#### Current Controls

| CRA Requirement | Status | Evidence |
|----------------|--------|----------|
| SBOM (Part II, Annex I) | Strong | CycloneDX 1.6 SBOM, Syft deep SBOMs in CI, validated against schema |
| Vulnerability handling | Strong | Dependabot for GitHub Actions updates; Grype CVE scanning in CI; CVD policy in SECURITY.md |
| Cybersecurity risk assessment | Partial | Tier classification, boundary annotations; no formal risk assessment document |
| Security updates for support period | N/A | Depends on distribution model |
| CE marking / Declaration of Conformity | N/A | Only if commercially distributed |

**CRA Phased Application (Art. 71):**
- **2024-12-10**: Entry into force
- **2026-06-11**: Conformity assessment body notification (Chapter IV, Art. 35-51)
- **2026-09-11**: Reporting obligations (Art. 14)
- **2027-12-11**: Full application (all manufacturer obligations, Art. 13)

#### Gaps Requiring Action

1. **Coordinated Vulnerability Disclosure Policy (Art. 13(8))** — Addressed: CVD policy documented in [SECURITY.md](../../SECURITY.md).

2. **CVE Monitoring** — Addressed: Grype scans all container images in CI (`cve-scan` job) and fails on critical vulnerabilities.

3. **SBOM Format** — CRA Art. 13(24) anticipates implementing acts specifying SBOM format. Current CycloneDX 1.6 is well-positioned but should be monitored for mandated format changes.

---

### 2.5 ePrivacy (Directive 2002/58/EC)

If the platform is accessible via web browser (Open WebUI), ePrivacy provisions on cookies/tracking apply. The chart sets `DO_NOT_TRACK=true` and `ANONYMIZED_TELEMETRY=false`, which is positive. However:

- **Cookie consent**: If Open WebUI sets any non-essential cookies, a consent mechanism is required under ePrivacy Art. 5(3). The chart does not provide a cookie consent banner.
- **Austrian TKG 2021 § 165**: Implements ePrivacy cookie provisions in Austrian law. Cookie consent requirements apply.

**Status:** Attention — deployers must verify Open WebUI's cookie behavior and implement consent mechanisms if non-essential cookies are set.

---

## 3. Cross-Regulation Interactions

| Interaction | Impact |
|------------|--------|
| **GDPR Art. 35 + AI Act Art. 27** | Both require impact assessments (DPIA and FRIA). These can be combined into a single integrated assessment covering data protection and fundamental rights. |
| **GDPR Art. 33 + NIS2 Art. 23** | Dual notification obligations: GDPR breach to DPA (72h) and NIS2 incident to CSIRT (24h early warning + 72h full). These are independent and cumulative per GDPR Guide cross-regulation note. |
| **GDPR Art. 22 + AI Act Art. 14** | Automated decision-making safeguards under GDPR stack with AI Act human oversight requirements for high-risk systems. |
| **CRA SBOM + NIS2 Art. 21(2)(d)** | CRA SBOM obligations complement NIS2 supply chain security requirements. The existing CycloneDX SBOM serves both. |
| **AI Act Art. 50 + GDPR Art. 13** | AI transparency obligations supplement GDPR information duties. Both must be addressed in user-facing notices. |

---

## 4. Austrian National Law Specifics

| Law | Relevance | Notes |
|-----|-----------|-------|
| **Datenschutzgesetz (DSG)** | GDPR supplement | §§ 1-4: constitutional right to data protection; § 4: images as personal data; § 12: data processing for scientific research. DSG supplements but does not override GDPR. |
| **TKG 2021 § 165** | ePrivacy cookie consent | Implements ePrivacy Art. 5(3). Consent required for non-essential cookies/tracking. |
| **NISG 2024** | NIS2 transposition | Austrian transposition of NIS2. Defines essential/important entities, CSIRT (CERT.at), and notification procedures. Deployers must check classification under NISG. |
| **AI Act** | Directly applicable | EU Regulation — no transposition needed. Austrian national AI authority designation pending. |

---

## 5. Compliance Scorecard

| Regulation | Current Posture | Priority Gaps |
|------------|----------------|---------------|
| **GDPR** | Good | Art. 17 (automated erasure), Art. 13 (privacy notice in chart) |
| **AI Act** | Good | Content marking (Art. 50(2)) |
| **NIS2** | Strong | No critical gaps remaining |
| **CRA** | Strong | Formal risk assessment (if commercially distributed) |
| **ePrivacy** | Good | Cookie consent mechanism verification (per-deployment audit recommended) |

---

## 6. Recommended Actions (Prioritised)

### Critical (address before production deployment)

| # | Action | Regulation | Effort |
|---|--------|-----------|--------|
| 1 | ~~**Create DPIA template**~~ | GDPR Art. 35, AI Act Art. 27 | Done — [DPIA_TEMPLATE.md](DPIA_TEMPLATE.md) |
| 2 | ~~**Add AI transparency disclosure**~~ | AI Act Art. 50(1) | Done — `WEBUI_BANNER_TEXT` in values.yaml |
| 3 | ~~**Document data retention policy**~~ and provide guidance for automated purge of conversations, embeddings, uploaded docs | GDPR Art. 5(1)(e) | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §1 |
| 4 | ~~**Create incident response playbook**~~ | GDPR + NIS2 | Done — [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) |

### High (address within first quarter of operation)

| # | Action | Regulation | Effort |
|---|--------|-----------|--------|
| 5 | ~~**Document DSAR procedures**~~ | GDPR Art. 15-20 | Done — [DSAR_PROCEDURES.md](DSAR_PROCEDURES.md) |
| 6 | ~~**Provide ROPA template**~~ | GDPR Art. 30 | Done — [ROPA_TEMPLATE.md](ROPA_TEMPLATE.md) |
| 7 | ~~**Add DPA guidance**~~ for external API providers with checklist of required contractual clauses | GDPR Art. 28, Art. 44-49 | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2 |
| 8 | ~~**Integrate CVE scanning**~~ | CRA Art. 13 | Done — Grype `cve-scan` job in CI |
| 9 | ~~**Document encryption-at-rest requirements**~~ for PVCs in operator guidance | NIS2 Art. 21(2)(h) | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §3 |

### Medium (address within first year)

| # | Action | Regulation | Effort |
|---|--------|-----------|--------|
| 10 | **Implement AI content marking** (C2PA metadata or watermarking) for AI-generated outputs | AI Act Art. 50(2) | High |
| 11 | ~~**Create coordinated vulnerability disclosure policy**~~ | CRA Art. 13(8) | Done — [SECURITY.md](../../SECURITY.md) |
| 12 | ~~**Document GPAI downstream obligations**~~ — guidance for deployers using external model providers | AI Act Art. 53 | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §2.3 |
| 13 | ~~**Add security audit/pentest cadence**~~ to operator documentation | NIS2 Art. 21(2)(f) | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §5 |
| 14 | ~~**Document operator training requirements**~~ for platform security | NIS2 Art. 21(2)(g) | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §6 |
| 15 | ~~**Verify cookie behavior**~~ and provide consent mechanism guidance | ePrivacy/TKG 2021 | Done — [EU_OPERATIONS_GUIDE.md](EU_OPERATIONS_GUIDE.md) §7 |

---

## 7. Methodology

This assessment was conducted by:

1. **Regulation identification** — Using EU Regulation applicability checks for the `other/ai_platform` sector with AT member state context
2. **Article-level analysis** — Reviewing full text of key provisions: GDPR Art. 22, 25, 32, 35; AI Act Art. 50, 53; NIS2 Art. 21; CRA Art. 13
3. **Control mapping** — Mapping existing chart controls (values.yaml, templates, documentation) against regulatory requirements
4. **Austrian national law** — Searching the Datenschutzgesetz and related Austrian federal statutes for supplementary obligations
5. **Cross-regulation analysis** — Identifying stacking and lex specialis interactions per regulation guides
6. **Gap identification** — Flagging missing controls, documentation, or operational procedures

### Data Sources

- EU Regulations database (CELEX)
- Austrian RIS OGD (Federal Chancellery)
- ai-stack chart source code and documentation
- GDPR, AI Act, NIS2, and CRA regulation guides

### Validation (2026-03-23)

Cross-checked against EU regulation full texts and Austrian RIS OGD. Corrections applied:

1. **NIS2 effective date** — Corrected from 2024-10-18 to 2024-10-17 (CELEX 32022L2555)
2. **CRA FOSS exception** — Removed incorrect "Art. 53(2)" reference; FOSS exclusion operates via Art. 3(22) definition scope (Recitals 17-20)
3. **CRA phased timeline** — Added Art. 71 phased application dates (full application 2027-12-11, not just entry into force 2024-12-10)
4. **AI Act Art. 26 deadline** — Corrected from "In force" to 2026-08-02 (Chapter III general application date)
5. **AI Act Art. 27 FRIA scope** — Narrowed to actual scope per Art. 27(1): public bodies, public service providers, and Annex III points 5(b)/(c) deployers only
6. **AI Act Art. 73 provider/deployer distinction** — Clarified Art. 73 is a provider obligation; deployers report to providers per Art. 26(5)
7. **AI Act Art. 73 timelines** — Added nuanced deadlines from Art. 73(2)-(4): 15 days (general), 2 days (widespread), 10 days (death)
8. **AI Act Art. 13 role** — Corrected from deployer obligation to provider obligation (deployers consume info per Art. 26(9))
9. **Incident response authority** — Corrected from "National AI authority" to "Market surveillance authority" per Art. 73(1)

### Validation (2026-03-26)

Cross-checked against EUR-Lex full texts (CELEX 32024R1689, 32024R2847, 32022L2555), artificialintelligenceact.eu article annotations, digital-strategy.ec.europa.eu CRA implementation pages, and Austrian RIS OGD (Gesetzesnummer 10001597). Corrections applied:

10. **AI Act Art. 50 deadline** — Corrected Ollama and LangGraph Art. 50 deadlines from "In force" to 2026-08-02. Art. 50 transparency obligations become applicable 24 months after entry into force per Art. 113(a), i.e. 2 August 2026.
11. **AI Act Art. 50 open-source exemption** — Added note that the FOSS exemption (Art. 2(12)) does not apply to Art. 50. Open-source AI systems must still comply with transparency requirements.
12. **CRA Chapter IV label** — Corrected "Market surveillance" to "Conformity assessment body notification". Chapter IV (Art. 35-51) covers notification of conformity assessment bodies, not market surveillance.
13. **Incident response Art. 73 authority** — Corrected remaining "National AI supervisory authority" references in INCIDENT_RESPONSE.md to "Market surveillance authority" per Art. 73(1).
14. **Incident response Art. 73 death timeline** — Clarified that death reporting requires immediate notification upon suspected causal link, with 10-day outer limit (Art. 73(4)), not just the outer limit.
15. **LICENSE_COMPLIANCE.md version alignment** — Updated 8 component versions to match values.yaml: Ollama 0.18.2, Qdrant v1.17.0, Tika 3.3.0.0, SearXNG 2026.3.23, OTel 0.148.0, PostgreSQL 17-alpine, Open Terminal 0.11.27, Ingestion Worker 3.13-slim.

### Limitations

- This is a **technical compliance gap analysis**, not legal advice. Formal legal review by qualified counsel is recommended before production deployment.
- Austrian NISG 2024 transposition details were not fully available in the legislation database; manual verification against the official Bundesgesetzblatt is recommended.
- Austrian DSG (BGBl. I Nr. 165/1999) and TKG 2021 section references could not be fully validated against the RIS OGD database due to indexing coverage; citations are based on established legal references.
- CRA applicability depends on the distribution model (commercial vs. FOSS); both scenarios are addressed.
- AI Act classification depends on the specific use case; high-risk scenarios are flagged as conditional.
- ePrivacy assessment is preliminary; a detailed cookie audit of Open WebUI is needed.

---

*This document should be reviewed and updated when: (a) new components are added, (b) the deployment model changes, (c) EU regulations are amended, or (d) national transposition acts are published.*
