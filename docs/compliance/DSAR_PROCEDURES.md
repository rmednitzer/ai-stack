# Data Subject Access Request (DSAR) Procedures — ai-stack

**GDPR Art. 15–22**

---

## 1. Overview

Data subjects have the following rights under GDPR. This document provides
operational procedures for fulfilling each right within the ai-stack platform.

| Right | Article | Deadline | Applies to ai-stack? |
|-------|---------|----------|---------------------|
| Access | Art. 15 | 1 month | Yes |
| Rectification | Art. 16 | 1 month | Yes |
| Erasure ("right to be forgotten") | Art. 17 | 1 month | Yes |
| Restriction of processing | Art. 18 | 1 month | Yes |
| Data portability | Art. 20 | 1 month | Yes |
| Object | Art. 21 | Without undue delay | Yes (if processing based on legitimate interest) |
| Automated decision-making | Art. 22 | N/A (ongoing) | Conditional (see §8) |

**Deadline:** 1 month from receipt, extendable by 2 months for complex requests
(Art. 12(3)). Must inform data subject of extension within 1 month.

---

## 2. Request Intake

### 2.1 Channels

DSARs may arrive via:
- Email to DPO: *[dpo@example.com]*
- Web form: *[URL]*
- Post: *[address]*
- Verbal (must be documented immediately)

### 2.2 Identity Verification

Before processing any DSAR:
1. Verify the requester's identity (Art. 12(6))
2. Match the request to an Open WebUI user account
3. If identity cannot be verified, request additional information (the 1-month
   clock pauses until verification is complete)

### 2.3 Logging

Log every DSAR in the register:

| Field | Value |
|-------|-------|
| Request ID | *[unique ID]* |
| Date received | *[date]* |
| Data subject | *[name/identifier]* |
| Right(s) exercised | *[Art. 15/16/17/18/20/21/22]* |
| Identity verified | *[yes/no/pending]* |
| Deadline | *[1 month from receipt]* |
| Status | *[Received / In progress / Complete / Refused]* |
| Response date | *[date]* |

---

## 3. Right of Access (Art. 15)

The data subject has the right to obtain confirmation of processing and a copy
of their personal data.

### Data locations in ai-stack

| Data | Location | Export Method |
|------|----------|-------------|
| User profile | Open WebUI database | Open WebUI Admin Panel → Users → Export |
| Conversations | Open WebUI database | Open WebUI Settings → Chats → Export All Chats (JSON) |
| Uploaded documents | Open WebUI file storage | Open WebUI → Documents → Download per document |
| Vector embeddings | Qdrant | `curl http://qdrant:6333/collections/{collection}/points/scroll` with user metadata filter |
| Cross-conversation memories | Open WebUI (Qdrant-backed) | Open WebUI Settings → Memories → view/export |
| LangGraph checkpoints | PostgreSQL | `psql -c "SELECT * FROM checkpoints WHERE user_id = '...'"` |
| Telemetry/logs | OTel pipeline | PII-redacted; may not contain identifiable data |

### Procedure

1. Identify all data stores containing the data subject's data
2. Export data from each location using the methods above
3. Compile into a structured, machine-readable format (JSON preferred)
4. Include the Art. 15(1) information:
   - Purposes of processing
   - Categories of data
   - Recipients
   - Retention periods
   - Rights information
   - Source of data (if not from the data subject)
   - Existence of automated decision-making (Art. 22)
5. Provide via secure channel within deadline

---

## 4. Right to Rectification (Art. 16)

### Procedure

| Data | Rectification Method |
|------|---------------------|
| User profile (name, email) | Open WebUI Admin Panel → Users → Edit user |
| Conversation content | Not directly editable (conversations are historical records). Document the correction as an addendum. |
| Uploaded documents | Delete incorrect document, upload corrected version |
| Vector embeddings | Delete and re-embed corrected source document (see §5 for deletion) |
| Memories | User can edit/delete memories via Open WebUI Settings → Memories |

---

## 5. Right to Erasure (Art. 17)

### Procedure

**Step 1: Delete user conversations**

Via Open WebUI Admin Panel, or programmatically:

