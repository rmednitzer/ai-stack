# Changelog

All notable changes to the ai-stack Helm chart will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **`lint.yaml` now runs on every pull request and ends in a requireable
  `ci-success` aggregate (infra BACKLOG F13).** This was the only repository in
  the fleet with no required status check, and the reason was structural: every
  PR-triggered workflow carried a `paths` filter, so no check was guaranteed to
  report, and a check that never reports cannot be required. Combined with
  repository-level `allow_auto_merge`, that meant an ordinary pull request could
  be auto-merged with no validation having run at all.

  The path filter moved off the `on:` trigger into a new cheap `changes` job
  (checkout plus one `git diff`, plain git rather than a third-party
  paths-filter action, since every action here is digest-pinned and reviewed).
  The nine chart-validation jobs are now gated on `needs.changes.outputs.chart`,
  so a docs-only pull request costs one job instead of eleven and chart pull
  requests behave exactly as before: the regex reproduces the previous path list
  entry for entry. The filter fails safe toward running everything if the base
  commit is unavailable.

  `ci-success` runs with `if: always()` over all twelve jobs and fails when any
  dependency is anything other than `success` or `skipped`. It is deliberately
  **not** a trivial always-green job: one of those would give native auto-merge
  something to wait on while going green in seconds regardless of the diff,
  which converts the gap into the appearance of a gate rather than closing it.

  `renovate.json5` keeps `platformAutomerge: false` for now. It is only safe to
  drop once `ci-success` is actually added to the `main-protection` ruleset
  (id 15857143), which is a repository-settings change outside this PR; the
  comment there records the sequencing. No template, no image, no chart-version
  change.

### Added

- **`NOTICE` file, closing the Apache-2.0 paperwork gap.** The repository shipped
  `LICENSE` without the companion `NOTICE` that the rest of the fleet carries. It
  states what the Apache grant actually covers (chart templates, values, helpers,
  tests, Zarf definition, ArgoCD manifests, docs, CI tooling; no vendored
  third-party source), and draws the distinction that matters for a deployment
  chart: images are **referenced by immutable digest, not redistributed**, so each
  remains under its own license and the Apache grant does not extend to them.
  It points at `sbom.cdx.json` and `docs/compliance/LICENSE_COMPLIANCE.md` as the
  source of truth rather than restating the per-image list, since a hand-copied
  second inventory is precisely what drifts. The two non-permissive components
  (SearXNG AGPL-3.0-or-later, enabled by default; LangGraph Server ELv2, opt-in)
  are named inline so a reader of `NOTICE` alone is not misled. No template, no
  image, no chart-version change.

- **Ollama runtime model-pull egress is now gateable
  ([ADR-019](docs/architecture/ADR-019-ollama-model-pull-egress.md); audit backlog
  D-1 / posture A-8).** New opt-out `ollama.allowModelPullEgress` (**default
  `true`**, behaviour-preserving) gates the Ollama `:443` egress rule — the one
  outbound connection Ollama needs, for `ollama pull` from `registry.ollama.ai`.
  Set `false` in regulated / air-gapped clusters with pre-pulled models: the
  egress rule is dropped and the namespace default-deny isolates Ollama to DNS
  only. This is the L3/L4 *close* alternative to the B6 FQDN *narrow* layer.
  Asserted both ways in `tests/networkpolicy_test.yaml`; documented in
  `docs/components/ollama.md` and the hardening guide. No image or chart-version
  change.

- **ServiceMonitor coverage completed for every metrics-exposing component
  (audit backlog D-3 / R9).** Added a LangGraph `ServiceMonitor` (the server
  exposes Prometheus `/metrics` on its API port by default) and an **opt-in**
  Authelia exporter + `ServiceMonitor` (`authelia.metrics.enabled`, default
  `false` — Authelia ships its `:9959` `/metrics` exporter disabled). The
  `servicemonitors.yaml` header now records the full coverage matrix: Tika,
  SearXNG, Valkey, MCPO, Open Terminal, and non-CNPG Postgres expose no native
  Prometheus endpoint (intentionally uncovered); CNPG self-monitors via its
  operator PodMonitor. New `tests/servicemonitor_test.yaml`. No image or
  chart-version change.

- **Full deployment wired into Open WebUI — corrected env wiring, `values-full.yaml`,
  and a full-deployment guide
  ([ADR-015](docs/architecture/ADR-015-openwebui-wiring-full-deployment.md);
  [guide](docs/operations/full-deployment.md)).** Fixes Open WebUI environment
  variables that the pinned image (v0.9.6) no longer reads — validated against
  `open-webui` `config.py` — and which were therefore **silently ignored**:
  web search (`RAG_WEB_SEARCH_ENGINE` → `WEB_SEARCH_ENGINE`, plus the missing
  `ENABLE_WEB_SEARCH`), chunking (`RAG_CHUNK_SIZE`/`RAG_CHUNK_OVERLAP` →
  `CHUNK_SIZE`/`CHUNK_OVERLAP`), the upload cap (`MAX_UPLOAD_SIZE` bytes →
  `FILE_MAX_SIZE` **megabytes**, `50`), and the **AI Act Art. 50(1) transparency
  banner** (`WEBUI_BANNER_TEXT`/`_DISMISSIBLE` → `WEBUI_BANNERS` JSON — the
  disclosure had never rendered). The worker's own `RAG_CHUNK_SIZE`/`_OVERLAP`
  (a separate contract) are unchanged. New `values-full.yaml` overlay enables the
  optional plane and wires the **ingestion worker → Pydantic AI agent → Open
  WebUI** RAG path (the agent's `search_knowledge_base` tool reads the same
  `documents` collection the worker writes; `exposeToOpenWebUI` surfaces it as a
  model), turns SearXNG web search on (off in base — attacker-influenced content),
  and enables the observability pipeline. MCPO tool-server wiring stays a
  documented admin-UI step (its key is inline in `TOOL_SERVER_CONNECTIONS`, so the
  chart will not bake it into a pod manifest — POL-002). Asserted in
  `tests/openwebui_wiring_test.yaml`; all affected docs updated. No image or
  chart-version change.

- **Supply-chain and runtime enforcement — blocking CVE gate, chart signing, and
  operator hardening examples
  ([ADR-014](docs/architecture/ADR-014-supply-chain-runtime-enforcement.md);
  [runbook](docs/operations/RUNBOOK-remediation.md) A8;
  [hardening guide](docs/operations/hardening-guide.md)).** The `cve-scan` CI job
  is now **blocking** — a critical CVE in any referenced image fails the build
  (B4), keeping the push-only cost design. The relief valve is a time-boxed
  `.grype.yaml` exception (linked advisory + `expires:` date), enforced by
  `.github/scripts/check_grype_exceptions.py` so an ignore cannot silently become
  permanent. The release workflow **cosign-keyless-signs** the published Helm
  chart OCI artifact (Sigstore Fulcio + Rekor, no key to manage) (B5). The
  operator-owned controls ship as adaptable examples under `examples/hardening/`
  with a guide: a Kyverno `verifyImages` admission policy (B5 admission, `Audit`
  by default), a Cilium `toFQDNs` egress allowlist (B6), and Istio
  `PeerAuthentication` / Linkerd mTLS (B7) — layered on the chart's secure-by-
  default floor, never bundled into it. No image or chart-version change.

- **Distributed Qdrant high availability — gated cluster mode
  ([ADR-013](docs/architecture/ADR-013-distributed-qdrant-ha.md);
  [runbook](docs/operations/RUNBOOK-remediation.md) A7).** New `qdrant.cluster`
  block, **off by default** (the single-node Deployment + PVC render unchanged).
  When `qdrant.cluster.enabled`, Qdrant becomes a StatefulSet of `replicas` peers
  (default 3) running Raft consensus over the p2p port (6335) behind a headless
  Service (`clusterIP: None`, `publishNotReadyAddresses: true`) for peer
  discovery, with per-pod PVCs (`volumeClaimTemplates`) and soft anti-affinity;
  bootstrap follows Qdrant's documented model (pod-0 forms the cluster, the rest
  join via pod-0), validated against the upstream Helm chart. Data HA is wired
  end to end: the ingestion worker creates collections with
  `replication_factor >= 2` (`QDRANT_REPLICATION_FACTOR` / `QDRANT_SHARD_NUMBER`,
  set automatically from `qdrant.cluster.replicationFactor` / `shardNumber`). The
  p2p port is confined to qdrant peers by the NetworkPolicy and never exposed on
  the shared client Service; the existing `maxUnavailable: 1` PDB protects the
  quorum. Asserted in `tests/qdrant_cluster_test.yaml`, with worker create-body
  coverage in `files/ingestion-worker/test_worker.py`. No image or chart-version
  change.

- **Per-tenant RAG isolation and GDPR erasure on the opt-in ingestion path
  ([runbook](docs/operations/RUNBOOK-remediation.md) A6).** The ingestion worker
  now tags Qdrant points with validated `user_id` / `tenant_id` (+ ISO 8601
  `created_at`) and builds keyword payload indexes on them; Pydantic AI scopes
  retrieval to the caller identity via a Qdrant `filter`, threaded durable-safely
  through agent `deps` (`/run` body fields; `X-User-Id` / `X-Tenant-Id` headers or
  the OpenAI `user` field on `/v1/chat/completions`). Absent identity = unfiltered
  (backward compatible). Right-to-erasure becomes a documented delete-by-filter
  keyed on `user_id`. Adds a Pydantic AI test harness (`files/pydanticai/test_app.py`,
  incl. an end-to-end `TestModel` check that deps reach the query filter) and a
  `pydanticai-tests` CI job; the worker tests cover the payload tags + indexes.
  No image or chart-version change.

- **Application configuration tuning, validated against upstream docs
  ([runbook](docs/operations/RUNBOOK-remediation.md) A5).** Qdrant now stores point
  payloads on disk by default (`QDRANT__STORAGE__ON_DISK_PAYLOAD: "true"`) — lower
  RAM on large corpora at negligible RAG latency (Qdrant "Storage" guide; add a
  payload index before filtering on a payload field). Ollama gains documented
  opt-in VRAM knobs (`OLLAMA_FLASH_ATTENTION` + `OLLAMA_KV_CACHE_TYPE: q8_0`, which
  roughly halve KV-cache memory; KV quantization needs flash attention and is
  architecture-dependent, so they ship commented), with a guard note never to set
  `OLLAMA_MAX_LOADED_MODELS` below 2 (RAG keeps the chat model and the embedder
  resident). The production overlay enables `valkey.persistence` so session /
  websocket-manager and rate-limit state survive a Valkey restart. Asserted in
  `tests/config_tuning_test.yaml`. No image or chart-version change.

