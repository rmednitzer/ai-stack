# Remediation runbook

Operator-executable remediation plan for the ai-stack chart, produced from the
in-depth architecture review. It has two parts:

- **Part A — Executed in-chart**: the fail-closed Open WebUI HA guard, the
  corrected production database default, the CTL-003 execution isolation control,
  the opt-in-path Qdrant collection bootstrap, the POL-002 credential-management
  control, the upstream-validated application configuration tuning, and per-tenant
  RAG isolation with GDPR erasure. Each entry lists the exact verification command.
- **Part B — Deferred remediations**: real findings that are out of scope for one
  surgical change (opt-in code paths with no test home, cluster-level controls
  outside the chart, or larger reworks). Each entry states the finding, the
  evidence (`file:line`), severity, the fix design, ready-to-apply steps, how to
  validate, and how to roll back.

Decision record: [ADR-012](../architecture/ADR-012-ha-guard-execution-isolation-remediation-runbook.md).
Threat model: [SECURITY.md](../../SECURITY.md). Control registry:
[CONTROLS.md](../governance/CONTROLS.md). Known gaps: [LIMITATIONS.md](../../LIMITATIONS.md).

Conventions: ISO 8601 dates, 24h UTC, SI units. Run every change through the
validation gate in the Appendix before pushing. "Severity" is operational impact,
not a CVSS score.

---

## Part A — Executed in-chart

### A1. Open WebUI high-availability split-brain (production) — FIXED

**Severity:** high (production data integrity).

