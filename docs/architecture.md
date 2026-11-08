# Initial architecture

For the working semantic contract and the distinction between current behavior
and intended record lifecycles, see [epistemic-semantic-contract.md](epistemic-semantic-contract.md).
The planned observation-time and evidence-lifecycle increments are described in
[observation-provenance-lifecycle-plan.md](observation-provenance-lifecycle-plan.md).

CLI or local browser/API → shared application operations → workspace service → SQLite.

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
with a JSON schema, followed by strict local validation. The CLI and browser show the
proposal before asking for acceptance, using shared operations in
`workspace/operations.py`. Acceptance revalidates the reviewed context and
commits under one write transaction; the model call runs outside that transaction. Uncertain/unrelated proposals are not
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

`PRAGMA user_version=3` adds derivation/lineage storage (see below). Version 2
introduced the transactional observation-time migration;
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

## Adversarial validation checkpoint

[Experiment 002](../experiments/002-binary-beta/README.md) validates this contract
without changing the core implementation. Its 12 scenarios exercise fixed
projection inputs, dependency caps, raw-partition recombination, retries,
correction/reinterpretation lineage, withdrawal recovery, CLI restarts, read-only
inspection, legacy annotation, numeric range errors, and transaction rollback.
An exact rational reference checks readout explanations independently of the
projector's floating-point aggregation. Run reports retain input records,
checkpoints, versions, and source hashes; all database work uses temporary stores.

The saved example includes a supplied domain-level exclusion. The workspace still
does not persist exclusions or propagate derived-conclusion eligibility. An
active zero-mass link may yield qualitative `supported` at the quantitative prior;
an above-0.5 mean may coexist with `contested`. Those are documented semantic
differences, not reasons to replace either readout with a truth verdict.

This checkpoint establishes bounded engineering acceptance, not calibration,
source independence, historical as-of replay, or comparative research efficacy.

## Experiment-only replay environment

`experiments/003-evidence-revision/revision_world/` is independent of the core
workspace. It generates immutable JSON source/task schedules and separate private
truth/lineage/scoring records, with a canonical digest binding each pair. A
public-only replay driver exposes detached event prefixes, stops at unanswered
tasks, and requires checkpoint restoration after task four. Actual process
restart behavior is exercised by integration tests.

The offline scorer distinguishes physical correctness from valid justification,
including finite action choices, available-source boundaries, sufficient AND/OR
support sets, unresolved tasks, and retained-control audits. It is not an agent
or a belief policy. The generator's subject-time histories do not implement
temporal inference in `Workspace`.

Methods must receive only serialized views. Complete schedules, private labels,
seeds/manifests and scorer outputs belong to the trusted driver/evaluator. This
is a tested application data boundary, not a sandbox against malicious code.
The experiment now includes H0 (actual Workspace), LWW, filtered rereading and
full rebuilding, a shared deterministic actor, subprocess workers, persisted
method state, logical budgets/cost vectors and detached audits. The trusted
`compare.py` driver scores only after each method finishes. It refuses validation
families; the application boundary is not OS isolation. H0 gains no graph repair
or temporal adjudication. See the [baseline contract](../experiments/003-evidence-revision/baselines.md)
for cost definitions, limitations and next work, and the
[schema contract](../experiments/003-evidence-revision/schema.md).

## Local browser adapter (step 5)

`web/application.py` and `web/server.py` provide the local browser boundary;
packaged plain HTML/CSS/JavaScript lives in `web/static/`. The standard-library
HTTP server binds only to loopback and adds no runtime dependencies. The selected
workspace path is configured at startup, displayed in the UI, and cannot be
changed through an HTTP request. Each operation owns its SQLite connection.

Listing/search/filtering methods live in `Workspace`. Inspection and all evidence
mutations use the existing service policies. The CLI and browser share model
preview/acceptance orchestration, including a consistent context snapshot,
explicit acceptance, rejection of uncertain/unrelated proposals, and atomic
revalidation against changes made during model execution or human review.

