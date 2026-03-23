# Incident Response Playbook — ai-stack

**GDPR Art. 33/34 | NIS2 Art. 23 | AI Act Art. 73**

---

## 1. Scope

This playbook covers incident response for the ai-stack platform, addressing
three overlapping notification regimes:

| Regime | Trigger | Authority | Timeline |
|--------|---------|-----------|----------|
| **GDPR Art. 33** | Personal data breach | Data Protection Authority (DPA) | 72 hours from awareness |
| **GDPR Art. 34** | High-risk breach to individuals | Data subjects | Without undue delay |
| **NIS2 Art. 23** | Significant cybersecurity incident | CSIRT (AT: CERT.at) | 24h early warning, 72h notification, 1 month report |
| **AI Act Art. 73** | Serious AI incident (provider obligation; deployers report to providers per Art. 26(5)) | Market surveillance authority | 15 days from causal link established (Art. 73(2)); 2 days for widespread infringement (Art. 73(3)); 10 days if death involved (Art. 73(4)) |

**These obligations are cumulative.** A single event may trigger all three.

---

## 2. Incident Classification

### 2.1 Severity Levels

| Level | Description | Examples | Response |
|-------|-------------|----------|----------|
| **P1 — Critical** | Active data breach, system compromise, AI safety incident | Unauthorised access to conversation data; model producing harmful outputs at scale | Immediate response team activation |
| **P2 — High** | Potential breach, significant service disruption | Suspicious authentication failures; Qdrant exposed without API key; external API key leaked | Response within 1 hour |
| **P3 — Medium** | Contained security event, minor service impact | Failed login brute force (blocked); single-component outage | Response within 4 hours |
| **P4 — Low** | Informational, no confirmed impact | Vulnerability disclosed in dependency; anomalous telemetry pattern | Assess within 24 hours |

### 2.2 Incident Categories

| Category | GDPR Breach? | NIS2 Incident? | AI Act Incident? |
|----------|-------------|----------------|-----------------|
| Unauthorised access to user data | Yes | Likely | If AI system involved |
| Data exfiltration via external API | Yes | Yes | If prompts contained PII |
| Ransomware/malware on cluster | Yes (if data affected) | Yes | If AI service disrupted |
| Ollama model tampering | Possibly | Yes | Yes (model integrity) |
| AI system producing harmful outputs | Possibly | No | Yes (Art. 73) |
| Qdrant data corruption/loss | Yes (if personal data) | Yes | No |
| DDoS against Open WebUI | No (unless data lost) | Yes | No |
| Vulnerability in container image | No (until exploited) | Assess | No |

---

## 3. Response Procedures

### Phase 1: Detection & Triage (0–1 hour)

1. **Detect** — Sources: OTel alerts, Prometheus alerts, user reports, CVE
   advisories, external threat intelligence
2. **Assess** — Determine severity level, incident category, and which
   notification regimes are triggered
3. **Activate** — Assemble response team based on severity:
   - P1: Incident commander + security + legal + DPO + management
   - P2: Incident commander + security + DPO
   - P3: On-call engineer + security
   - P4: On-call engineer
4. **Contain** — Immediate containment actions:

   ```bash
   # Isolate compromised component (example: scale to zero)
   kubectl scale deployment ai-stack-openwebui -n ai-stack --replicas=0

   # Revoke exposed secrets
   kubectl delete secret <secret-name> -n ai-stack
   # Helm will regenerate on next reconciliation

   # Block external egress (if data exfiltration suspected)
   kubectl apply -f - <<EOF
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: emergency-block-egress
     namespace: ai-stack
   spec:
     podSelector: {}
     policyTypes: [Egress]
     egress: []  # Block all egress
   EOF
   ```

### Phase 2: Notification (1–72 hours)

#### NIS2 Early Warning (24 hours)

If the incident is significant (affects service availability, causes financial
loss, or affects other entities):

| Field | Value |
|-------|-------|
| **Authority** | CERT.at (Austrian CSIRT) |
| **Deadline** | 24 hours from awareness |
| **Content** | Whether the incident is suspected to be caused by unlawful or malicious acts; whether it could have cross-border impact |
| **Channel** | *[CERT.at reporting portal / email — verify current contact]* |

#### GDPR Breach Notification to DPA (72 hours)

If personal data is affected:

| Field | Value |
|-------|-------|
| **Authority** | Datenschutzbehörde (Austrian DPA) |
| **Deadline** | 72 hours from awareness (Art. 33(1)) |
| **Content** | Nature of breach, categories and approximate number of data subjects, DPO contact, likely consequences, measures taken |
| **Form** | *[DSB online notification form]* |
| **Exception** | Not required if breach is unlikely to result in risk to data subjects |