**Finding.** The production overlay disabled the database while running Open WebUI
at multiple replicas. `values.yaml` documents `postgres.enabled: true` as a core
dependency ("Open WebUI HA state (`DATABASE_URL`) … disable only for an ephemeral
single-pod lab", `values.yaml:1048`), but `values-prod.yaml` set
`postgres.enabled: false` with `openwebui.replicaCount: 2` + autoscaling to 5.
`ai-stack.webuiHaEnv` emits `DATABASE_URL` only when `postgres.enabled`
(`templates/_helpers.tpl`), so each replica fell back to a private per-pod SQLite
database and state (users, chats, settings) split across pods.

**Fix applied.**

1. `ai-stack.openwebuiHaGuard` (`templates/_helpers.tpl`), invoked at the top of
   `templates/openwebui/deployment.yaml`: refuses, at render time, a scaled Open
   WebUI (`openwebui.replicaCount > 1` or `openwebui.autoscaling.enabled`) when
   `postgres.enabled` is
   false. Emits nothing on success; does not trip the single-replica lab.
2. `values-prod.yaml`: `postgres.enabled: true` (the overlay already configures
   `mode: cnpg`, 3 instances, pooler, TLS `require`).
3. `.github/workflows/lint.yaml`: `Cluster,Pooler,ScheduledBackup` added to the
   `kubeconform -skip` lists, since the production profile now renders CNPG CRs.
4. `tests/openwebui_ha_test.yaml`: pins both the fail-closed paths and the
   positive `DATABASE_URL` wiring.

**Verify.**

```
# Guard catches the old broken topology:
helm template ai-stack . -f values.yaml -f values-prod.yaml --set postgres.enabled=false
#   => render fails with: "...without a shared PostgreSQL..."

# Production now wires the shared database:
helm template ai-stack . -f values.yaml -f values-prod.yaml \
  -s templates/openwebui/deployment.yaml | grep -c "name: DATABASE_URL"   # >= 1

helm unittest -f tests/openwebui_ha_test.yaml .
```

**Residual (see B1):** multi-node Open WebUI still needs RWX or S3 object storage
for uploaded-file durability; the shared database fixes account/chat state, not
the on-disk upload store.

### A2. Model-driven execution isolation not a traceable control — FIXED

**Severity:** medium (governance traceability).

**Finding.** Open Terminal (runs model-generated commands) and MCPO (brokers model
tool calls) already enforce isolation — opt-in hardened `runtimeClassName`, a CORS
allowlist that never resolves to `*`, a bounded root filesystem,
`automountServiceAccountToken: false`, default-deny egress — but none of it traced
to a control identifier.

**Fix applied.** `CTL-003` added to `docs/governance/CONTROLS.md` and the
`README.md` governance table; Open Terminal and MCPO reference it via
`ai-stack.governanceMap` (`CTL-002,CTL-003,POL-001`); `tests/governance_labels_test.yaml`
extended.

**Verify.**

```
helm template ai-stack . --set openTerminal.enabled=true,mcpo.enabled=true \
  | grep 'control-refs.*CTL-003'                 # both controller and pod
helm unittest -f tests/governance_labels_test.yaml .
```

### A3. Qdrant collection never created on the opt-in ingestion path — FIXED

**Severity:** medium (day-one failure of the opt-in ingestion-worker → Pydantic AI RAG path).

**Finding.** Nothing issued the `PUT /collections/<name>` that creates the Qdrant
collection the ingestion worker upserts into (`files/ingestion-worker/worker.py`)
and Pydantic AI queries (`files/pydanticai/app.py`), so the first upsert/query
returned 404. A latent bug compounded it: `process_task` resolved a per-task
`collection` but `upsert_vectors` ignored it and used the module-global
`COLLECTION_NAME`. (Open WebUI is unaffected — it manages its own collections.)

**Fix applied.** `ensure_qdrant_collection` creates the collection on first use,
taking the vector size from the **live embedding** (no hard-coded dimension, no
drift) with `Cosine` distance (nomic-embed-text, the chart default); it is
idempotent and tolerates a concurrent create by a peer worker (relevant under the
worker's autoscaling). `upsert_vectors` now takes the per-task `collection` and
writes points there. The producer-supplied collection name is validated against a
strict allowlist before it is interpolated into any Qdrant URL (no path, query, or
whitespace characters, mirroring the `file_url` hardening of ADR-009), and
confirmed-existing collections are memoised so repeated upserts skip the existence
check. First Python test harness for `files/`: `test_worker.py` + `conftest.py`
(respx-mocked HTTP, no backing services), run by the new `worker-tests` CI job.

**Verify.**

```
pip install -r files/ingestion-worker/requirements-dev.txt
python -m pytest files/ingestion-worker -q
ruff check files/ingestion-worker/
```

### A4. Credential management not a traceable policy (POL-002) — FIXED

**Severity:** medium (governance traceability).

**Finding.** The chart already manages every component credential through a
Kubernetes `Secret` — generated and kept stable across upgrades via
`ai-stack.persistentSecret`, overridable by an explicit value or an
`existingSecret`, with no hardcoded plaintext defaults and never rendered inline in
a workload manifest (`templates/common/secrets.yaml`) — but this discipline traced
to no policy identifier, so it could not be referenced from an annotation, a test,
or an audit.

**Fix applied.** `POL-002` (credential management) added to the registry
(`docs/governance/CONTROLS.md`) and the `README.md` governance table. It is
referenced via `ai-stack.governanceMap` by exactly the components the chart
provisions credentials for — Open WebUI, Authelia, MCPO, Open Terminal, Qdrant,
SearXNG, Valkey, PostgreSQL, LangGraph, Pydantic AI — and **not** the credential-less
components (Ollama, Tika, ingestion worker, OTel Collector), keeping the control
discriminating. `tests/governance_labels_test.yaml` pins the new value on each.

**Verify.**

```
helm unittest -f tests/governance_labels_test.yaml .
helm template ai-stack . -s templates/ollama/deployment.yaml | grep control-refs   # POL-002 absent
helm template ai-stack . -s templates/qdrant/deployment.yaml | grep control-refs   # POL-002 present
```

### A5. Application configuration tuning (B11) — FIXED

**Severity:** low (performance / durability). **Type:** config, validated against upstream docs.

**Finding.** Several known-good performance and durability settings were unset.

**Fix applied**, each validated against the upstream documentation:

- **Qdrant on-disk payload (default).** `QDRANT__STORAGE__ON_DISK_PAYLOAD: "true"`
  in `qdrant.env` keeps point payloads on disk rather than in RAM (Qdrant
  "Storage" guide). Payloads here are chunk text fetched only with results, so the
  latency cost is negligible and the RAM saving is material on a large corpus;
  vector search (in-memory HNSW) is unaffected. Applies to collections created
  while set; add a payload index before filtering on a payload field.
- **Ollama VRAM knobs (documented opt-in).** `OLLAMA_FLASH_ATTENTION` +
  `OLLAMA_KV_CACHE_TYPE` (`q8_0`) roughly halve KV-cache memory for long contexts
  (Ollama FAQ); KV quantization requires flash attention and is
  architecture-dependent, so they ship commented, not as a blanket default. A note
  warns **not** to drop `OLLAMA_MAX_LOADED_MODELS` below 2, since RAG keeps both
  the chat model and the embedder resident (the default 3×GPU already covers this).
- **Valkey persistence in prod.** `valkey.persistence.enabled: true` in
  `values-prod.yaml` so the Open WebUI session / websocket-manager and rate-limit
  state survive a Valkey restart (RDB on a PVC; Recreate strategy).

**Verify.**

```
helm unittest -f tests/config_tuning_test.yaml .
helm template ai-stack . -s templates/qdrant/deployment.yaml | grep ON_DISK_PAYLOAD
helm template ai-stack . -f values.yaml -f values-prod.yaml | grep -A3 "kind: PersistentVolumeClaim" | grep valkey
```

### A6. Per-tenant RAG isolation and GDPR erasure (B3) — FIXED

**Severity:** high for multi-tenant use of the opt-in ingestion → Pydantic AI path.

**Finding.** On that path retrieval queried the whole collection with no per-user
filter, and the payload carried no `user_id`/`tenant_id` — so there was nothing to
isolate on and **nothing to erase by**, making a GDPR Art. 17 erasure request a
no-op. (Open WebUI's own knowledge bases have their own per-user access controls;
this concerns only the custom path.)

**Fix applied.**

- **Attribution (ingestion worker).** When a producer tags a task with `user_id` /
  `tenant_id`, the worker validates them (lenient bound: ≤256 chars, no control
  characters — they travel in JSON, not a URL) and writes them, plus an ISO 8601
  `created_at`, into the Qdrant payload. Absent tags leave the payload unchanged.
  On collection creation it also builds **keyword payload indexes** on `user_id`
  and `tenant_id` so filtered reads/deletes do not scan on-disk payloads (the
  `on_disk_payload` default from A5).
- **Isolation (Pydantic AI).** `_qdrant_retrieve` takes the caller identity and
  adds a Qdrant `filter: {must: [...]}` matching `user_id` / `tenant_id` when set.
  Identity is threaded durable-safely via agent `deps` (`AgentDeps`,
  `RunContext`): `/run` reads `user_id`/`tenant_id` from the body; the
  OpenAI-compatible `/v1/chat/completions` reads the `X-User-Id` / `X-Tenant-Id`
  headers or the OpenAI `user` field. No identity = unfiltered (backward
  compatible). Covered by `files/pydanticai/test_app.py` (incl. an end-to-end
  `TestModel` run asserting deps reach the query filter), run by the new
  `pydanticai-tests` CI job.

**GDPR erasure (right to be forgotten).** With `user_id` in the payload and
indexed, erase one subject's points with a delete-by-filter (record it in the
data-subject-request log):

```bash
curl -sS -X POST "$QDRANT_URI/collections/$COLLECTION/points/delete" \
  -H "api-key: $QDRANT_API_KEY" -H 'content-type: application/json' \
  -d '{"filter":{"must":[{"key":"user_id","match":{"value":"<subject-id>"}}]}}'
```

**Verify.**

```
pip install -r files/ingestion-worker/requirements-dev.txt -r files/pydanticai/requirements-dev.txt
python -m pytest files/ingestion-worker files/pydanticai -q
```

**Operator note.** This delivers the mechanism; wiring Open WebUI (or your client)
to send the user/tenant on each call is deployment-specific. The identity is a
plain match value, so an unknown id simply returns no results (fail-safe).

---

### A7. Distributed Qdrant high availability (B8) — FIXED

**Severity:** low–medium for the single-node default; the gap is real only where
retrieval must survive a node loss.

**Finding.** Qdrant shipped as a single `Deployment` with one ReadWriteOnce PVC and
no replication: a node or pod loss interrupted retrieval, and recovery was from
backup, not failover (LIMITATIONS L7).

**Fix applied.** A gated cluster mode (`qdrant.cluster.enabled`, off by default,
[ADR-013](../architecture/ADR-013-distributed-qdrant-ha.md)). Off, the chart renders
exactly the prior single-node Deployment + PVC. On, it renders a StatefulSet of
`cluster.replicas` peers (default 3) running Raft consensus over the p2p port (6335)
behind a headless Service (`clusterIP: None`, `publishNotReadyAddresses: true`) for
peer discovery, with per-pod PVCs (`volumeClaimTemplates`) and soft anti-affinity to
spread peers across nodes. Bootstrap follows Qdrant's documented model (validated
against the upstream Helm chart): pod-0 forms the cluster (`--uri`), the rest join it
(`--bootstrap` pod-0 `--uri` self). Data HA additionally needs each collection
created with `replication_factor >= 2`; the ingestion worker does this automatically
when cluster mode is on (`QDRANT_REPLICATION_FACTOR` / `QDRANT_SHARD_NUMBER`, wired
from `qdrant.cluster.replicationFactor` / `shardNumber`). The p2p port is confined to
qdrant peers by the NetworkPolicy (ingress + egress on 6335) and never exposed on the
client Service; the existing `maxUnavailable: 1` PDB now protects the quorum. Asserted
in `tests/qdrant_cluster_test.yaml`; worker create-body coverage in
`files/ingestion-worker/test_worker.py`.