Application transactions encompass both service effects and durable browser
request receipts. `Workspace.transaction()` joins an active outer transaction
without committing it; failures propagate to its owner. The additive
`browser_receipts` adapter table is created on the first successful browser
command, without independently changing the core schema version. It stores canonical command
digests and original results so exact retries, including completed acceptances
after restart, do not repeat writes. It is not an evidence or attempt-log table.

Pending previews are bounded and expire in memory. The browser preserves an
unconfirmed command in tab session storage and offers retry after lost responses.
Commands require a per-server request token, checked local Host/Origin, and bounded
JSON; assets have a restrictive content security policy and render record text
as text, not HTML. This local research adapter is not a remote deployment server.

Searchable selectors replace manual UUID copying. Views expose claims,
observations, active/withdrawn evidence, provenance, revision history and
experimental projection metadata. Report correction, reinterpretation and
withdrawal preserve the existing distinctions. General chat, dependency repair
views and persistent logging of declined/failed model attempts remain future work.

Automated application, CLI parity, concurrency, rollback and in-memory HTTP
handler tests pass. Live server/browser acceptance is pending because the
implementation sandbox denied socket creation; see
[browser startup and acceptance](browser-workspace.md).

## Derivation domain (step 6 slice 1)

`domain/derivation.py` defines immutable signed proposition references,
justifications, and validated graph snapshots under `derivation-v1`. Premises
within a justification are conjunctive; separate justifications for the same
signed conclusion are alternatives. Snapshot validation rejects unknown IDs and
cycles across the complete graph. Structural matching uses only explicitly
supplied available premises and performs no transitive inference or belief update.
See [the derivation/lineage contract](derivation-lineage-contract.md) for polarity,
conflict, attribution, history and future storage boundaries. The domain module is now used by persistence and shared Workspace/CLI/API
operations; it remains independent of projection and belief-update policies.

## Derivation and origin persistence (step 6 slice 2)

`workspace/derivation_storage.py` provides `DerivationStore`, a standalone
connection-owning persistence boundary. The additive schema-3 migration creates
immutable justification and lineage-event tables without rewriting earlier data.
Premises are canonical JSON within one immutable justification row. All references
and graph acyclicity are validated against the actual workspace under a write lock.
Origin lineage assigns observations to explicitly asserted groups; it does not
change evidence impact clusters. Assignment, merge and reversal events record
before/after memberships and effective predecessor events. Overlapping events
must unwind in dependency order; independent later events remain untouched.

Reads reconstruct validated graph/lineage snapshots. Exact retries are idempotent,
stale lineage revisions fail, and two new ledger digests have explicit input
contracts. Legacy projection policies and digests retain their old meaning.
Migration preservation, failure rollback, restart and concurrency tests pass.
Shared Workspace/application integration is implemented in slice 3; GUI integration is slice 4.
See [the persistence contract](derivation-lineage-contract.md) for exact semantics.

## Shared derivation/lineage operations (step 6 slice 3)

Workspace now exposes the storage operations and decoded, labeled whole-workspace
inspection. `DerivationStore.for_workspace` borrows the same connection and
transaction owner without closing it. `Workspace.atomic()` composes evidence,
derivation and lineage writes under one lock/commit; failures must propagate to
roll back the outer transaction. Read-only inspection captures the ledger and
record labels in one snapshot. Existing inspection shapes and belief policies
remain unchanged. No additional schema change is required.

CLI commands and the local API call these shared operations. API input validation
covers signed references, bounded lists and integer revisions. Lineage conflicts
return HTTP 409. Browser command receipts commit with the operation, including
rollback if receipt persistence fails. See the [interface contract and commands](derivation-lineage-contract.md).
Slice 4 adds GUI controls in `web/static/structure.js`: signed premise selection,
AND/OR justification inspection, observation origin assignment, and merge/reversal
review with before/after memberships. Forms use the existing command receipt
mechanism and expected lineage revision. A 409 blocks resubmission until a fresh
review is loaded. Supplied justifications do not yet propagate beliefs.