```bash
# Access Open WebUI admin API
kubectl exec -n ai-stack deploy/ai-stack-openwebui -- \
  curl -s -X DELETE "http://localhost:8080/api/v1/chats/user/{user_id}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

**Step 2: Delete vector embeddings**

```bash
# Delete user's document embeddings from Qdrant
kubectl exec -n ai-stack deploy/ai-stack-qdrant -- \
  curl -s -X POST "http://localhost:6333/collections/{collection}/points/delete" \
    -H "Content-Type: application/json" \
    -d '{"filter": {"must": [{"key": "user_id", "match": {"value": "USER_ID"}}]}}'
```

**Step 3: Delete uploaded documents**

Via Open WebUI Admin Panel → Documents, or:

```bash
kubectl exec -n ai-stack deploy/ai-stack-openwebui -- \
  rm -rf /app/backend/data/uploads/{user_id}/
```

**Step 4: Delete cross-conversation memories**

User self-service via Open WebUI Settings → Memories → Delete All, or admin
deletion via API.

**Step 5: Delete LangGraph checkpoints** (if enabled)

```bash
kubectl exec -n ai-stack deploy/ai-stack-postgres -- \
  psql -U langgraph -d langgraph -c \
    "DELETE FROM checkpoints WHERE metadata->>'user_id' = 'USER_ID';"
```

**Step 6: Delete user account**

Via Open WebUI Admin Panel → Users → Delete user.

**Step 7: Verify deletion**

- Confirm no data remains in Qdrant: scroll with user filter returns empty
- Confirm no conversations remain: user chats API returns empty
- Confirm user account is removed

**Note:** Telemetry data is PII-redacted at collection time and cannot be
attributed to specific users. No action needed for telemetry.

### Exceptions (Art. 17(3))

Erasure may be refused if processing is necessary for:
- (a) Freedom of expression and information
- (b) Legal obligation
- (c) Public health
- (d) Archiving in public interest
- (e) Legal claims

Document the exception and inform the data subject.

---

## 6. Right to Restriction (Art. 18)

When processing must be restricted (e.g., accuracy contested, processing
unlawful but subject opposes erasure):

1. Mark the user account as restricted in Open WebUI (disable login)
2. Do not delete data — store but do not process
3. Document the restriction and reason
4. Notify the data subject before lifting restriction

---

## 7. Right to Data Portability (Art. 20)

The data subject has the right to receive their data in a structured, commonly
used, machine-readable format.

### Export Format

Provide data as JSON:

```json
{
  "export_date": "2026-03-18T00:00:00Z",
  "user": {
    "id": "...",
    "name": "...",
    "email": "..."
  },
  "conversations": [
    {
      "id": "...",
      "created_at": "...",
      "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    }
  ],
  "documents": [
    {"id": "...", "filename": "...", "uploaded_at": "..."}
  ],
  "memories": [
    {"id": "...", "content": "...", "created_at": "..."}
  ]
}
```

### Procedure

1. Export all user data per §3 (Right of Access)
2. Package as JSON (structure above)
3. If requested, transmit directly to another controller (Art. 20(2))

---

## 8. Automated Decision-Making (Art. 22)

If the ai-stack is used to make decisions with legal or similarly significant
effects based solely on automated processing:

1. **Inform** the data subject about the automated decision-making (Art. 13(2)(f), Art. 14(2)(g))
2. **Provide** meaningful information about the logic involved
3. **Ensure** the right to:
   - Obtain human intervention
   - Express their point of view
   - Contest the decision

**Assessment:** Document whether your use case involves solely automated
decisions with legal/significant effects. If the platform is used as an
assistive tool with human review before any consequential action, Art. 22 is
not triggered.

---

## 9. Response Templates

### Acknowledgement

> Dear [Name],
>
> We acknowledge receipt of your data subject access request dated [date].
> Your request ID is [ID]. We will respond within one month.
>
> [DPO signature]

### Completion

> Dear [Name],
>
> Further to your request [ID] dated [date], please find enclosed [description
> of data / confirmation of deletion / etc.].
>
> If you have questions, contact our DPO at [email].
>
> [DPO signature]

### Refusal (with reasons)

> Dear [Name],
>
> We have reviewed your request [ID] dated [date]. We are unable to fulfil
> this request for the following reason: [exception under Art. 17(3) / identity
> not verified / manifestly unfounded or excessive (Art. 12(5))].
>
> You have the right to lodge a complaint with the Datenschutzbehörde
> (Austrian DPA) at [contact].
>
> [DPO signature]

---

*Template version: 2.0 | Based on GDPR Art. 12–22 and EDPB Guidelines on data subject rights.*
