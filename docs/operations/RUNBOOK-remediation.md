# Remediation runbook

Operator-executable remediation plan for the ai-stack chart, produced from the
in-depth architecture review. It has two parts:

- **Part A — Executed in-chart**: the fail-closed Open WebUI HA guard, the
  corrected production database default, the CTL-003 execution isolation control,
  and the opt-in-path Qdrant collection bootstrap. Each entry lists the exact
  verification command.
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

---

## Part B — Deferred remediations

Ordered by recommended sequence. B2 is done (see A3); B3 applies only when the
opt-in ingestion-worker → Pydantic AI retrieval path is enabled; B5–B8 are
cluster-level controls outside a single Helm chart.

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

### B3. Per-tenant retrieval isolation and GDPR erasure (opt-in RAG corpus)

**Severity:** high (only for multi-tenant use of the opt-in path). **Type:**
in-app code + procedure.

**Finding.** On the custom ingestion → Pydantic AI path, `_qdrant_retrieve`
queries the whole collection with no per-user filter
(`files/pydanticai/app.py:163-178`), and the worker payload carries no
`user_id`/`tenant_id` (`files/ingestion-worker/worker.py:632-638`). There is no
identity to filter on and no key to erase by, so a GDPR Art. 17 erasure request
against this corpus is a no-op. (Open WebUI's own knowledge bases have their own
per-user access controls; this concerns only the custom path.)

**Fix design.**

1. Ingestion API includes `user_id`/`tenant_id` (and `created_at`) in the stream
   fields; the worker propagates them into the Qdrant payload (the payload already
   merges arbitrary metadata, so this is additive).
2. `_qdrant_retrieve` adds a Qdrant `filter` on the caller's `user_id`/`tenant_id`.
3. Erasure procedure: `POST /collections/<name>/points/delete` with a
   `filter: { must: [{ key: "user_id", match: { value: <id> }}]}`, recorded in the
   data-subject-request log.

**Validate.** Two users' documents are retrievable only by their owner; a
delete-by-filter removes exactly one user's points. **Rollback.** The filter is
additive; removing it restores unfiltered behaviour. **Tracking.**
[SECURITY.md](../../SECURITY.md); `docs/components/pydanticai.md`.

### B4. Make the container CVE gate blocking

**Severity:** medium (supply chain). **Type:** CI.

**Finding.** `cve-scan` runs Grype with `--fail-on critical` per image but captures
the exit code into a `::warning::` and never fails the step
(`.github/workflows/lint.yaml:561-573`), and runs on `push` only
(`lint.yaml:504`) by deliberate cost/rate-limit design. Critical CVEs are visible
in artifacts but do not block.

**Fix options (tradeoff).**

- **(a) Fail on push (low cost).** Track a `CRITICAL` count and `exit 1` at the end
  of the scan step. Signal arrives post-merge on `main` (red main), not pre-merge.
- **(b) Gate on PRs (higher cost).** Add a PR-triggered scan limited to images that
  changed in the PR diff, to bound pull cost and rate limits. Strongest gate.

**Ready patch (option a).** Replace the trailing summary with:

```bash
echo "=== CVE Scan Summary: ${TOTAL} images scanned, ${CRITICAL} with critical CVEs ==="
if [ "$CRITICAL" -gt 0 ]; then
  echo "::error::${CRITICAL} image(s) have critical CVEs"; exit 1
fi
```

Pair with a documented, time-boxed exception path (a Grype ignore file with an
expiry and a linked advisory) so an unfixable upstream CVE does not wedge releases.

**Validate.** A seeded critical CVE fails the job; a clean scan passes. **Rollback.**
Restore the warning-only tail. **Tracking.** `AGENTS.md` (CI), this runbook.

### B5. Image signing and admission verification

**Severity:** medium (supply chain). **Type:** release + cluster policy
(out-of-chart).

**Finding.** Images are digest-pinned and SBOM-attested with parity enforced in CI,
but are not cryptographically signed, and nothing verifies signatures at admission.

**Fix design.** Sign release images with cosign (keyless/OIDC) in the release
workflow; enforce with a cluster admission policy (Kyverno `verifyImages` or the
sigstore policy-controller) scoped to the ai-stack namespace, requiring a valid
signature and optionally an SBOM/SLSA attestation. Keep it out of the chart: it is
a cluster-wide control an operator owns.

**Validate.** An unsigned or tampered image is rejected at admission; the signed
release set admits. **Rollback.** Set the policy to `audit` before `enforce`.
**Tracking.** `SECURITY.md`; [ADR-002](../architecture/ADR-002-image-digest-pinning.md).

### B6. FQDN-aware egress

**Severity:** medium. **Type:** cluster networking (out-of-chart).