**Verify.**

```
helm template ai-stack . --set qdrant.cluster.enabled=true \
  | grep -E 'kind: (StatefulSet|Service)'   # StatefulSet + client + headless Service
helm unittest . -f 'tests/qdrant_cluster_test.yaml'
```

In a live cluster, deleting one Qdrant pod (with `replication_factor >= 2`) leaves
collections readable and writable; the pod rejoins and re-syncs on restart.

**Operator note.** Cluster mode is opt-in. Surviving a node loss needs the peers on
distinct nodes (the default anti-affinity is soft so small clusters still schedule;
pin nodes or harden it to a required rule for guaranteed HA) and collections with
`replication_factor >= 2`. Collections created outside the worker (e.g. Open WebUI
manages its own) must set their own replication at creation. **Rollback.** Set
`qdrant.cluster.enabled: false`.

---

### A8. Supply-chain and runtime enforcement (B4–B7) — FIXED / ADDRESSED

**Severity:** medium (supply chain) for B4/B5; low–medium (runtime) for B6/B7.

**Finding.** Four hardening gaps: the CVE gate was advisory-only (B4); images were
unsigned with no admission verification (B5); egress was port-level, not host-level
(B6); inter-component traffic was plaintext (B7).

**Fix applied.** Recorded in [ADR-014](../architecture/ADR-014-supply-chain-runtime-enforcement.md);
operator steps in the [hardening guide](hardening-guide.md).