- **POL-002 — credential management as a traceable governance policy
  ([runbook](docs/operations/RUNBOOK-remediation.md) A4).** The chart already
  delivers every component credential through a generated-and-persisted Kubernetes
  `Secret` (`ai-stack.persistentSecret`) with no hardcoded plaintext defaults and
  never baked into an image, overridable by an explicit value or `existingSecret` —
  but this traced to no policy identifier. `POL-002`
  is added to `docs/governance/CONTROLS.md` and the `README.md` governance table,
  and referenced via `ai-stack.governanceMap` by exactly the credential-bearing
  components (Open WebUI, Authelia, MCPO, Open Terminal, Qdrant, SearXNG, Valkey,
  PostgreSQL, LangGraph, Pydantic AI) and not the credential-less ones (Ollama,
  Tika, ingestion worker, OTel Collector), so the control stays discriminating.
  Asserted in `tests/governance_labels_test.yaml`. No image or chart-version change.

- **Fail-closed Open WebUI HA guard, CTL-003 execution-isolation control, and a
  remediation runbook ([ADR-012](docs/architecture/ADR-012-ha-guard-execution-isolation-remediation-runbook.md)).**
  `ai-stack.openwebuiHaGuard` refuses, at render time, a scaled Open WebUI
  (`openwebui.replicaCount > 1` or `openwebui.autoscaling.enabled`) when `postgres.enabled`
  is false — the topology that silently splits state across per-pod SQLite
  databases — with a message that names the fix. It emits nothing on success and
  does not trip the single-replica ephemeral lab. New control **CTL-003**
  (model-driven execution isolation) is added to the registry and the `README.md`
  governance table; Open Terminal and MCPO reference it
  (`CTL-002,CTL-003,POL-001`) through `ai-stack.governanceMap`. The new
  [remediation runbook](docs/operations/RUNBOOK-remediation.md) records these
  fixes and the deferred items (multi-node file storage, the opt-in Qdrant
  collection bootstrap, per-tenant retrieval isolation/erasure, a blocking CVE
  gate, image signing/admission, FQDN egress, distributed Qdrant, DR backups)
  with operator steps. Asserted in `tests/openwebui_ha_test.yaml` and
  `tests/governance_labels_test.yaml`. No image or chart-version change.

- **Opt-in hybrid retrieval + cross-encoder reranking for RAG
  ([ADR-011](docs/architecture/ADR-011-rag-retrieval-quality.md)).** New Open
  WebUI knobs in `openwebui.env` — `ENABLE_RAG_HYBRID_SEARCH`,
  `RAG_RERANKING_MODEL`, `RAG_RERANKING_ENGINE`, `RAG_TOP_K_RERANKER`, and
  `RAG_HYBRID_BM25_WEIGHT` — add a BM25 lexical leg fused with the dense-vector
  results plus a CrossEncoder reranking stage. **OFF by default:** the reranking
  model is fetched from Hugging Face at runtime, which needs egress the
  default-deny NetworkPolicy does not grant, so enabling it is a conscious opt-in
  (allow egress or pre-stage the model). Recommended rerankers are small and
  Apache-2.0 (see [LICENSE_COMPLIANCE.md](docs/compliance/LICENSE_COMPLIANCE.md)).
  Asserted in `tests/rag_retrieval_test.yaml`. No image or chart-version change.

### Changed

