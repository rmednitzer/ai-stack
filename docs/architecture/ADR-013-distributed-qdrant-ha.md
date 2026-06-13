# ADR-013 — Distributed Qdrant high availability (gated cluster mode)

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Roman Mednitzer (chart maintainer)
- **Chart version at acceptance:** 2.12.0 (`appVersion` 2026.5); ships in the next minor release
- **Supersedes:** none (additive — a new opt-in topology beside the existing
  single-node Deployment; the default render is byte-identical, and no existing
  values key or template-contract signature is removed or changed)

---

## Context

Qdrant shipped as a single `Deployment` with one `ReadWriteOnce` PVC and no
replication (`templates/qdrant/deployment.yaml`). A node or pod loss interrupts
retrieval, and recovery is from backup, not failover. This is the residual
single-node-store gap tracked as `LIMITATIONS.md` L7 and runbook B8.

Qdrant supports distributed deployment: multiple peers form a cluster over a Raft
consensus protocol, sharing collection shards. The known-good Kubernetes shape
(confirmed against Qdrant's distributed-deployment documentation and the upstream
`qdrant/qdrant-helm` chart) is a StatefulSet behind a headless Service:

- Peers discover each other by stable per-pod DNS, so the Service is headless
  (`clusterIP: None`) with `publishNotReadyAddresses: true` (peers must resolve
  one another during bootstrap, before they pass readiness).
- Bootstrap is ordinal-driven: pod-0 forms the cluster (`--uri <self>`); pods 1+
  join it (`--bootstrap <pod-0> --uri <self>`). The ordinal comes from the pod
  hostname (`${HOSTNAME##*-}`).
- Inter-peer traffic uses a p2p port (6335) that Qdrant documents must be isolated
  from outside access, since it carries write-capable consensus operations.
- Crucially, **`replication_factor` is a per-collection property set at creation
  time**, not a cluster-wide config knob. A cluster with single-replica collections
  is *not* data-HA: losing the node holding a shard's only copy loses that shard.
  Surviving a node loss requires both the topology *and* collections created with
  `replication_factor >= 2`.

Constraints that shaped the decision: never weaken a default; `values.yaml` is the
source of truth; surgical change over rewrite; defaulting to the current single
node (runbook B8); every security-relevant template change carries a `tests/`
assertion; the p2p port must stay confined under the default-deny NetworkPolicy.

## Decision

1. **Gated cluster mode, default off.** Add a `qdrant.cluster` block
   (`enabled: false`, `replicas: 3`, `replicationFactor: 2`, `shardNumber: ""`,
   `p2pPort: 6335`). When off, `templates/qdrant/deployment.yaml` renders exactly
   the prior single-node Deployment + shared PVC. When on, that Deployment and its
   shared PVC are suppressed and `templates/qdrant/statefulset.yaml` renders
   instead. The client `Service` is shared by both modes (it selects the same
   component labels), so consumers' `QDRANT_URI` is unchanged across the switch.

2. **StatefulSet + headless Service.** The StatefulSet uses `serviceName` =
   `<release>-qdrant-headless`, `podManagementPolicy: OrderedReady` (pod-0 must be
   Ready before pod-1 bootstraps against it), per-pod `volumeClaimTemplates`, and
   the chart's existing restricted security posture (read-only root, non-root UID
   1000, dropped capabilities, no token automount). The container `command`
   inlines Qdrant's documented bootstrap shell (the same logic as the upstream
   chart's `initialize.sh`): derive the ordinal, exec the image's own
   `./entrypoint.sh` with `--uri`/`--bootstrap`. Cluster mode is enabled by
   `QDRANT__CLUSTER__ENABLED=true` and `QDRANT__CLUSTER__P2P__PORT` (Qdrant's
   `__`-nested env override convention, already used by the chart for
   `QDRANT__STORAGE__*`). A soft pod anti-affinity prefers spreading peers across
   nodes. The headless Service is `clusterIP: None` +
   `publishNotReadyAddresses: true`, exposing http/grpc/p2p for peer DNS only.

