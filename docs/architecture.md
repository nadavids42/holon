# Initial architecture

For the working semantic contract and the distinction between current behavior
and intended record lifecycles, see [epistemic-semantic-contract.md](epistemic-semantic-contract.md).
The planned observation-time and evidence-lifecycle increments are described in
[observation-provenance-lifecycle-plan.md](observation-provenance-lifecycle-plan.md).

CLI → workspace service → SQLite.

Domain definitions describe records and deterministic evidence-presence rules.
The caller explicitly identifies a proposition, its shared scope, and the report's
relation. Optional Ollama interpretation proposes a relation; explicit human acceptance is required before a supporting or contradicting link is stored.
Observations, evidence links, and belief revisions commit in one transaction.
Current state is the latest revision; prior revisions retain their evidence IDs.
Recording timestamps are UTC ingestion times. An optional caller-supplied
`observed_at` records an observation instant separately, normalized to UTC;
unknown and legacy values remain null. It does not imply subject time or change
the current model prompt or belief policies. Scope is caller-supplied text.
The database is a research prototype store, not a tamper-proof audit system.

## Evidence lifecycle

`withdraw` appends attribution, reason, timestamp, and an optional replacement
link in the `withdrawals` table. Original observations, interpretations, evidence,
and revisions remain intact. `correct` creates a new observation/evidence link
and withdraws the old link in the same transaction as the resulting revision.
Failures roll back the entire correction. Attribution is caller-supplied.

`active-presence-v2` computes status from evidence without withdrawal records.
Support alone yields `supported`, contradiction alone `opposed`, both `contested`,
and no active links `insufficient_evidence`. Each new revision lists its active
evidence IDs; old revisions preserve their original IDs and policy labels.
Inspection returns all links with active flags and withdrawal metadata.

`reinterpret` atomically withdraws one evidence link and creates a replacement
for the same observation and proposition. It preserves the original link and
its interpretation, retains the original cluster, attribution, migration origin,
and (unless explicitly overridden) impact mass. Manual attribution is stored on
the withdrawal; accepted model proposals retain their separate model rationale.
Other links to the observation are unaffected. Missing legacy impact metadata
requires explicit annotation before reinterpretation. Model preview happens
outside the transaction and the original link is checked again on commit.

Opening an older store adds lifecycle tables and widens the revisions status
constraint in an explicit transaction, preserving revision sequences and content.
This is a targeted prototype migration; a general versioned migration system
belongs to the binary Beta persistence slice. Integration tests cover migration,
restart persistence, lifecycle commands, validation, and failed-correction rollback.

## Interpretation boundary

An observation can also be recorded independently with `observe`, inspected
with `inspect-observation`, and linked to multiple propositions with `link` or
the preview-and-accept `interpret-observation` workflow. A new link, its impact
metadata, and revision commit atomically. A second active link for the same
observation/proposition is rejected after checking for an exact event-key retry.
Historical duplicates remain inspectable and withdrawable. Link event keys use
the existing source/proposition namespace with a distinct operation digest.
Standalone observations are distinct per call and have no event-key retry.
The original one-step report and interpret workflows remain atomic.

`inference/inference.py` defines a provider-independent protocol and validated
proposal. `inference/ollama.py` uses Ollama's non-streaming `/api/chat` endpoint
with a JSON schema, followed by strict local validation. The CLI shows the
proposal before asking for acceptance. Uncertain/unrelated proposals are not
stored. Failed and declined attempts are not retained in this checkpoint.
Accepted interpretation metadata is stored atomically with the original report,
evidence, and belief revision in an additive `interpretations` table. Direct
structured reports continue to work without interpretation metadata.

The adapter follows https://docs.ollama.com/api/chat. Automated adapter/CLI tests
mock the transport/model; they do not establish live model classification quality.

## Pure binary Beta projection

`domain/projection.py` supplies immutable `ProjectionPolicy`,
`ProjectionEvidence`, `ClusterSummary`, and `ProjectionResult` types plus
`project_binary(proposition_id, evidence, policy)`. It operates only on supplied
inputs, without storage access, model calls, time reads, or status changes.
Workspace projection and optional inspection now call this API from one SQLite snapshot.

The experimental default uses Beta(1,1) and caps each cluster's support and
contradiction mass separately at one. Unit mass means stipulated impact,
not calibrated confidence. Callers explicitly supply cluster membership;
the projector does not infer independent sources. Distinct records with repeated
content can share a cluster; duplicate evidence IDs are rejected as malformed
snapshots. Mixed propositions are also rejected.

Results retain raw/effective mass, cluster multipliers, contributing IDs,
withdrawn IDs, exclusions with reasons, posterior mean/variance, evidence strength,
and concentration including the prior. Opposing mass and conflict balance
describe disagreement separately from posterior variance. No threshold assigns
commitment or resolves conflict. Active count includes excluded active links;
withdrawn and excluded counts are disjoint, with withdrawal taking precedence.
Zero-mass active eligible links remain in provenance but add no strength.

Aggregation sorts evidence and clusters and uses stable summation. Reproject
combined raw ledger partitions rather than summing capped projections. Invalid
numeric inputs and aggregate overflow raise ValueError. The current policy has
no decay or learned reliability. Persistent metadata and legacy replay coverage are described below.


## Projection persistence and read contract

`PRAGMA user_version=2` includes the transactional observation-time migration;
version 1 introduced projection metadata. Original
records and revision IDs survive the upgrade. `projection_policies` stores an
immutable canonical policy payload/digest; `evidence_impact` stores mass semantics,
cluster attribution, retry identity, and optional migration origin. Attribution
and assumptions live in `impact_migrations`. SQLite triggers reject updates and
deletes of these metadata records; this remains a research store, not a tamper-proof
ledger. No source reliability is inferred.

`Workspace.project` and `inspect(..., projection_policy=...)` use a consistent
snapshot and create no revisions or persisted confidence values. Policy and
ledger digests accompany results. Any missing/unsupported impact metadata blocks
the quantitative readout and reports incomplete coverage, including retained
withdrawn records. Explicit legacy annotation produces approximate coverage.
There is no projection cache or historical as-of query. Schema creation/upgrade
can write on opening an old store; projection reads on an initialized store do not.
The existing ledger digest does not include `observed_at`; it is not a complete
provenance digest. Versioned request digests include known observation times;
unknown-time requests retain the legacy digest format for retry compatibility.

Reports and corrections commit impact metadata atomically with the existing
lifecycle records. Source/proposition-scoped optional event keys make identical
retries idempotent; conflicting requests fail. Corrections preserve lineage,
including source-based lineage for legacy links. Explicit shared clusters require
actor/reason and share a namespace distinct from automatic source clusters.