- **Useful defaults for the agentic workloads — bounded runs, temperature, prompt,
  recursion limit ([ADR-018](docs/architecture/ADR-018-agent-workload-defaults.md)).**
  Validated against pydantic-ai 1.106 and `langchain-ai/langgraph`:
  - **Bounded Pydantic AI runs.** Every run/stream is now capped via pydantic-ai
    `UsageLimits` (forwarded through `DBOSAgent` for durable runs): `AGENT_REQUEST_LIMIT`
    (default `12`, the tool-loop bound vs pydantic-ai's implicit `50`),
    `AGENT_TOOL_CALLS_LIMIT` (default `8`), and an opt-in `AGENT_TOTAL_TOKENS_LIMIT`
    (empty = unbounded, so long answers are not truncated). Previously the agent ran
    with no token/tool-call ceiling — a runaway-loop footgun on local inference.
    Hitting a limit returns a clean notice (`finish_reason: length`), not a 5xx.
  - **Low default temperature.** `AGENT_TEMPERATURE` (default `0.2`) applied as the
    agent's `model_settings`; empty = the provider default.
  - **Grounded, tool-aware, AI-transparent default prompt.** `AGENT_SYSTEM_PROMPT`
    now steers tool use, grounding, admitting uncertainty, and AI disclosure (Art. 50).
  - **LangGraph recursion bound.** `LANGGRAPH_DEFAULT_RECURSION_LIMIT=25` (LangGraph's
    own conventional default) replaces the `langgraph-server` image's effectively
    unbounded `10007`; model/temperature/prompt/usage-limits live in the operator's
    graph (documented for parity, not invented as server env).
  All env-overridable; both workloads stay opt-in. New `tests/agent_defaults_test.yaml`
  + Python unit tests in `files/pydanticai/test_app.py`. No image or chart-version change.

- **Production overlay enables the shared database
  ([ADR-012](docs/architecture/ADR-012-ha-guard-execution-isolation-remediation-runbook.md)).**
  `values-prod.yaml` now sets `postgres.enabled: true`, restoring the documented
  core dependency the overlay had disabled while running Open WebUI at 2–5
  replicas. The overlay already configures `postgres.mode: cnpg` (3 instances,
  pooler, TLS `require`), so this enables the HA PostgreSQL it was built for; the
  CloudNativePG operator (v1.25+) is now a load-bearing prerequisite of the
  shipped production profile. Because the prod profile now renders
  `postgresql.cnpg.io/v1` `Cluster`/`Pooler`, those CR kinds were added to the
  `kubeconform -skip` lists in `.github/workflows/lint.yaml` (matching the chart's
  practice for operator-owned CRDs). No image or chart-version change.

- **Embedding task-instruction prefixes now applied by default
  ([ADR-011](docs/architecture/ADR-011-rag-retrieval-quality.md)).**
  `nomic-embed-text` (the chart's default embedder) is instruction-tuned and
  requires `search_query: ` on queries and `search_document: ` on passages; the
  stack previously embedded raw text on every surface, a silent
  retrieval-quality regression. New `RAG_EMBEDDING_QUERY_PREFIX` /
  `RAG_EMBEDDING_CONTENT_PREFIX` knobs (Open WebUI, the ingestion worker, and
  Pydantic AI) default to the correct nomic prefixes; the in-repo apps prefix
  only the embedding input, leaving the stored Qdrant payload text unchanged.
  The ingestion worker's `RAG_CHUNK_OVERLAP` code default was aligned to the
  chart value (`150`). **Upgrade note:** changing the prefixes changes the
  embedding space — **re-index existing collections / Open WebUI knowledge**
  after upgrading so queries match the stored vectors (greenfield deployments are
  correct immediately).

- **Consolidated dependency automation on Renovate — `.github/dependabot.yml`
  retired ([ADR-010](docs/architecture/ADR-010-consolidate-dependency-automation-on-renovate.md)).**
  Renovate's `github-actions`, `dockerfile`, and `pip-compile` managers now own
  what Dependabot previously did, alongside the existing `helm-values` manager,
  so all dependency automation lives in one config (`renovate.json5`). The
  `uv`-compiled `files/pydanticai/` and `files/ingestion-worker/` locks stay
  universal and fully hashed: Renovate replays the recorded
  `uv pip compile --universal --generate-hashes` command. `pydanticai`'s lock
  header was normalised to `uv`'s standard autogenerated form so the
  `pip-compile` manager detects it (pins and hashes unchanged). Supersedes the
  two-manager split in ADR-001 §3 and the Dependabot `pip` mechanism that
  AUDIT-2026-06 R7 recommended (the hashed-lock intent is preserved).
  GitHub-native Dependabot **security** alerts are independent of
  `dependabot.yml` and remain available. Governance docs (`SECURITY.md`,
  `README.md`, `EU_COMPLIANCE_CHECK.md`, `LICENSE_COMPLIANCE.md`,
  `EU_OPERATIONS_GUIDE.md`, `ENTERPRISE_EVALUATION.md`) updated to match
  (ADR-001 §2 docs-as-code). No chart template, `values.yaml`, SBOM, or Zarf
  change.

### Fixed

- **Open WebUI per-file upload cap is now actually enforced (fourth audit, Q-1 —
  High).** `openwebui.env.FILE_MAX_SIZE: "50"` was inert: open-webui v0.9.6 reads
  the cap from **`RAG_FILE_MAX_SIZE`** (`os.getenv` in `config.py`) and only stores
  it on the internal `app.state.config.FILE_MAX_SIZE` attribute, so the 50 MB limit
  silently never applied (defaulting to unlimited) — an unbounded-upload surface on
  the attacker-influenced RAG path. Renamed the env key to `RAG_FILE_MAX_SIZE` (the
  value and MB semantics are unchanged) and added a `notContains FILE_MAX_SIZE`
  regression assertion; corrected [ADR-015](docs/architecture/ADR-015-openwebui-wiring-full-deployment.md)
  (with a dated correction note) and the values comment. Verified against the
  v0.9.6 source. No image or chart-version change.

- **MCPO becomes Ready again (fourth audit, Q-2 — High, opt-in).** The earlier F-1
  fix moved MCPO's liveness/readiness probes to `/openapi.json` but left the
  `startupProbe` hardcoded to `GET /`. MCPO's FastAPI returns 404 on `/`, so the
  startupProbe failed all 20 attempts (~100 s) → CrashLoopBackOff and the
  liveness/readiness probes never activated. Pointed the startupProbe at
  `/openapi.json` and added a startupProbe-path assertion to `tests/mcpo_test.yaml`.
  Affects only `mcpo.enabled=true`. No image or chart-version change.

- **SBOM open-webui license corrected (fourth audit, Q-3).** `sbom.cdx.json`
  recorded open-webui as `MIT`, contradicting `LICENSE_COMPLIANCE.md` (the custom
  *Open WebUI License* — BSD-3 + branding, "not MIT") and the 2.12.0 CHANGELOG. The
  image-parity CI checks tag/digest only, so it could not catch the license slip.
  Switched to the CycloneDX custom-license form (`name` + `url`). No image or
  chart-version change.

- **Documentation accuracy sweep (fourth audit, Q-4/Q-5).** Finished the T-1
  read-only-rootfs correction across the four files it missed (`SECURITY.md`,
  `ENTERPRISE_EVALUATION.md`, `docs/components/tika.md`, `docs/components/searxng.md`,
  plus the `DPIA_TEMPLATE.md` "Most components" cell) — Tika and SearXNG render a
  *writable* rootfs; the read-only set is Qdrant, Valkey, OTel Collector, ingestion
  worker, Pydantic AI. Fixed `HOWTO.md` §4.4, which wrongly stated web search is
  "enabled by default" (it ships off — web content is attacker-influenced).
  Documented the ServiceMonitor/default-deny interaction in `docs/components/otel.md`
  and on the `serviceMonitor` toggle (audit posture A-9), and linked the ADRs +
  audit snapshots from `REFERENCE.md`. No image or chart-version change.

- **Pydantic AI reference app uses the current instrumentation API (audit
  backlog D-2).** `files/pydanticai/app.py` built the agent with
  `Agent(instrument=…)`, deprecated since pydantic-ai 1.106 (the pinned version)
  and removed in 2.0 — it emitted a `PydanticAIDeprecationWarning` on every
  startup. Switched to `capabilities=[Instrumentation()] if _OTEL else []`
  (verified warning-free on the shipped `pydantic-ai-slim==1.106.0`; no
  dependency bump needed). A new subprocess test promotes the warning to an error
  so a revert is caught (the prior suite only *warned*). No image or
  chart-version change.

- **Audit 2026-06-14 — corrected a false read-only-rootfs claim and closed two
  test-coverage gaps
  ([AUDIT-2026-06.md](docs/audit/AUDIT-2026-06.md) third pass).** The README,
  `SECURITY_BASELINE.md` (B2), and `.kube-linter.yaml` "read-only root filesystem"
  lists claimed Tika and SearXNG (both render `readOnlyRootFilesystem: false`) and
  omitted the ingestion worker and Pydantic AI (both `true`) — corrected to the
  rendered reality. Added a `runAsNonRoot: true` regression guard for the
  non-excepted workloads (kube-linter excludes the `run-as-non-root` check
  globally, so nothing else caught a silent drop to root) and the missing
  `WEB_SEARCH_CONCURRENT_REQUESTS` assertion (ADR-017). Added Envoy AI Gateway to
  the CONTROLS.md T1 tier description (already `T1/model-serving` in `_helpers.tpl`
  and the governance tests). All supply-chain/version/governance invariants
  re-verified green (17-image values↔SBOM↔Zarf parity, Grype exceptions, the
  `files/` payload test suites). No image or chart-version change.

- **Ingestion worker now bootstraps its Qdrant collection
  ([runbook](docs/operations/RUNBOOK-remediation.md) A3).** On the opt-in
  ingestion-worker → Pydantic AI RAG path nothing created the Qdrant collection,
  so the first upsert/query returned 404. The worker now creates the collection
  on first use, taking the vector size from the live embedding (no hard-coded
  dimension, no drift) with `Cosine` distance; the create is idempotent and
  tolerates a concurrent create by a peer worker. `upsert_vectors` also now writes
  to the per-task `collection` instead of a module-global default. The
  producer-supplied collection name is validated against a strict allowlist before
  it is interpolated into a Qdrant URL (no path/query/whitespace characters), and
  confirmed collections are memoised to skip the per-upsert existence check. Adds
  the first Python test harness for `files/` (`files/ingestion-worker/test_worker.py`,
  respx-mocked) and a `worker-tests` CI job. Open WebUI's own Qdrant collections
  are unaffected. No image or chart-version change.

- **Production Open WebUI split-brain
  ([ADR-012](docs/architecture/ADR-012-ha-guard-execution-isolation-remediation-runbook.md)).**
  The production overlay disabled `postgres` while running Open WebUI at multiple
  replicas, so each replica fell back to a private per-pod SQLite database and
  users, chats, and settings split across pods. Fixed by enabling the shared
  database in `values-prod.yaml` and adding the render-time guard above so the
  misconfiguration can no longer ship from any values file. Open WebUI's own
  Qdrant-backed RAG is unaffected; multi-node uploaded-file durability remains a
  documented follow-up ([runbook](docs/operations/RUNBOOK-remediation.md) B1).

- **License matrix corrected: Open WebUI is not MIT
  ([LICENSE_COMPLIANCE.md](docs/compliance/LICENSE_COMPLIANCE.md)).** The deployed
  `open-webui` image is licensed under the custom **Open WebUI License**
  (BSD-3-Clause plus a branding-protection clause that applies above 50 end users
  in any rolling 30-day window), not MIT. Recorded in the license matrix with a
  dedicated analysis subsection, and the runtime-downloaded models (the embedding
  model and the optional reranker) are now catalogued with their licenses. The
  chart's own license (Apache-2.0) is unaffected.

- **In-depth audit and adversarial review — probe, identity, and parity fixes
  ([ADR-016](docs/architecture/ADR-016-audit-2026-06.md);
  [audit](docs/audit/AUDIT-2026-06.md) §6–§11).** A full-pass repository audit
  fixed two High-severity defects and a set of minor parity/precision issues, and
  re-verified the 2026-06-07 backlog as essentially closed:
  - **MCPO readiness never passed.** Both probes hit `GET /`, which MCPO (a
    FastAPI gateway) answers with 404, so the pod never became Ready. Now probes
    `/openapi.json` (validated against `open-webui/mcpo`).
  - **Authelia OIDC SSO was broken when enabled.** `client_secret` relied on
    Authelia's `${VAR}` expansion, which is off by default (and `expand-env` is
    deprecated, removed in v4.40), so the literal placeholder became the secret.
    It is now read from a mounted file via the `template` config filter's `secret`
    function (`X_AUTHELIA_CONFIG_FILTERS=template`); the value no longer rides a
    pod env var or the rendered manifest. Validated against `authelia/authelia`.
  - **Unbounded agent `deps` emptyDirs.** Pydantic AI and the ingestion worker now
    bound their dependency-install volume (`sizeLimit: 1Gi`, matching the `tmp`
    sibling) so a runaway install cannot exhaust node ephemeral storage.
  - **Parity / precision:** SBOM Valkey `boundary` aligned to the governance map
    (`cache` → `storage`); three stale `LICENSE_COMPLIANCE.md` versions re-aligned
    to `values.yaml` (Ollama, OTel, LangGraph); LangGraph tracing var
    canonicalised to `LANGSMITH_TRACING`; the OTel redaction compliance claim
    qualified to telemetry-enabled. The Tika-egress "finding" was verified a false
    positive (already closed by the additive default-deny). New
    `tests/authelia_oidc_test.yaml` plus assertions in `tests/mcpo_test.yaml` and
    `tests/hardening_test.yaml` (122 tests). No image or chart-version change.

- **Open WebUI wiring completeness — OTel activation, signup governance, Open
  Terminal docs, web-search tuning
  ([ADR-017](docs/architecture/ADR-017-openwebui-wiring-completeness.md)).** A
  source-validated review of how Open WebUI is configured and wired to its tools:
  - **Open WebUI OpenTelemetry now actually exports.** The chart injected the
    shared `OTEL_EXPORTER_OTLP_*` vars but Open WebUI gates OTel behind its own
    `ENABLE_OTEL` plus the per-signal `ENABLE_OTEL_TRACES` / `ENABLE_OTEL_METRICS`
    (all default-off upstream), so it emitted **nothing** even with
    `global.otel.enabled=true`. The chart now sets all three, gated on
    `global.otel.enabled` (off by default), so traces + metrics flow through the
    redaction-applying collector — the NIS2 monitoring control now covers the chat
    surface. Validated against `open-webui` (OTel since 0.6.0, present in v0.9.6).
  - **Governed signup defaults pinned.** `DEFAULT_USER_ROLE=pending` is now
    explicit (new accounts need admin approval; matches upstream's default but can
    no longer silently regress), with `ENABLE_SIGNUP=true` kept for first-admin
    bootstrap and documented to disable in production / under OIDC.
  - **Open Terminal wiring documented.** Like MCPO it is an admin-UI step
    (`TERMINAL_SERVER_CONNECTIONS` is inline-key JSON, POL-002): the full-deployment
    guide now covers retrieving the key and adding it under **Admin Settings →
    Integrations → Open Terminal**, and `values-full.yaml` carries a ready-to-enable
    block with the runtime-hardening caveat.
  - **Web-search tuning** added to `values-full.yaml` (`WEB_SEARCH_RESULT_COUNT=5`,
    `WEB_SEARCH_CONCURRENT_REQUESTS=10`, an empty `WEB_SEARCH_DOMAIN_FILTER_LIST`
    defense-in-depth hook). Asserted in `tests/openwebui_wiring_test.yaml` (125
    tests). No image or chart-version change.

## [2.12.0] - 2026-06-09

Works the deferred recommendation backlog of the 2026-06 deep audit
([AUDIT-2026-06](docs/audit/AUDIT-2026-06.md) §3, R1–R10) in one coordinated
change: supply-chain closure for the CNPG datastore, spec-compliant SBOM
purls, NetworkPolicy least-privilege tightening, opt-in Valkey AUTH
(ADR-008), ingestion URL-fetch SSRF hardening (ADR-009), and dependency
hash-locking. **No shipped default weakened**; two defaults strengthened
(see Security + upgrade notes).

### Added

- **Opt-in Valkey AUTH — `valkey.auth.enabled` ([ADR-008](docs/architecture/ADR-008-valkey-auth.md), audit R4).**
  Defense-in-depth on top of the default-deny NetworkPolicy for the
  session/pipeline datastore. The generated password (stable across upgrades)
  feeds a Secret-mounted `valkey.conf` (`requirepass` never appears in process
  args), the values-defined `valkey-cli` probes (via `VALKEYCLI_AUTH`/
  `REDISCLI_AUTH`), and every consumer URL by `$(...)` substitution: Open WebUI
  `REDIS_URL`/`WEBSOCKET_REDIS_URL`, the ingestion worker `VALKEY_URL` +
  stream-init, Authelia `session.redis.password`, and the helm-test RESP
  `AUTH`. Default off — enabling is a deliberate coordinated rollout; rotation
  is manual (`kubectl rollout restart`). New `tests/valkey_auth_test.yaml`.
- **CNPG operand image joins the supply chain (audit R1, High).**
  `postgres.cnpg.imageName` (an unpinned `:18` tag invisible to every parity
  check) is replaced by the standard `postgres.cnpg.image.{repository,tag}`
  block — digest-pinned, Renovate-managed, catalogued in `sbom.cdx.json` and
  mirrored by a new optional `postgres-cnpg` Zarf component (with a
  `POSTGRES_MODE` deploy variable), so the regulated datastore no longer
  escapes ADR-001/ADR-002 parity. The template fails with a migration hint if
  the legacy key is still set.
- **Ingestion worker URL-fetch hardening ([ADR-009](docs/architecture/ADR-009-ingestion-url-fetch-hardening.md), audit R5).**
  New `ingestionWorker.fetch.{schemes,allowedCidrs}` →
  `INGESTION_FETCH_SCHEMES` / `INGESTION_FETCH_ALLOWED_CIDRS`: https-only by
  default; loopback/link-local (IMDS)/multicast/reserved addresses always
  refused; private/non-global ranges refused unless allow-listed; redirects
  followed manually and re-screened per hop; invalid CIDRs fail at startup.
  Status/log messages keep the no-URL-leak property (host only, never the
  presigned query string).
- **Hashed universal lock for the ingestion worker (audit R7).** New
  `files/ingestion-worker/requirements.in` (ranges) compiled to a fully
  pinned, hashed, universal `requirements.txt` via `make
  ingestion-worker-lock` (uv, Python 3.14); the `install-deps` initContainer
  and the prebuilt-image Dockerfile install with `--require-hashes`. When
  `sources.pipPackages` adds fsspec backends, the base set is co-resolved from
  the `.in` ranges in one pass (pip hash mode is all-or-nothing — documented
  in values.yaml). Dependabot gains a `pip` ecosystem entry for both
  `files/` locks.
- **`global.otel.exportNamespace`** (default `observability`) — names the
  platform observability namespace so the OTel Collector's export egress can
  be scoped (see Security); keep in sync with the exporter endpoints.
- **`global.repoSlug` surfaced in values.yaml + schema (audit R9).** Already
  consumed by the PrometheusRule runbook URLs (with a working default); now
  documented so forks can point runbook links at their own docs. The
  remaining R9 item (more ServiceMonitors) is intentionally not done: no other
  component exposes a native Prometheus `/metrics` endpoint to scrape
  (SearXNG metrics are disabled by config; Valkey/Postgres need exporters,
  out of chart scope).

### Changed

- **SBOM purls are now spec-compliant (audit R2).** Components previously
  carried a double-`@` form (`pkg:docker/name@tag@sha256:…`); the digest now
  rides the canonical `checksum` qualifier
  (`pkg:docker/name@tag?checksum=sha256:…`), qualifiers sorted per the purl
  spec. `sync_image_artifacts.py` (`rewrite_purl`/`update_sbom`) emits the new
  form and migrates the legacy one; the CI parity steps verify purl-version ↔
  component-version and checksum ↔ hashes[] consistency; new unit tests cover
  both functions.
- **helm-test hook image digest-pinned (audit R6):**
  `busybox:1.37@sha256:9532d8c3…` (test hook only; intentionally outside the
  SBOM/Zarf parity set, which covers shipped images).
- `Chart.yaml` 2.11.0 → 2.12.0; version-bearing artifacts resynced per
  ADR-001 (README badge, `zarf.yaml` package/chart versions + deploy comment,
  SBOM package version/timestamp/serial, compliance/enterprise/governance/
  baseline/multi-user doc headers, SECURITY.md supported versions,
  LIMITATIONS.md review marker).

### Fixed

- **`helm test` had no test to run: the connection-test hook was silently
  excluded from the chart.** The `.helmignore` entry `tests/` (added with the
  helm-unittest suite in 2.6.0 to keep unit tests out of the package) matches
  any directory named `tests` at any depth — including `templates/tests/` — so
  the connectivity-check Pod was dropped from every render, package, and
  install since then (`helm test` reported nothing; the hook also escaped
  kube-linter/kubeconform). The pattern is now anchored to the chart root
  (`/tests/`), the hook renders again, and a `tests/` assertion locks its
  presence (and its ADR-002 digest pin) so it cannot vanish silently again.

### Security

- **Open WebUI in-namespace ingress no longer admits every pod (audit R3).**
  The `podSelector: {}` rule is replaced by an allowlist of the helm-test pod
  and (only when telemetry is enabled) the OTel Collector's `/metrics`
  scrape. Edge traffic via `global.ingressNamespace` is unchanged. **Upgrade
  note:** operator-added in-namespace clients that called the Open WebUI API
  directly were riding on the any-pod rule — give them their own additive
  NetworkPolicy.
- **OTel Collector export egress is namespace-scoped (audit R3).** The
  previously unscoped 4317/4318/3100/9090 egress now targets only
  `global.otel.exportNamespace` + `global.monitoringNamespace`. **Upgrade
  note:** if your observability pipeline lives in another namespace, set
  `global.otel.exportNamespace`; if it lives **off-cluster** (an external
  OTLP/Loki endpoint), namespace selectors cannot match it — add your own
  additive NetworkPolicy with an `ipBlock` egress for the collector pods
  (NetworkPolicies are additive, so the chart's policy does not need
  changing).
- **Ingestion `file_url` fetches are https-only and address-screened by
  default (ADR-009; audit R5 — strengthened default).** **Upgrade note:**
  plain-HTTP sources need `ingestionWorker.fetch.schemes: [https, http]`;
  in-cluster/private-range sources (e.g. presigned URLs of an in-cluster
  MinIO) need their CIDR in `ingestionWorker.fetch.allowedCidrs`. External
  presigned HTTPS URLs and CSI-mount local paths keep working untouched.
- **Local `file_url` reads validate the live file handle (audit R10).**
  `O_NOFOLLOW` open + `fstat` on the descriptor replaces the
  check-then-reopen sequence, closing the symlink-swap TOCTOU on writable
  mounts; FIFOs can no longer hang the open (`O_NONBLOCK`).
- **Open WebUI OAuth session-token encryption uses its own key (audit R8).**
  `OAUTH_SESSION_TOKEN_ENCRYPTION_KEY` now reads a dedicated, independently
  generated `oauth-token-encryption-key` Secret entry instead of reusing the
  JWT-signing `secret-key`. **Upgrade note:** existing OAuth session tokens
  cannot be decrypted after the split — SSO users re-authenticate once;
  local-auth sessions are unaffected.
- LIMITATIONS.md **L9** updated for the ADR-009 posture and its residuals
  (DNS-rebinding window — no connection pinning; parent-directory symlink
  races; overly broad CIDR grants).

## [2.11.0] - 2026-06-07

Ingestion worker: a documented contract (specification) and **opt-in native
source connectors** for object stores and network shares.

### Added

- **Native ingestion source connectors (ADR-007).** Opt-in `fsspec`-based
  resolver so producers can enqueue object-store / network-share scheme URLs
  (`s3://`, `gs://`, `az://`, `smb://`, `sftp://`, …) — alongside the existing
  `http(s)://` (incl. **presigned** URLs) and local-path (incl. **CSI-mounted
  NFS/SMB**) sources. **Deny-by-default:** a native scheme is honored only when
  allow-listed in `ingestionWorker.sources.schemes`; backends are operator-chosen
  via `sources.pipPackages` (the default image stays lean); credentials come from
  `sources.existingSecret` (projected via `envFrom`, never inlined). Off by
  default and fully backward compatible. New `tests/ingestion_sources_test.yaml`.
- **`docs/components/ingestion-worker-spec.md` — authoritative worker contract.**
  Task-message and status-hash protocols, consumer-group delivery/retry
  semantics, the optional PostgreSQL corpus state machine (states, transitions,
  audit tables, and the `corpus:state` pub/sub event), source-resolution rules,
  and the full environment-variable reference.

### Changed

- Corrected the ingestion-worker docs to match the code: the component doc's
  values-key table (referenced non-existent keys) and status fields; `HOWTO.md`
  §5 status lifecycle (`queued → … → completed` → the real
  `processing → extracting → chunking → embedding → upserting → done`); the
  README/HOWTO enqueue contract incl. the optional `collection` field — which
  keys the corpus state machine and tags the payload, and does **not** route the
  Qdrant upsert; and a stale `digest:` example in the worker `Dockerfile`.

### Fixed

- **Init container `install-deps` is one `pip install` with `set -e`.** Base
  `requirements.txt` and the operator-selected `sources.pipPackages` now resolve
  in a single pass (a backend that conflicts with a base dep fails at build, not
  at runtime), and a failed base install no longer exits 0 and silently starts a
  worker with missing dependencies.
- **`file://` URLs parsed per RFC 8089.** `file:///p` and `file://localhost/p`
  both resolve to `/p`; previously a `file://host/…` authority was folded into the
  path and the worker read the wrong (cwd-relative) file.
- **`INGESTION_SOURCE_SCHEMES` is wired only when a scheme is allow-listed** (not
  on `sources.enabled` alone), so a scheme-allowlist audit never sees an empty,
  misleading variable.
- **Version-reference drift.** `SECURITY.md` supported-versions table and the
  `LIMITATIONS.md` review marker realigned to 2.11.0; new `LIMITATIONS.md` **L9**
  documents the ADR-007 fetch surface.

### Security

- **Local `file_url` reads are restricted to regular files** — devices
  (`/dev/urandom`, `/dev/zero`), FIFOs, sockets and directories are rejected,
  closing an unbounded-`read_bytes` DoS — in addition to the existing
  credential/system-prefix fence (`/proc`, `/sys`, `/etc`, `/root`, `/run`,
  `/var/run`).
- **HTTP `file_url` fetches reject non-2xx responses** — reporting only the
  status code, never the URL, so a **presigned signature isn't echoed** into logs
  or the status hash — and a 404/500 error-page body is never extracted.
- **Pydantic AI warns at startup when `PYDANTICAI_API_KEY` is empty**, surfacing
  that the bearer-token gate is a no-op (endpoints unauthenticated).
- **No security default weakened.** Native connectors are opt-in and
  deny-by-default; the chart does **not** auto-open egress for native non-HTTPS
  protocols (SMB/NFS/SFTP). PSA `restricted`, default-deny NetworkPolicy, and
  per-component identity are unchanged. See
  [ADR-007](docs/architecture/ADR-007-ingestion-source-connectors.md).

## [2.10.0] - 2026-06-07

Baseline, standards, and a deep repo audit — plus a focused set of
defense-in-depth and documentation-currency fixes. **No security default
weakened.**

### Added

- **`docs/SECURITY_BASELINE.md` — operator-facing security & operations
  baseline.** Maps the chart's shipped defaults to validated external standards
  (CIS Kubernetes Benchmark, NSA/CISA Kubernetes Hardening Guide, NIST SP
  800-190, Pod Security Standards, OWASP LLM Top 10) with a conformance matrix
  and copy-paste verification commands. Fills the gap between the
  contributor-facing `AGENTS.md`/`CLAUDE.md` and the assessment-oriented
  enterprise/compliance docs.
- **`docs/operations/MULTI_USER.md` — multi-user, cost, and audit-retention
  guide.** `ResourceQuota`/`LimitRange` examples, Open WebUI role/group
  model-access, per-user isolation, GPU right-sizing and scaling economics, and
  forensic vs. data-minimisation log-retention guidance.
- **`docs/audit/AUDIT-2026-06.md` — committed deep-audit report** with verified
  findings and a prioritised recommendation backlog (including items
  intentionally deferred to a dedicated change: CNPG image digest-pinning + SBOM
  inclusion, SBOM purl format, NetworkPolicy egress tightening, optional Valkey
  AUTH, ingestion-worker URL allowlisting).
- **Valkey `PodDisruptionBudget`.** Valkey was the only single-replica
  session/Streams store without a PDB; it now joins the other protected
  components (`maxUnavailable: 1`, `unhealthyPodEvictionPolicy: AlwaysAllow`) —
  the chart's documented single-replica PDB pattern: drain-safe (no eviction
  deadlock) and disruption-budget-aware once Valkey is scaled out. Surviving a
  node drain with zero session loss still requires a multi-replica / clustered
  Valkey.