- **B4 (FIXED, in CI).** `cve-scan` now fails on any critical CVE (`exit 1`),
  keeping the push-only cost design. The relief valve is a time-boxed
  [`.grype.yaml`](../../.grype.yaml) exception (advisory + `expires:` date),
  enforced by `.github/scripts/check_grype_exceptions.py` so an ignore cannot
  become permanent.
- **B5 (signing FIXED; admission ADDRESSED).** `release.yaml` cosign-keyless-signs
  the published chart OCI artifact (Sigstore Fulcio + Rekor, no key). Admission
  verification of workload images is operator-owned: an `Audit`-mode Kyverno
  example ([`examples/hardening/kyverno-verify-images.yaml`](../../examples/hardening/kyverno-verify-images.yaml))
  plus the mirror-and-sign pattern in the guide.
- **B6 (ADDRESSED).** A Cilium `toFQDNs` example
  ([`examples/hardening/cilium-fqdn-egress.yaml`](../../examples/hardening/cilium-fqdn-egress.yaml))
  narrows the open `:443`/`:80` egress to a host allowlist, on top of the chart's
  L3/L4 default-deny floor.
- **B7 (ADDRESSED).** Istio `PeerAuthentication` STRICT
  ([`examples/hardening/istio-peerauthentication.yaml`](../../examples/hardening/istio-peerauthentication.yaml))
  or Linkerd injection adds automatic mTLS over the per-component ServiceAccount
  identities.

**Verify.** `python3 .github/scripts/check_grype_exceptions.py` passes on an empty
exception list and fails on an expired/missing-expiry entry; a seeded critical CVE
fails `cve-scan`. cosign verification command in the guide. **Rollback.** Per item,
in the guide (warning-only tail; policy to `Audit`; remove the FQDN policy / mesh
label). **Tracking.** ADR-014; [SECURITY.md](../../SECURITY.md); this runbook.

---

## Part B — Deferred remediations

Ordered by recommended sequence. B2, B3, B4, and B8 are done (see A3, A6, A8, A7),
and B5–B7 are addressed as in-repo signing plus operator-owned examples + the
[hardening guide](hardening-guide.md) (they remain cluster-level controls outside
a single Helm chart).