#### GDPR Notification to Data Subjects (without undue delay)

If breach is likely to result in **high risk** to rights and freedoms:

| Field | Value |
|-------|-------|
| **Deadline** | Without undue delay (Art. 34(1)) |
| **Content** | Clear and plain language description, DPO contact, likely consequences, measures taken and recommended |
| **Exception** | Not required if: (a) data was encrypted, (b) subsequent measures eliminate risk, or (c) disproportionate effort (use public communication instead) |

#### NIS2 Full Notification (72 hours)

| Field | Value |
|-------|-------|
| **Deadline** | 72 hours from awareness |
| **Content** | Update to early warning with: severity, impact, indicators of compromise, root cause (if known) |

#### AI Act Serious Incident Report (15 days)

If the AI system caused or contributed to a serious incident (death, serious
health damage, serious property damage, serious disruption of critical
infrastructure):

| Field | Value |
|-------|-------|
| **Authority** | National AI supervisory authority |
| **Deadline** | 15 days from awareness (Art. 73(1)) |
| **Content** | AI system identification, nature of incident, corrective measures |

### Phase 3: Eradication & Recovery (hours–days)

1. **Root cause analysis** — Identify the vulnerability or misconfiguration
2. **Eradicate** — Remove threat actor access, patch vulnerability, rotate
   all affected credentials
3. **Recover** — Restore services from backups if needed:

   ```bash
   # Restore Qdrant from backup snapshot
   kubectl exec -n ai-stack deploy/ai-stack-qdrant -- \
     /qdrant/recover-snapshot.sh /backup/qdrant-latest.snapshot

   # Restore Ollama models
   kubectl exec -n ai-stack deploy/ai-stack-ollama -- \
     cp -r /backup/ollama-latest/* /root/.ollama/
   ```

4. **Verify** — Run Helm tests to confirm service health:

   ```bash
   helm test ai-stack -n ai-stack
   ```

### Phase 4: Post-Incident (days–month)

1. **NIS2 Final Report** — Submit within 1 month (Art. 23(4)(d)):
   - Root cause analysis
   - Mitigation measures applied
   - Cross-border impact assessment

2. **Lessons Learned** — Document:
   - Timeline of events
   - Detection effectiveness
   - Response effectiveness
   - Gaps identified
   - Improvements to implement

3. **Update Controls** — Implement improvements:
   - Update NetworkPolicies if needed
   - Add OTel alerting rules for the detection gap
   - Update this playbook
   - Update DPIA if risk profile changed

---

## 4. Contact Directory

| Role | Name | Contact | Available |
|------|------|---------|-----------|
| **Incident Commander** | *[name]* | *[phone, email]* | *[hours]* |
| **DPO** | *[name]* | *[phone, email]* | *[hours]* |
| **Security Lead** | *[name]* | *[phone, email]* | *[hours]* |
| **Legal Counsel** | *[name]* | *[phone, email]* | *[hours]* |
| **Platform Admin** | *[name]* | *[phone, email]* | *[hours]* |
| **Management** | *[name]* | *[phone, email]* | *[hours]* |

### External Contacts

| Authority | Contact | Purpose |
|-----------|---------|---------|
| **CERT.at** | *[current contact]* | NIS2 incident notification |
| **Datenschutzbehörde** | *[current contact]* | GDPR breach notification |
| **National AI Authority** | *[pending designation]* | AI Act incident reporting |

---

## 5. Evidence Preservation

During any incident, preserve the following evidence:

| Evidence | Source | Preservation Method |
|----------|--------|-------------------|
| OTel traces/logs | OTel Collector export | Export to offline storage before rotation |
| Kubernetes events | `kubectl get events` | Capture to file |
| Pod logs | `kubectl logs` | Capture to file before pod restart |
| Network flows | NetworkPolicy logs (if enabled) | Export from CNI |
| Qdrant audit logs | Qdrant container logs | Capture before restart |
| Open WebUI access logs | Open WebUI container logs | Capture before restart |
| ZFS snapshots (if applicable) | ZFS pool | `zfs snapshot` before any recovery |

---

## 6. Testing

This playbook should be tested:

- **Tabletop exercise**: Quarterly — walk through a scenario without
  actually disrupting services
- **Simulation**: Annually — simulate an incident (e.g., inject a fake
  breach alert) and execute the full response procedure
- **After any real incident**: Review and update the playbook

| Test Date | Type | Scenario | Findings |
|-----------|------|----------|----------|
| *[date]* | *[tabletop/simulation]* | *[scenario]* | *[findings]* |

---

*Template version: 1.0 | Based on GDPR Art. 33/34, NIS2 Art. 23, AI Act Art. 73, and ENISA incident handling guidelines.*