- **`tests/hardening_test.yaml`.** Asserts the Valkey PDB and that the OTel
  Collector ships its **credential** redaction patterns (bearer tokens, JWTs,
  PEM private keys, provider API-key shapes), not only the three PII patterns —
  so the security-relevant default cannot silently regress.

### Changed

- **Pydantic AI reference app uses a constant-time bearer-token check**
  (`hmac.compare_digest`) on its only auth gate, removing a timing oracle
  (`files/pydanticai/app.py`).
- **`.helmignore` excludes `Makefile`, `AGENTS.md`, `CLAUDE.md`, and `.claude/`**
  so internal contributor/agent tooling is not bundled into the packaged chart.

### Fixed

- **Documentation currency / drift (no behaviour change):**
  - `SECURITY.md` supported-versions table now covers `2.10.x` / `2.9.x`.
  - `LIMITATIONS.md` re-reviewed for 2.10.0; new **L8** tracks the AI Gateway
    BYO control/data-plane and external-provider data-transfer residual risk.
  - `docs/architecture/REFERENCE.md` extension key corrected to
    `mcpo.config.mcpServers` (was `mcpo.servers`, a silently-ignored override).
  - OTel redaction is documented as PII **and credential** redaction across
    `docs/components/otel.md`, `HOWTO.md` §14.3, and `CONTROLS.md` CTL-001
    (previously listed only the 3 PII patterns; 12 ship by default).
  - `docs/enterprise/ENTERPRISE_EVALUATION.md`: image management attributed to
    Renovate (digest-pinned) not "manual"; "versioned tags" → digest-pinned;
    removed fabricated DR retention numbers (backup is external by design).
  - `docs/compliance/LICENSE_COMPLIANCE.md`: SBOM CI validator corrected to
    `cyclonedx-cli`; stale Open WebUI / Ollama / Qdrant matrix versions resynced
    to `values.yaml`.
  - `docs/compliance/EU_COMPLIANCE_CHECK.md`: supply-chain tooling attributed to
    Renovate (images) + Dependabot (Actions).
  - `README.md` architecture diagram now includes the opt-in AI Gateway.
  - `CHANGELOG.md` compare-links restored for 2.5.0–2.10.0.