### B1. Multi-node Open WebUI file durability

**Severity:** high (only when running multi-node HA). **Type:** chart + operator.

**Finding.** The Open WebUI data volume is one `ReadWriteOnce` PVC with a fixed
per-release `claimName` shared by all replicas (`templates/openwebui/deployment.yaml`
volume `data`; `values.yaml:483` `accessMode: ReadWriteOnce`). A second replica on
another node cannot attach it, and Open WebUI writes uploaded files to
`DATA_DIR/uploads` on local disk. A1 fixes account/chat state (Postgres); uploaded
files are still per-pod.

**Fix design (operator chooses one).**

- **Object storage (recommended).** Configure Open WebUI S3 file storage so
  uploads do not depend on the PVC. Set in `openwebui.env`: `STORAGE_PROVIDER: "s3"`
  and the `S3_*` variables (bucket, region, endpoint, credentials via an
  `existingSecret`). Keep the PVC small (cache only) or disable it. Pairs with an
  EU-region MinIO/S3 for sovereignty.
- **RWX volume.** Set `openwebui.persistence.accessMode: ReadWriteMany` with a
  storage class that supports it (CephFS, NFS, Longhorn-RWX). Simpler, but RWX
  performance and file-locking semantics vary by backend.

**Steps (S3 path).**

1. Provision an EU-region bucket and a scoped credential; create a Secret.
2. Add the `STORAGE_PROVIDER`/`S3_*` env to `openwebui.env`; reference the Secret.
3. Re-render and deploy; upload a file on one replica and confirm it is visible
   after the request is routed to another replica.

**Validate.** Pod logs show the S3 provider initialised; uploads survive a single
replica restart. **Rollback.** Remove the `S3_*`/`STORAGE_PROVIDER` env; Open WebUI
reverts to PVC/local storage. **Tracking.** [LIMITATIONS.md](../../LIMITATIONS.md)
L7; `docs/components/openwebui.md`.

### B2. Qdrant collection bootstrap (opt-in RAG path) — DONE

Implemented; see **A3**. The worker now creates the collection on first use
(vector size from the live embedding, `Cosine` distance, idempotent and
concurrent-create safe) and honours the per-task collection name, with the first
`files/` Python test harness (`test_worker.py`) wired into the `worker-tests` CI
job. **Tracking.** `docs/components/ingestion-worker-spec.md`.

### B3. Per-tenant retrieval isolation and GDPR erasure — DONE

Implemented; see **A6**. The ingestion worker now tags points with validated
`user_id` / `tenant_id` (+ `created_at`) and indexes them; Pydantic AI filters
retrieval by the caller identity (threaded via agent `deps`); and erasure is a
documented delete-by-filter. Covered by `files/pydanticai/test_app.py` and the
worker tests. **Tracking.** [SECURITY.md](../../SECURITY.md); `docs/components/pydanticai.md`.

### B4. Make the container CVE gate blocking — DONE

Implemented; see **A8** and [ADR-014](../architecture/ADR-014-supply-chain-runtime-enforcement.md).
`cve-scan` fails on any critical CVE, with a time-boxed [`.grype.yaml`](../../.grype.yaml)
exception path enforced by `.github/scripts/check_grype_exceptions.py`.

### B5. Image signing and admission verification — ADDRESSED

Chart signing implemented; admission documented. See **A8**, ADR-014, and the
[hardening guide](hardening-guide.md). `release.yaml` cosign-keyless-signs the
published chart; the operator-owned admission half ships as an `Audit`-mode Kyverno
example ([`examples/hardening/kyverno-verify-images.yaml`](../../examples/hardening/kyverno-verify-images.yaml)).
**Tracking.** [ADR-002](../architecture/ADR-002-image-digest-pinning.md); ADR-014.

### B6. FQDN-aware egress — ADDRESSED

Operator-owned example + guide; see **A8** and the
[hardening guide](hardening-guide.md). A Cilium `toFQDNs` example
([`examples/hardening/cilium-fqdn-egress.yaml`](../../examples/hardening/cilium-fqdn-egress.yaml))
narrows the open `:443`/`:80` egress to a host allowlist on top of the chart's
L3/L4 default-deny floor. **Tracking.** [SECURITY.md](../../SECURITY.md); CTL-002.

