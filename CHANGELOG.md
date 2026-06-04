# Changelog

All notable changes to the ai-stack Helm chart will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/rmednitzer/ai-stack/compare/v2.4.0...HEAD
[2.4.0]: https://github.com/rmednitzer/ai-stack/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/rmednitzer/ai-stack/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/rmednitzer/ai-stack/compare/v2.1.1...v2.2.0
[2.1.1]: https://github.com/rmednitzer/ai-stack/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/rmednitzer/ai-stack/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/rmednitzer/ai-stack/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/rmednitzer/ai-stack/releases/tag/v1.0.0