### Security

- **No security default weakened.** All changes are additive hardening
  (availability PDB, constant-time auth), test coverage for an existing
  redaction default, or documentation accuracy. PSA `restricted`, default-deny
  NetworkPolicy, per-component identity, and digest pinning are unchanged.

## [2.9.0] - 2026-06-07

Opt-in **Envoy AI Gateway** component (ADR-006) — a governed, Apache-2.0,
OpenAI-compatible model-egress boundary. No security default changes.

### Added

- **Opt-in `aiGateway` component (implemented by Envoy AI Gateway, Apache-2.0).** Renders
  the Envoy AI Gateway custom resources (`AIGatewayRoute` / `AIServiceBackend` /
  `BackendSecurityPolicy` + the Envoy Gateway `Backend`, plus optional
  `BackendTrafficPolicy` token rate-limiting and a JWT/OIDC `SecurityPolicy`)
  that turn a pre-existing Gateway into one in-cluster OpenAI-compatible endpoint
  for local Ollama + external providers — centralizing provider credentials,
  routing, and audit. **CR-only:** the chart attaches to a BYO control + data
  plane (exactly as ADR-003's HTTPRoute attaches to a Gateway it does not
  provision) and emits **no workload pod** — governance metadata lives on the CR
  objects (like the CNPG `Cluster`/`Pooler`), with no ServiceAccount and no
  cluster-RBAC controller. Mutually exclusive with `externalAPIs` (one egress
  path, one audit story). Disabled by default. Governance: `T1` /
  `model-serving` / `CTL-002,POL-001`.
- **Air-gap image mirroring for the BYO controller.** The Envoy AI Gateway
  `ai-gateway-controller` and `ai-gateway-extproc` images (v0.7.0, Apache-2.0,
  digest-pinned) are declared in `values.yaml` and catalogued in `sbom.cdx.json`
  + `zarf.yaml` so Zarf mirrors them into an air-gapped registry; the platform
  installs the upstream controller chart against the mirror.

### Security

- **No security default weakened.** The new component is CR-only — it adds no
  privileged workload (no pod, no token-mounted ServiceAccount, no cluster RBAC).
  Provider API keys are stored in chart-managed (or existing) Secrets, never in
  rendered manifests. PSA `restricted`, default-deny NetworkPolicy, and digest
  pinning are unchanged. (Bundling the controller as an in-chart Deployment was
  evaluated and rejected for exactly this reason — see ADR-006.)

### Changed

- **CI: deep-SBOM validation now uses the CycloneDX CLI instead of Python
  `check-jsonschema`.** The `syft-sbom` job validated each generated deep SBOM
  against the remote CycloneDX 1.6 JSON schema with `check-jsonschema`, which
  took roughly 56 minutes per run on large SBOMs; it now uses the pinned,
  checksum-verified `cyclonedx-cli` (`validate --fail-on-errors`), which
  completes in seconds. The job also gains an explicit `timeout-minutes: 20`
  guard so a pathological input fails fast instead of running to the 6-hour
  ceiling. Validation coverage is unchanged: the committed `sbom.cdx.json` is
  still schema-validated by the `sbom-validate` job.
- **CI: `actions/setup-python` pinned to `v6.2.0`** (Node.js 24 runtime) in
  `lint.yaml`, `docs.yaml`, and `sync-image-artifacts.yml`, ahead of GitHub
  forcing the Node.js 24 runtime on 2026-06-16 (Node 20 is removed from runners
  on 2026-09-16). Aligns with the version already used fleet-wide.

## [2.8.0] - 2026-06-01

Governance-label integrity and supply-chain version parity, from a full-repo
audit (ADR-005). No security default changes — additive governance metadata plus
drift enforcement.

### Added

- **`assurance.platform/control-refs` annotation on every workload.** Each
  Deployment (plus the CNPG `Cluster`/`Pooler` and the Valkey and OTel Collector
  Deployments) now references the controls it implements — `CTL-002` (network-boundary governance)
  and `POL-001` (least-privilege identity); the OTel Collector adds `CTL-001`.
  `POL-001` is now traceable in-cluster for the first time. (AGENTS.md §2.6
  already required this; it was previously present only on the OTel Collector.)
  Tier/boundary labels and the control-refs annotation are emitted on **both the
  controller and the pod template** (via the `ai-stack.governanceMap` helper), so
  a pod-scanning evidence pipeline sees the same metadata a controller scan does;
  the now-redundant profile-wide `control-refs` in `values-prod.yaml`'s
  `global.podAnnotations` is removed so it can't overwrite the per-workload value.
- **Canonical governance label vocabulary** in `docs/governance/CONTROLS.md` — the
  authoritative `tier` (T0–T2) and `boundary` (8 values) tables, naming the
  rendered templates as the source of truth.
- **`tests/governance_labels_test.yaml`** — asserts tier/boundary/control-refs for
  every workload (16 cases), so templates, docs, and the CTL/POL registry can no
  longer drift apart.
- **SBOM package-version parity check** in the `sbom-validate` CI job — fails if
  `sbom.cdx.json` `metadata.component.version` differs from `Chart.yaml` `version`.
- **ADR-005** — governance label integrity: canonical vocabulary, control-refs on
  every workload, and the test + CI enforcement.

### Changed

- **Boundary annotations aligned across docs and templates.** The `boundary` value
  in 9 component docs (`authelia`, `ingestion-worker`, `ollama`, `otel`,
  `postgres`, `qdrant`, `searxng`, `tika`, `valkey`) now matches the rendered
  template; the v2.6.0 fix had only covered `mcpo` and `open-terminal`. Each
  component doc gained a `Control refs` line.
- `CONTROLS.md` CTL-002 / POL-001 rows now reference the canonical vocabulary and
  the in-cluster `control-refs` traceability; the dead `internal`/`decision`-only
  boundary wording is retired.
- `AGENTS.md` §5/§6 document the new SBOM package-version check and checklist item.
- `SECURITY.md` — refreshed the Supported Versions table (2.7.x/2.8.x) and added a
  governance-traceability control bullet.

### Fixed

- **OTel Collector `control-refs` was an invalid Kubernetes label** (`"CTL-001,CTL-002"`
  — commas are not valid in a label value, so a cluster apply would reject it;
  `kubeconform`/`kube-linter` are schema-only and never caught it). `control-refs`
  is now an **annotation** on every workload; `tier`/`boundary` remain labels.
- **Valkey Deployment was missing its `assurance.platform/boundary` label** — now
  `storage`, matching the other datastores.
- **SBOM package-version drift** — `sbom.cdx.json` `metadata.component.version` was
  stale at `2.5.0` while the chart was `2.7.0`; corrected to `2.8.0` and now
  CI-enforced.
- Synced all version-bearing artifacts to `2.8.0` (Chart, README badge, `zarf.yaml`
  package + local-chart versions + deploy comment, SBOM, and the
  compliance/enterprise/governance doc headers) per ADR-001.

## [2.7.0] - 2026-05-31

ArgoCD / GitOps optimization and deployment-rollout hardening.

### Added

- **Dedicated ArgoCD `AppProject`** (`argocd/appproject.yaml`) — least-privilege:
  the controller is scoped to this repository and the `ai-stack` namespace, and
  cluster-scoped resources other than `Namespace` are denied. Both Applications
  now run under it (`project: ai-stack`).
- **Sync-wave ordering** — chart workloads carry `argocd.argoproj.io/sync-wave`
  annotations so a fresh `argocd app sync` rolls out in dependency order:
  foundation (Secrets + ServiceAccounts, `-10`) → platform (datastores / backing
  services, `0`) → app workloads (`5`) → HPA/PDB policies (`10`, applied last so
  their target workloads already exist). Harmless outside ArgoCD.
- **GitOps CI validation** — the `kubeconform` job now validates the `argocd/`
  manifests against the Argo CRD schemas, and `argocd/**` is a workflow trigger
  path, so this set can no longer drift unchecked.

### Changed

- **Narrowed ArgoCD `manifest-generate-paths`** to chart-affecting files
  (`Chart.yaml`, `values*.yaml`, `values.schema.json`, `templates/`, `files/`)
  so docs/tests/SBOM pushes don't churn the controller.
- **Rollout strategy for RWO single-replica deployments** — Authelia, LangGraph,
  and Open Terminal use `strategy: Recreate` **when `persistence.enabled`** (an
  attached ReadWriteOnce PVC), avoiding the RollingUpdate deadlock where the new
  pod cannot mount the volume still held by the old pod. Ephemeral installs keep
  the default RollingUpdate. Probes, resources, and anti-affinity
  (topologySpread) were reviewed and left unchanged — already appropriate.

### Fixed

- The README GitOps table said the lab Application had auto-sync **disabled**; it
  is in fact **enabled** (prune + selfHeal), matching the manifest and HOWTO §17.

## [2.6.0] - 2026-05-31

Tool/command-plane hardening for the model-driven components (MCPO and Open
Terminal), derived from a cross-checked review against the MCP authorization
spec, OWASP LLM "excessive agency", the NSA/CISA Kubernetes hardening guidance,
and the untrusted-code sandboxing consensus. Hardening patterns are integrated
natively; no external projects are bundled.

### Added

- **Sandbox runtime for model-generated code** — new `openTerminal.runtimeClassName`
  and `mcpo.runtimeClassName` (default empty = cluster default). Set to a
  hardened RuntimeClass (e.g. `gvisor`/`kata`) to add a kernel/VM boundary
  around model-executed code; standard containers are only the minimum-viable
  isolation for untrusted code.