### B7. In-cluster mTLS — ADDRESSED

Operator-owned example + guide; see **A8** and the
[hardening guide](hardening-guide.md). Istio `PeerAuthentication` STRICT
([`examples/hardening/istio-peerauthentication.yaml`](../../examples/hardening/istio-peerauthentication.yaml))
or Linkerd injection adds automatic mTLS over the per-component ServiceAccount
identities. **Tracking.** [SECURITY.md](../../SECURITY.md).

### B8. Distributed Qdrant high availability — DONE

Implemented as a gated cluster mode; see **A7** and
[ADR-013](../architecture/ADR-013-distributed-qdrant-ha.md). Off by default (the
single-node Deployment is unchanged); `qdrant.cluster.enabled` renders a Raft
StatefulSet behind a headless Service, with the ingestion worker creating
collections at `replication_factor >= 2` so a node loss leaves retrieval available.

### B9. Disaster recovery: backups and snapshots

**Severity:** medium. **Type:** operator config + small chart addition.

**Finding.** CNPG backups are disabled by default (`values.yaml:1152`;
`values-prod.yaml` `cnpg.backup.enabled: false`), and there is no Qdrant snapshot
automation. A volume loss is unrecoverable.

**Fix design.**

- **PostgreSQL:** set `postgres.cnpg.backup.enabled: true` with a
  `barmanObjectStore` pointing at EU-region S3/MinIO (WAL archiving +
  scheduled base backups); confirm the retention policy. Test a restore.
- **Qdrant:** add a `CronJob` that calls the Qdrant snapshot API
  (`POST /collections/<name>/snapshots`) and ships the artifact to object storage,
  or snapshot the PVC via the CSI `VolumeSnapshot` API on a schedule.

**Validate.** A scheduled backup/snapshot appears in object storage; a restore into
a scratch namespace reproduces the data. **Rollback.** Disable the backup flag /
remove the CronJob. **Tracking.** `docs/components/postgres.md`; this runbook.

### B10. Credential management as a named policy (POL-002) — DONE

The governance half is implemented; see **A4**. POL-002 is in the registry and
annotated on every credential-bearing component. The remaining operator-side
recommendation stands: for regulated production, prefer the `existingSecret`
patterns backed by External Secrets Operator or Vault over the chart's generated
secrets (model-provider keys, MCPO / Open Terminal API keys, Qdrant API key, Valkey
AUTH, PostgreSQL). **Tracking.** [CONTROLS.md](../governance/CONTROLS.md); ADR-008
(Valkey AUTH).

### B11. Performance and operational tuning — DONE

Implemented; see **A5**. Validated against upstream docs and applied: Qdrant
on-disk payload as a default, Valkey prod persistence, and the Ollama VRAM knobs as
documented opt-in. Remaining deeper durability follow-up: layer **AOF**
(`appendonly`) on Valkey on top of RDB for ~1 s worst-case loss (Valkey persistence
docs) — needs a config-file launch path for the no-AUTH case, so it is left as a
follow-up rather than bundled here.

---

## Appendix — validation gate

Run before every push (mirrors `CLAUDE.md` and CI):

```
ruff check files/                       # when files/ change
helm lint . && helm lint . -f values.yaml -f values-prod.yaml
helm template ai-stack . >/dev/null
helm template ai-stack . -f values.yaml -f values-prod.yaml >/dev/null
helm template ai-stack . \
  --set openTerminal.enabled=true,mcpo.enabled=true \
  --set langgraph.enabled=true,pydanticai.enabled=true,postgres.enabled=true,ingestionWorker.enabled=true \
  --set authelia.enabled=true,global.otel.enabled=true >/dev/null
helm unittest .
python3 .github/scripts/check_md_links.py    # when docs change
```

Any security-relevant template change carries a `tests/` assertion. Image or
version changes sync `values.yaml` ↔ `sbom.cdx.json` ↔ `zarf.yaml` in the same
change (ADR-001/002); a `Chart.yaml` bump triggers the `AGENTS.md` §6 checklist.

## Rollback (Part A)

Part A is template logic, values, governance metadata, tests, and docs — no image,
data, or `Chart.yaml` change. Reverting the change restores prior behaviour with no
migration. The HA guard and CTL-003 add no rendered fields; `postgres.enabled: true`
in production reflects the documented default and the overlay's existing `cnpg`
configuration.