**Finding.** NetworkPolicies are default-deny with explicit allows, but the
internet egress rules open `:443`/`:80` to any destination (e.g. the LangGraph and
Pydantic AI egress blocks in `templates/common/networkpolicies.yaml`, and the
SearXNG search path). Native `NetworkPolicy` cannot express destination FQDNs, so a
persuaded workload can reach arbitrary external hosts on those ports.

**Fix design.** Layer an FQDN/DNS-aware egress control: Cilium
`CiliumNetworkPolicy` `toFQDNs`, or an egress gateway / mesh
`ServiceEntry`+`Sidecar` allowlist (PyPI, the configured model providers, the
search engines SearXNG queries). Keep the chart's L3/L4 default-deny as the floor.

**Validate.** Egress to an allow-listed FQDN succeeds; egress to an unlisted host on
`:443` is denied. **Rollback.** Remove the FQDN policy; the chart's port-level
default-deny remains. **Tracking.** [SECURITY.md](../../SECURITY.md); CTL-002.

### B7. In-cluster mTLS

**Severity:** low–medium. **Type:** cluster mesh (out-of-chart).

**Finding.** Inter-component traffic is plaintext over ClusterIP; NetworkPolicy
governs reachability, not encryption or workload identity.

**Fix design.** Adopt a mesh providing automatic mTLS (Linkerd, or Istio ambient).
The chart's per-component ServiceAccounts give the mesh stable identities. Treat as
a platform capability, not a chart feature.

**Validate.** Traffic between components is encrypted and peer-authenticated (mesh
dashboard / `linkerd viz`). **Rollback.** Remove the mesh injection annotation.
**Tracking.** `SECURITY.md`.

### B8. Distributed Qdrant high availability

**Severity:** low–medium. **Type:** larger chart rework.

**Finding.** Qdrant is a single `Deployment` with one RWO PVC and no replication
(`templates/qdrant/deployment.yaml`; `values.yaml:566`). A node/pod failure
interrupts retrieval; recovery is from snapshot.

**Fix design.** Offer a Qdrant cluster mode (StatefulSet, ≥3 nodes, replication
factor ≥2, headless service for peer discovery), gated behind a values flag and
defaulting to the current single node. Significant rework; size it as its own
change with its own ADR.

**Validate.** Killing one Qdrant node leaves collections readable/writable.
**Rollback.** Flag back to single-node. **Tracking.** [LIMITATIONS.md](../../LIMITATIONS.md)
L7.

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

### B10. Secret management hardening and POL-002

**Severity:** low–medium. **Type:** operator config + governance.

**Finding.** Secrets are auto-generated via `ai-stack.persistentSecret` (a `lookup`
that regenerates under `helm template`/GitOps dry-run). Good for a self-contained
deploy; for regulated production, externalise to a managed store. There is no named
policy for credential management.

**Fix design.** Document and prefer the `existingSecret` patterns backed by External
Secrets Operator or Vault for every credential (model-provider keys, MCPO/Open
Terminal API keys, Qdrant API key, Valkey AUTH, Postgres). Formalise **POL-002
(credential management)** in [CONTROLS.md](../governance/CONTROLS.md) and reference
it from the secret-bearing components in `ai-stack.governanceMap` (update
`tests/governance_labels_test.yaml` in the same change).

**Validate.** No generated Secret is required when `existingSecret` is set; the
governance test pins the new `control-refs`. **Rollback.** Governance metadata is
additive. **Tracking.** [CONTROLS.md](../governance/CONTROLS.md); ADR-008 (Valkey AUTH).

### B11. Performance and operational tuning (recommendations)

**Severity:** low. **Type:** opt-in knobs (not default changes).

These change runtime defaults or are environment-specific, so they are
recommendations, not chart defaults (the chart does not weaken or second-guess a
default without cause):

- **Qdrant memory:** set `QDRANT__STORAGE__ON_DISK_PAYLOAD: "true"` in `qdrant.env`
  to keep payloads on disk; trades a little latency for materially lower RAM on
  large corpora.
- **Ollama GPU memory:** tune `OLLAMA_KEEP_ALIVE` and set
  `OLLAMA_MAX_LOADED_MODELS` to bound concurrent model residency on a single GPU
  and avoid OOM; the right value depends on VRAM and model mix.
- **Valkey durability in prod:** if Valkey holds session/websocket and rate-limit
  state you want to survive a restart, enable `valkey.persistence` in
  `values-prod.yaml`; otherwise a restart is a cold cache (not data loss, given
  Postgres holds durable state).

**Validate.** Re-render and confirm the env/persistence is present; observe the
resource effect. **Rollback.** Remove the knob. **Tracking.** per-component docs.

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