- **Scoped CORS for Open Terminal** — new `openTerminal.corsAllowedOrigins`.
  `OPEN_TERMINAL_CORS_ALLOWED_ORIGINS` is now templated from it and **never
  emits `*`** (OWASP A05); empty derives the Open WebUI origin — from its
  ingress host (scheme matched to the ingress TLS config, including matching
  wildcard certs) or httpRoute hostname
  (http when a parentRef targets port 80, else https), else the in-cluster
  Service. A legacy `openTerminal.env.OPEN_TERMINAL_CORS_ALLOWED_ORIGINS`
  override is preserved verbatim and is no longer duplicated as a second env
  var on upgrade — **except a carried-over `"*"` from the old default, which is
  dropped** so a `helm upgrade --reuse-values` from 2.5.x does not retain a
  wildcard CORS policy on the code-executing service. (CORS is only exercised
  if the terminal/notebook UI is exposed to a browser; the default topology
  reaches Open Terminal server-side, pod-to-pod.)
- **Secret redaction in telemetry** — the OTel Collector redaction processor now
  also strips bearer tokens, JWTs, full PEM private-key blocks (header through
  footer, not just the header line), and provider API-key shapes (OpenAI, AWS,
  GitHub, GitLab, Google, Slack, Stripe) in addition to PII.
- **Threat model** in `SECURITY.md` (indirect prompt injection → excessive
  agency at the tool/command plane; compensating controls; residual risk) and a
  new top-level **`LIMITATIONS.md`** with per-component scope boundaries.
- **`AGENTS.md` + `CLAUDE.md`** — an agent/contributor operating spec (repo map,
  required change workflow, version-bump checklist, CI gates, security posture)
  and a Claude-specific collaboration overlay; linked from `CONTRIBUTING.md`.
  Version-bearing docs (`ENTERPRISE_EVALUATION.md`, `CONTROLS.md`,
  `LICENSE_COMPLIANCE.md`, `EU_COMPLIANCE_CHECK.md`) synced to `2.6.0`.
- **`helm-unittest` test suite** (`tests/`) asserting the security claims —
  restricted `securityContext`, no token automount, scoped CORS, opt-in
  `runtimeClassName`, ephemeral storage default, governance tier/boundary
  labels, and default-deny/tool-plane NetworkPolicy isolation — wired into CI
  (`helm-unittest` job) and `make unittest` / `make test`.

### Changed

- **Open Terminal storage is now ephemeral by default** —
  `openTerminal.persistence.enabled` defaults to `false` so a payload written by
  model-generated code does not survive a restart; the ephemeral volume is
  size-bounded (`emptyDir.sizeLimit`, from `openTerminal.persistence.size`) so a
  runaway write cannot exhaust node ephemeral storage. **Upgrade note:** set
  `openTerminal.persistence.enabled=true` to retain the previous behaviour; the
  PVC keeps `helm.sh/resource-policy: keep`, so existing data is not deleted.
- Expanded `docs/components/{open-terminal,mcpo}.md` Security sections
  (sandbox-first framing, Authelia-when-exposed, no token passthrough).

### Fixed

- Synced `zarf.yaml` package and local-chart versions to `2.6.0` alongside the
  chart bump (ADR-001 version-bearing-artifact discipline).
- Documentation drift: `docs/components/open-terminal.md` and `mcpo.md` now state
  the actual deployment `boundary` annotations (`execution` and `decision`
  respectively, not `internal`), and `mcpo.md` references the real values key
  `mcpo.config.mcpServers` (not `mcpo.servers`).

### Security

- Hardened the two components that execute or broker model-driven actions; see
  `SECURITY.md` (Threat model) and `LIMITATIONS.md` for the residual-risk
  posture and the controls that remain the operator's responsibility.

## [2.5.0] - 2026-05-31

### Added

- **Pydantic AI production hardening** — the reference agent
  (`files/pydanticai/app.py`) now exposes an **OpenAI-compatible API**
  (`GET /v1/models`, `POST /v1/chat/completions` with streaming and
  non-streaming) alongside `POST /run`, wraps its tool I/O (SearXNG web search,
  Qdrant retrieval) in `DBOS.step()` for durable, checkpointed execution, and
  enforces bearer-token auth on every endpoint. Python dependencies are now a
  **fully pinned, hashed, universal lock** (`files/pydanticai/requirements.txt`,
  compiled from `requirements.in` and installed with `--require-hashes`);
  regenerate with `make pydanticai-lock`.
- **Open WebUI high-availability by default** — Open WebUI now runs as a
  genuinely stateless, horizontally-scalable service. The chart wires
  `WEBUI_SECRET_KEY` (+ `OAUTH_SESSION_TOKEN_ENCRYPTION_KEY`) from a persisted
  Secret so sessions survive restarts and are valid on every replica; points
  `DATABASE_URL` at the shared PostgreSQL (its own `openwebui` database,
  auto-created in standalone mode via an initdb ConfigMap); and configures the
  Valkey-backed websocket manager (`REDIS_URL`, `WEBSOCKET_MANAGER=redis`,
  `WEBSOCKET_REDIS_URL`) per Open WebUI's "Scaling & HA" guidance. PostgreSQL is
  now a **default-enabled** core dependency (set `postgres.enabled=false` for an
  ephemeral single-pod lab, where Open WebUI falls back to SQLite). New keys:
  `openwebui.secretKey`, `openwebui.databaseName`.
- **Open WebUI ↔ Pydantic AI wiring** — set `pydanticai.exposeToOpenWebUI=true`
  to register the agent in Open WebUI's model picker: the chart appends the
  agent's `/v1` endpoint to `OPENAI_API_BASE_URLS`, injects its API key from the
  generated Secret, and opens the Open WebUI → pydanticai NetworkPolicy egress.
  A `helm test` health probe now covers the agent.
- **Docs link-check CI gate** (`.github/workflows/docs.yaml` +
  `.github/scripts/check_md_links.py`): a deterministic, offline checker
  validates every relative link and `#anchor` across all markdown files using
  GitHub-accurate heading slugs, so internal doc-link rot fails CI. Runs only on
  markdown changes; also available via `make check-links`.
- **CI `zarf-lint` job** (`.github/workflows/lint.yaml`): validates `zarf.yaml`
  with `zarf dev lint` (pinned Zarf v0.77.0 + SHA-256 checksum) against the Zarf
  package schema — catching package-definition drift the image-parity check
  cannot see. Also broadened the workflow's `paths` trigger to include
  `zarf.yaml`, `files/**`, `values.schema.json`, and `.kube-linter.yaml`
  (edits to those previously skipped CI on PRs), and added `pydanticai` to the
  all-optional-components kube-linter run.
- **ADR-003** (opt-in Gateway API `HTTPRoute`) and **ADR-004** (Pydantic AI as an
  MIT-licensed agentic-runtime alternative) documenting the architectural
  decisions shipped in 2.3.0 / 2.4.0; linked from the README documentation table.

### Changed

- **Pydantic AI documentation** (`docs/components/pydanticai.md`, `README.md`,
  `HOWTO.md` §8.4) updated for the OpenAI-compatible endpoints, the
  `exposeToOpenWebUI` toggle, and the hashed dependency lock.
- **Documentation polish across the stack**: the README architecture
  diagram includes Pydantic AI and the Gateway API section lists `pydanticai`;
  `REFERENCE.md` §3 and `HOWTO.md` §8 cover both agentic runtimes (LangGraph /
  Pydantic AI) with a new HOWTO §8.4; `langgraph.md` cross-references the MIT
  alternative; `CONTRIBUTING.md` documents the cross-artifact sync discipline and
  the CI gates (kube-linter, digest parity, zarf-lint); `otel.md` corrected to the
  actual `redaction` processor.

### Removed

- **GPU Workbench component** — the opt-in JupyterLab/CUDA workbench
  (`workbench.*`) has been removed entirely (template, values, SBOM/Zarf image,
  docs, and SA/Secret/PDB/NetworkPolicy wiring) to streamline the chart. It was
  disabled by default, so existing default deployments are unaffected; users who
  need GPU notebooks should deploy a dedicated JupyterHub/Notebook chart
  alongside. The chart now pins **14** container images (was 15).

### Fixed

- **Pydantic AI OpenAI-compatible endpoint** — preserve multi-turn chat history
  (build `message_history` from the full `messages` array instead of only the
  last user turn); stream real token deltas via `run_stream()` when running
  non-durable (the DBOS durable path keeps the buffered single-chunk SSE); and
  return generic error text to clients while logging detail server-side
  (addresses a CodeQL information-exposure finding). *(Codex/CodeQL review.)*
- **Open WebUI → LangGraph NetworkPolicy egress** was inadvertently replaced by
  the Pydantic AI egress rule; both allows now coexist. *(Codex review.)*
- **Docs link checker** now reproduces GitHub's duplicate-heading anchor
  suffixes (`-1`, `-2`, …) so links to repeated sections are not falsely
  flagged. *(Codex review.)*
- **`zarf.yaml` chart variables were invalid** against the Zarf package schema
  (`zarf dev lint` reported 16 errors across the optional components): each
  `charts[].variables[]` entry was missing the required `description` and
  carried a `default` key that `ZarfChartVariable` does not permit. Moved the
  defaults to package-level `variables` (which legitimately carry `default`) and
  gave every variable a `description`. `zarf dev lint` now passes cleanly. No
  change to rendered chart output.

## [2.4.0] - 2026-05-31

### Added