3. **Data HA wired through the ingestion worker.** Because replication is
   per-collection at creation, the worker reads `QDRANT_REPLICATION_FACTOR` /
   `QDRANT_SHARD_NUMBER` (optional positive ints; absent = today's behaviour) and
   includes them in the create-collection body. The chart sets these on the worker
   automatically when `qdrant.cluster.enabled`, sourced from
   `qdrant.cluster.replicationFactor` / `shardNumber`, so collections the worker
   owns are replicated without operator action.

4. **p2p confinement.** The Qdrant NetworkPolicy gains, only under cluster mode, an
   `Egress` policy type plus matched ingress/egress rules allowing the p2p port
   *between qdrant pods only*. The port is never accepted from clients and never
   surfaced on the client Service. The existing `maxUnavailable: 1` PDB already
   selects these pods, so it protects the consensus quorum unchanged.

5. **Tests.** `tests/qdrant_cluster_test.yaml` pins: single-node default (no
   StatefulSet, ingress-only NetworkPolicy); cluster topology (StatefulSet replicas
   / serviceName / OrderedReady / volumeClaimTemplates, the bootstrap args, cluster
   env, p2p port, restricted security context); the headless Service shape; the
   p2p NetworkPolicy ingress + egress; and the worker replication-env wiring. The
   worker create-body is covered in `files/ingestion-worker/test_worker.py`.

## Consequences

**Positive**

- Operators who need it get a real HA retrieval tier (Raft quorum, replicated
  shards, peer failover) from one flag, validated against Qdrant's documented
  deployment model, without touching consumer configuration.
- The default path is unchanged and proven: single-node users see no new resources
  and no behavioural drift; the switch is reversible by flipping one flag.
- Data HA is not a footgun: the chart wires `replication_factor >= 2` through the
  worker automatically, closing the most common "clustered but not replicated"
  mistake for the path the chart owns.

**Negative**

- Cluster mode is a genuinely more complex topology (StatefulSet bootstrap, Raft
  consensus, per-pod PVCs) with more failure modes than a single pod; the runbook
  and component doc carry the operator caveats.
- The shipped anti-affinity is *soft*, so on a constrained cluster Kubernetes may
  co-locate peers and a single node loss could still drop a shard's replicas.
  Guaranteed HA requires the operator to spread peers (hard anti-affinity, topology
  spread, or node pinning); this is documented, not enforced.
- Collections created outside the worker (e.g. Open WebUI manages its own Qdrant
  collections) are not auto-replicated; their replication must be set at creation
  by whoever creates them.

**Neutral**

- No image, `Chart.yaml` version, SBOM, or `zarf.yaml` change: the work is a new
  template, values, a worker code path, tests, and docs. It accumulates in
  `CHANGELOG.md` `[Unreleased]` for the next release.
- The cluster `command` overrides the image entrypoint to inject `--uri` /
  `--bootstrap`; it relies on the image's `/qdrant` WORKDIR (stable, the image is
  digest-pinned) and execs the image's own `entrypoint.sh`, so future image flags
  still apply.

## Alternatives considered and rejected

- **Always use a StatefulSet (replicas=1 by default).** Rejected: it would change
  the default-path resource kind and the PVC model (shared claim →
  `volumeClaimTemplates`) for every existing single-node user, a migration hazard
  for a release whose intent is "default to the current single node." A separate,
  opt-in StatefulSet keeps the default byte-identical.
- **Mount the bootstrap as a ConfigMap `initialize.sh` (as the upstream chart
  does).** Rejected as unnecessary surface here: the bootstrap is a few lines of
  shell with no per-pod templating beyond names already known at render time;
  inlining it in `command` keeps the logic in one reviewable place and avoids an
  extra mounted file under a read-only root filesystem.
- **Set replication cluster-wide instead of per-collection.** Not possible: Qdrant
  has no cluster-wide replication default; it is a create-time collection property.
  Wiring it through the worker is the only way to make the chart's own collections
  HA without an operator step.
- **Hard anti-affinity / required topology spread by default.** Rejected as the
  default: it turns "enable cluster mode" into "also have >= `replicas` schedulable
  nodes or fail to schedule," a poor first-run experience (e.g. on a single-node
  kind cluster). Soft by default, documented hardening for production HA.
- **Bundle Qdrant snapshot/backup automation (B9) into this change.** Rejected:
  backups are a distinct concern (disaster recovery, not availability) tracked
  separately as B9; folding them in would widen the blast radius of an
  availability-focused change.

## Revisit triggers

- Open WebUI (or another in-chart consumer) begins creating its own Qdrant
  collections on a clustered deployment — extend the auto-replication wiring beyond
  the ingestion worker, or document a required collection-create policy.
- A shipped overlay enables `qdrant.cluster.enabled` — revisit whether the default
  anti-affinity should harden to a required rule / topology spread, and whether the
  p2p port warrants TLS (`QDRANT__CLUSTER__P2P__ENABLE_TLS`) once B7 (mesh mTLS)
  lands.
- Qdrant changes its bootstrap CLI (`--uri` / `--bootstrap`) or image WORKDIR in a
  pinned-tag bump — re-validate the inlined bootstrap against the upstream chart.
- B9 (disaster-recovery backups) is implemented — cross-reference the Qdrant
  snapshot path with the cluster's shard layout.