- **Pydantic AI agentic runtime** (`pydanticai`, opt-in) — a fully
  **MIT/Apache-2.0**-licensed alternative to the LangGraph runtime (whose server
  image is ELv2 and gates production self-hosting behind a commercial key).
  Built on [Pydantic AI](https://ai.pydantic.dev/) with durable execution via
  **DBOS**, checkpointed in the shared PostgreSQL (degrades to non-durable when
  Postgres is absent). Exposes `GET /health` and `POST /run`, connects to Ollama
  (OpenAI-compatible inference) with optional SearXNG web-search and Qdrant
  retrieval tools, and emits OpenTelemetry traces. The agent source lives in
  `files/pydanticai/app.py` (loaded via `.Files.Get`) as a reference to extend;
  deps install at startup (`buildDeps: true`) or bake into a prebuilt image
  (`files/pydanticai/Dockerfile`, `buildDeps: false`). Ships ServiceAccount,
  API-key Secret, default-deny NetworkPolicy, optional HPA/PDB, Service, and
  Ingress + Gateway API HTTPRoute wiring. Base image
  `ghcr.io/astral-sh/uv:python3.13-trixie-slim` (digest-pinned) is catalogued in
  `sbom.cdx.json`, `zarf.yaml` (new optional component), `values.schema.json`,
  and the license matrix. See `docs/components/pydanticai.md`.

### Changed

- **Chart `version` 2.3.0 → 2.4.0** (minor — new opt-in component); version-bearing
  artifacts resynced (`Chart.yaml`, `zarf.yaml`, `sbom.cdx.json`, README badge,
  and the compliance/enterprise/governance doc headers) per ADR-001. `appVersion`
  stays `2026.5`.
- **OTel Collector**: renamed the `resourcedetection` processor to
  `resource_detection` (definition + all three pipelines). The old name is a
  deprecated upstream alias; this clears the deprecation warning and the
  follow-up flagged in the 2.3.0 notes. No behavioural change.
- **LangGraph licensing documentation strengthened** (closing a compliance gap):
  `LICENSE_COMPLIANCE.md`, the `sbom.cdx.json` license-note, and the README now
  distinguish the MIT `langgraph` library from the ELv2 `langgraph-server`
  runtime and state that production self-hosting requires a commercial LangGraph
  Platform license key beyond the free Developer tier (per LangChain's published
  terms 2026-05; verify for your version/tier). Cross-references the new MIT
  Pydantic AI alternative.

### Fixed

- **`LICENSE_COMPLIANCE.md` dependency-tracking note** corrected from "container
  images tracked manually" to Renovate (`helm-values`, `pinDigests`).

## [2.3.0] - 2026-05-31

### Added

- **Gateway API support (opt-in `HTTPRoute`).** Each externally-exposed component
  (`openwebui`, `workbench`, `langgraph`, `authelia`) can now emit a
  `gateway.networking.k8s.io/v1` `HTTPRoute` as a modern alternative to `Ingress`
  (both may be enabled simultaneously). A shared `ai-stack.httpRoute` helper renders
  the route and attaches it to a pre-existing `Gateway` via `parentRefs` (default
  namespace `global.gateway.namespace`, falling back to `global.ingressNamespace`).
  Default-off, so existing deployments are unchanged. `values.schema.json` and the
  kubeconform `-skip` list updated; rendered routes were validated against the
  upstream Gateway API v1 JSON schema. See README "Gateway API (HTTPRoute)".
- **Valkey persistence.** `valkey.persistence.enabled=true` now provisions a PVC
  (RDB snapshots under `/data`) and switches the Deployment to the `Recreate`
  strategy, so Valkey Streams and in-flight ingestion tasks survive pod restarts.
  Adds `valkey.persistence.{size,accessMode,mountPath}`. (See Fixed: the flag was
  previously a no-op.)
- **Ingestion worker prebuilt-image path (`ingestionWorker.buildDeps`).** Set to
  `false` to skip the runtime `pip install` initContainer and supply an image with
  dependencies baked in (new `files/ingestion-worker/Dockerfile`), removing PyPI
  egress at pod startup for air-gapped/hardened clusters.
- **kube-linter CI job** (`.github/workflows/lint.yaml`) policy-lints rendered
  manifests for the lab, prod, and all-optional-components profiles; tuned via
  `.kube-linter.yaml` (documented exclusions only). Pinned to v0.8.3 with a
  SHA-256 checksum.
- **CI image-digest parity check** in the `sbom-validate` job: enforces that every
  component's manifest digest is present and identical across `values.yaml`,
  `sbom.cdx.json`, and `zarf.yaml`. Closes the ADR-002 §Consequences follow-up
  (the prior parity step compared tags only).
- **PodDisruptionBudgets** now set `unhealthyPodEvictionPolicy: AlwaysAllow`
  (policy/v1, GA K8s 1.27) so node drains are not deadlocked by unready pods.

### Changed

- **Chart `version` 2.2.0 → 2.3.0** (minor — new opt-in features) and **`appVersion`
  2026.4 → 2026.5**; version-bearing artifacts resynced (`Chart.yaml`, `zarf.yaml`,
  `sbom.cdx.json`, README badges, and the compliance/enterprise/governance doc
  headers) per ADR-001.
- **`kubeVersion` raised `>=1.25.0-0` → `>=1.27.0-0`** (README badge → `1.27+`) —
  required by the new PDB `unhealthyPodEvictionPolicy` (GA 1.27) and matching the
  README's long-standing `1.27+` prerequisite.
- **Image bumps** (registry-verified digests, synced across `values.yaml`,
  `sbom.cdx.json`, `zarf.yaml`, the ADR-002 digest table, and `LICENSE_COMPLIANCE.md`
  per ADR-001/ADR-002): Tika `3.3.0.0 → 3.3.1.0`, SearXNG
  `2026.5.26-0037d43d8 → 2026.5.31-300695de5`, LangGraph Server `0.8-py3.12 → 0.9-py3.12`.
- **CloudNativePG image** `postgresql:16 → postgresql:18`, aligning `postgres.mode: cnpg`
  with the standalone `postgres:18` image so switching modes does not change the
  engine major version.
- **Ingestion worker source extracted** from the inline ConfigMap to
  `files/ingestion-worker/worker.py` (+ `requirements.txt` with major-version upper
  bounds), loaded via `.Files.Get`. The deployment's `checksum/config` now hashes the
  worker source (see Fixed).
- **README "Dependency Management"** rewritten: container images are managed by
  Renovate (`helm-values`, `pinDigests: true`), not "manually".

### Fixed

- **MCPO broken image pin — resolved.** The chart referenced
  `ghcr.io/open-webui/mcpo:0.0.20`, a tag that does not exist upstream
  (`ImagePullBackOff` whenever `mcpo.enabled=true`; masked by the default
  `mcpo.enabled: false`). Now pinned to the `main` channel by immutable digest
  (`main@sha256:1e82c955…`) across `values.yaml`, `sbom.cdx.json`, `zarf.yaml`,
  and the ADR-002 table — so all 14 images are digest-pinned, which is what lets
  the new digest-parity check run with no exceptions. Supersedes the prior
  "out-of-scope flag".
- **Valkey persistence was silently ignored.** `valkey.persistence.enabled=true`
  had no effect — the data volume was hard-coded to `emptyDir`, so documented
  Stream durability never worked. Now backed by a PVC (see Added).
- **LangGraph `ingress` was never rendered.** `langgraph.ingress` existed in
  `values.yaml` and the docs, but the deployment template omitted the Ingress
  resource entirely; it is now wired (alongside the new `httpRoute`).
- **Ingestion worker `checksum/config`** hashed only `ingestionWorker.env`, so
  edits to the worker code never triggered a pod rollout. It now hashes the
  worker source and requirements as well.

### Added (carried from earlier unreleased work)

- Reference architecture document (`docs/architecture/REFERENCE.md`) codifying the
  best-practice patterns for the conversational + RAG flow (Open WebUI) and the
  agentic flow (LangGraph), including design principles, anti-patterns, and a
  production hardening checklist. Linked from `README.md`, `HOWTO.md` (§4, §8, §9),
  and the Open WebUI / LangGraph / MCPO component pages.
- **ADR-001** (`docs/architecture/ADR-001-component-version-management.md`) capturing
  the 2026-05-24 codebase index + upstream validation. Records the recurring
  SBOM/Zarf-vs-`values.yaml` drift pattern, lists the five resynced components,
  enumerates upstream patch lag for four images, and sets the policy that
  documentation referencing image tags is treated as code and refreshed in lockstep
  with `values.yaml`. Linked from `README.md` documentation table.
- **CI image-tag parity check** in `.github/workflows/lint.yaml` `sbom-validate`
  job: a new step "Verify image-tag parity across values.yaml, sbom.cdx.json,
  zarf.yaml" enforces per-component version equality across all three files,
  flags purl-vs-version internal desync inside the SBOM, reports basename
  collisions, and lists components missing from any of the three sources.
  Closes the ADR-001 §Consequences follow-up ("file a follow-up if the next
  audit finds drift again"). The Zarf side is covered by the same step
  rather than a separate job (no Docker pulls required for repo-only
  comparison).
- **ADR-002** (`docs/architecture/ADR-002-image-digest-pinning.md`) accepted:
  every chart-deployed image now carries both `tag:` and `digest:` in
  `values.yaml`. Templates render `repo@digest` when `digest` is non-empty,
  falling back to `repo:tag` otherwise (same pattern previously used only by
  `openTerminal`). 13 of 14 images carry initial SHA-256 digests captured
  2026-05-27 via registry-native HTTP HEAD; MCPO's `digest` is empty pending
  resolution of an upstream tag issue (see Fixed section). Renovate
  configuration extended with `pinDigests: true` on the `helm-values` manager
  so digest and tag updates flow together. SBOM components carry the digest
  in a CycloneDX `hashes` array; Zarf images use `repo:tag@sha256:...` syntax.
  `values.schema.json` extended with a `digest` field on the `image` def
  (pattern `^$|^sha256:[a-f0-9]{64}$`).

### Changed (carried from earlier unreleased work)

- README architecture diagram: clarified legend (default-enabled vs opt-in vs
  conditional edges) and marked Authelia → Valkey / Postgres edges as conditional
  to match the chart's storage/session toggles.
- **OTel Collector image** bumped from `0.152.0` to `0.153.0` across `values.yaml`,
  `sbom.cdx.json`, `zarf.yaml`, and `docs/compliance/LICENSE_COMPLIANCE.md`.
  Absorbs Dependabot PR #106 with atomic SBOM/Zarf sync per ADR-001 §Decision[1].
  Upstream review (v0.153.0 release notes): no breaking changes affect this chart;
  the v0.153.0 default `error_mode` change for `filter`/`transform` processors does
  not apply because the chart uses the `redaction` processor instead. Note:
  `resourcedetection` is deprecated upstream in favour of `resource_detection`;
  the old name still works in v0.153.0 but should be renamed in a follow-up PR.
- **SearXNG image** bumped from `2026.4.11-9e08a6771` to `2026.5.26-0037d43d8`
  across `values.yaml`, `sbom.cdx.json`, `zarf.yaml`, and
  `docs/compliance/LICENSE_COMPLIANCE.md`. Closes the ~6-week upstream lag
  identified in ADR-001 §3 (informational at audit time). The chart's SearXNG
  config (`use_default_settings: true` with minimal overrides:
  `server.limiter: false`, `image_proxy: false`, `safe_search: 0`,
  `formats: [html, json]`, `general.enable_metrics: false`) is unaffected by
  upstream changes in this window. SearXNG uses continuous-release tagged
  container images; no formal release notes exist for individual tags. Smoke
  verification: `helm template` renders unchanged line counts; chart-testing
  expected to pass at PR time.
- **Authelia image** pinned from floating `4.39` to exact `4.39.20` across
  `values.yaml`, `sbom.cdx.json`, `zarf.yaml`,
  `docs/compliance/LICENSE_COMPLIANCE.md`, and `HOWTO.md` §12.2 docker-run
  example. Closes the ADR-001 §3 exact-pin lag (one patch newer than ADR-001's
  `v4.39.19` reference; `4.39.20` released 2026-05-26). v4.39.20 fixes two
  upstream security advisories: edge-case access-control rule domain
  canonicalisation, and missing username canonicalisation in LDAP Basic Auth.
  Behavioural change: access-control domain matching is now case-insensitive,
  which may affect deployments that relied on case-sensitive matching. The
  chart ships no preset Authelia access rules; user-managed rules should be
  reviewed during the next Authelia config touchpoint.

### Fixed (carried from earlier unreleased work)

- **SBOM drift fixed (again)** — five image versions in `sbom.cdx.json` were lagging
  `values.yaml`. Resynced: open-webui `v0.9.2 → v0.9.5`, ollama `0.23.1 → 0.24.0`,
  qdrant `v1.17.1 → v1.18.0`, valkey `8.1.6 → 9.1.0`, opentelemetry-collector-contrib
  `0.151.0 → 0.152.0`. Refreshed BOM `serialNumber` and `metadata.timestamp` (2026-05-24).
- **Zarf drift fixed (again)** — same five stale image references in `zarf.yaml`
  resynced to match `values.yaml`.
- **LICENSE_COMPLIANCE.md** — chart-version header updated from 2.0.0 (last reviewed
  2026-03-26) to 2.2.0 (2026-05-24). Image-version cells refreshed for all 14 components
  in the license matrix to match `values.yaml`.
- **EU_COMPLIANCE_CHECK.md** — header updated from chart 2.0.0 / appVersion 2026.1 to
  2.2.0 / 2026.4; date marked as re-validated on 2026-05-24.
- **ENTERPRISE_EVALUATION.md** — header and body bumped from chart 2.0.0 / appVersion
  2026.1 to 2.2.0 / 2026.4.
- **HOWTO.md §1.3 air-gap example** — stale image references (`v0.8.10`, `0.18.2`,
  `0.18.0`) replaced with current pins (`v0.9.5`, `0.24.0`).
- **docs/components/tika.md** — upstream REST API URL repointed from `3.1.1` to `3.3.1`
  to match the deployed image tag.
- **docs/governance/CONTROLS.md** — registry version footer bumped from 2.0 to 2.2 to
  track `Chart.yaml`.
- **SBOM and Zarf drift closure (qdrant `v1.18.0` → `v1.18.1`)**: PR #107 bumped
  `values.yaml` only, reintroducing the drift pattern ADR-001 §Decision[1] guards
  against. Resynced `sbom.cdx.json` and `zarf.yaml` to `v1.18.1`; refreshed BOM
  `serialNumber` and `metadata.timestamp` (2026-05-27). `docs/compliance/LICENSE_COMPLIANCE.md`
  qdrant row updated to match.
- **renovate.json5 ownership comment** corrected. The previous comment claimed
  Dependabot owns "Dockerfile/container deps" exclusively, but Dependabot's
  `docker` ecosystem also opens PRs against `values.yaml` (PR #106 is the
  empirical example: a bot-only `values.yaml` bump that would have produced
  drift without the absorption commit). New comment describes the actual
  dual-bot overlap, the rate-limit-based tolerance, and the preference for
  Renovate's PR when both bots fire on the same image.
- **README Kubernetes badge** was realigned to `1.25+` during this cycle; it is
  raised to `1.27+` in 2.3.0 (see Changed → `kubeVersion`) now that the chart
  emits PDB `unhealthyPodEvictionPolicy` (GA 1.27).

## [2.2.0] - 2026-04-29

### Added

- **PrometheusRule template** (`templates/otel/prometheusrules.yaml`) shipping curated alerting rules
  for pod health (CrashLoop, OOMKilled, ImagePullBackOff), deployment/statefulset availability,
  component SLOs (Open WebUI 5xx rate, Ollama/Qdrant scrape liveness), and security posture
  (NetworkPolicy default-deny, privileged container detection). Opt-in via
  `global.prometheusRule.enabled`, with per-group toggles, configurable alert prefix, severity
  routing labels, and PrometheusRule selector labels.
- **Helm OCI release workflow** (`.github/workflows/release.yaml`) that publishes the chart to
  `oci://ghcr.io/<owner>/charts/ai-stack` on `v*.*.*` tags, verifies that the tag matches
  `Chart.yaml`, generates a signed build-provenance attestation, attaches the packaged chart and
  `sbom.cdx.json` to a GitHub Release, and exposes a `workflow_dispatch` dry-run mode.
- Authelia component added to the Zarf air-gap package (previously missing) so OIDC/SSO can be
  installed offline alongside the rest of the stack.
- `prometheusRule` block in `values.schema.json` so Draft 2020-12 validation catches typos in
  the new alerting configuration.
- New `appVersion` and `Kubernetes` badges in README header.
- Consolidated `Documentation` navigation table in README, linking HOWTO, component docs index,
  CHANGELOG, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, Enterprise Evaluation, and SBOM.
- Per-component reference pages under `docs/components/` (openwebui, ollama, qdrant, tika, searxng,
  valkey, otel, authelia, langgraph, workbench, mcpo, open-terminal, postgres, ingestion-worker)
  plus an index (`docs/components/README.md`).
- `values.schema.json` — JSON Schema Draft 2020-12 validation for user overrides. Catches typos in
  `global.profile`, `postgres.mode`, `global.podSecurityStandard`, image pull policies, and
  non-boolean `enabled` values at `helm install`/`helm template` time.
- Quick-reference "Symptom → Diagnosis" decision table at the top of HOWTO §19 Troubleshooting.

### Changed

- Bumped chart version 2.1.1 → 2.2.0 and `appVersion` 2026.2 → 2026.4.
- `kubeconform` step in CI now also skips the `PrometheusRule` CRD (ships with the Prometheus
  Operator, not stock Kubernetes).

### Fixed

- **SBOM drift fixed** — `sbom.cdx.json` was lagging behind `values.yaml` for five components.
  Re-synced versions to match the live chart: open-webui v0.8.12 → v0.9.2, ollama 0.20.5 → 0.22.0,
  opentelemetry-collector-contrib 0.149.0 → 0.151.0, langgraph-server 0.7-py3.12 → 0.8-py3.12,
  python (ingestion-worker base) 3.12-slim → 3.14-slim. Refreshed BOM `serialNumber`,
  `metadata.timestamp`, and chart self-reference version.
- **Zarf package drift fixed** — `zarf.yaml` had the same five stale image references and a stale
  `version: 2.1.1` on every chart entry. All synchronised with `values.yaml` and bumped to 2.2.0.
- Corrected README Helm Chart badge from v2.0.0 to v2.1.1 to match `Chart.yaml`.
- Replaced plain-text section reference (`HOWTO.md §10`) in README Disaster Recovery with a proper
  markdown anchor link.
- Converted the three `§1`/`§2`/`§3` plain-text references to `EU_OPERATIONS_GUIDE.md` in
  HOWTO §18 (EU Compliance) into markdown anchor links.

## [2.1.1] - 2026-04-12

### Changed

- Updated Ollama image tag from 0.20.3 to 0.20.5
- Updated SearXNG image tag from 2026.4.5-474b0a55b to 2026.4.11-9e08a6771
- Updated Open Terminal image tag from 0.11.32 to 0.11.34
- Bumped chart version from 2.1.0 to 2.1.1

### Fixed

- Synced zarf.yaml Ollama image from 0.20.2 to 0.20.5 to match values.yaml
- Synced SBOM Ollama version from 0.20.2 to 0.20.5 to match values.yaml
- Synced SBOM and zarf.yaml PostgreSQL version from 17-alpine to 18-alpine to match values.yaml
- Updated SBOM ai-stack chart metadata version from 1.0.0 to 2.1.1
- Refreshed SBOM timestamp to 2026-04-12
- Updated supported version in SECURITY.md to 2.1.x
- Bumped Zarf package metadata.version and all charts[].version from 1.0.0 to 2.1.1
- Regenerated SBOM serialNumber for the new BOM instance

## [2.1.0] - 2026-04-06

### Changed

- Updated Open WebUI image tag from v0.8.10 to v0.8.12
- Updated Ollama image tag from 0.18.2 to 0.20.2
- Updated Qdrant image tag from v1.17.0 to v1.17.1
- Updated SearXNG image tag from 2026.3.23-2c1ce3bd3 to 2026.4.5-474b0a55b
- Updated Open Terminal image tag from 0.11.27 to 0.11.32
- Updated Valkey image tag from 8.1.1 to 8.1.6
- Updated OTel Collector image tag from 0.148.0 to 0.149.0
- Updated Syft from v1.21.0 to v1.42.3 in CI pipeline
- Updated Grype from v0.91.0 to v0.110.0 in CI pipeline
- Bumped chart version from 2.0.0 to 2.1.0

### Fixed

- Fixed MCPO image tag from 0.2.0 to 0.0.20 to match actual GHCR release tags
- Fixed SBOM Python ingestion-worker version from 3.13-slim to 3.12-slim to match values.yaml
- Fixed SBOM Valkey version from 8.1 to 8.1.6 to match values.yaml pinned version

## [2.0.0] - 2026-04-06

### Changed

- Renumbered HOWTO table of contents and section headers for consistency
- Updated Ollama image tag from 0.18.1 to 0.18.2
- Updated Kubernetes support statement: 1.27+ (tested against 1.32)
- Corrected tier classification system reference: T0–T2
- Updated all compliance template versions from 1.0 to 2.0
- Updated supported version in SECURITY.md to 2.0.x
- Bumped chart version from 1.0.0 to 2.0.0

### Fixed

- Fixed subsection numbering in Upgrading, ArgoCD, and Compliance documentation sections
- Fixed numbering in EU_OPERATIONS_GUIDE roadmap
- Fixed section numbering inconsistencies throughout documentation

## [1.0.0] - 2026-03-01

### Added

- Initial release of the ai-stack Helm chart
- Open WebUI, Ollama, Qdrant, Tika, SearXNG, Valkey as core components
- Optional components: LangGraph, Workbench, MCPO, Open Terminal, Authelia, Ingestion Worker
- PostgreSQL support: standalone, CloudNativePG, and external modes
- PSA restricted baseline enforcement
- Default-deny NetworkPolicy with per-component allowlists
- OpenTelemetry Collector with PII redaction
- CycloneDX SBOM (sbom.cdx.json)
- CI pipeline: helm-lint, chart-testing, sbom-validate, syft-sbom, cve-scan, kubeconform
- EU compliance documentation: DPIA, DSAR, incident response, ROPA templates
- Governance controls registry (docs/governance/CONTROLS.md)
- ArgoCD application manifests for lab and production profiles
- Dependabot configuration for GitHub Actions
- Structured issue and PR templates

[Unreleased]: https://github.com/rmednitzer/ai-stack/compare/v2.12.0...HEAD
[2.12.0]: https://github.com/rmednitzer/ai-stack/compare/v2.11.0...v2.12.0
[2.11.0]: https://github.com/rmednitzer/ai-stack/compare/v2.10.0...v2.11.0
[2.10.0]: https://github.com/rmednitzer/ai-stack/compare/v2.9.0...v2.10.0
[2.9.0]: https://github.com/rmednitzer/ai-stack/compare/v2.8.0...v2.9.0
[2.8.0]: https://github.com/rmednitzer/ai-stack/compare/v2.7.0...v2.8.0
[2.7.0]: https://github.com/rmednitzer/ai-stack/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/rmednitzer/ai-stack/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/rmednitzer/ai-stack/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/rmednitzer/ai-stack/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/rmednitzer/ai-stack/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/rmednitzer/ai-stack/compare/v2.1.1...v2.2.0
[2.1.1]: https://github.com/rmednitzer/ai-stack/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/rmednitzer/ai-stack/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/rmednitzer/ai-stack/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/rmednitzer/ai-stack/releases/tag/v1.0.0
