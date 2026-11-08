# Derivation and lineage contract

Contracts: `derivation-v1`, `origin-lineage-v1`. Step 6 slices 1–3 implemented 2026-11-07; slice 4 implemented 2026-11-08 (live GUI acceptance pending).

This slice defines immutable domain records and structural validation in
`src/holon/domain/derivation.py`. It does not persist derivations, change evidence
eligibility, assign belief status, or add Beta impact. The domain model itself does not change SQLite or interface behavior. Slice 2
now adds schema-3 persistence as described below; CLI/API integration is implemented in slice 3; GUI integration is implemented in slice 4. Automatic repair is step 7.

## References, rules, and identity

A `SignedClaim` references one existing scoped proposition ID and an explicit
stance: `supports` or `contradicts`. These names reuse the evidence vocabulary but
this record is not an evidence link. A negative stance is explicit opposition;
missing support does not imply opposition. Observation IDs and evidence IDs are
not interchangeable with proposition IDs. The domain graph checks references
against a supplied set of proposition IDs; the storage boundary now loads
and validates that set against actual persisted propositions.

A `Justification` contains:

| Field | Meaning |
| --- | --- |
| `id` | Stable identity for this particular justification |
| `conclusion` | One signed proposition reference |
| `premises` | Nonempty set, represented as a canonical tuple, of signed proposition references |
| `rule` | Explicit caller-supplied explanation of why these premises jointly justify the conclusion |
| `actor` | Attribution for supplying the justification, not authenticated identity |
| `reason` | Why this justification was recorded |

Every premise in one justification is required (**AND**). Multiple justifications
for the same signed conclusion are alternative sufficient grounds (**OR**).
Positive and negative conclusions have separate alternative sets. A justification
with an empty premise set is rejected: direct evidence remains an observation and
an evidence link, not a premise-free derivation.

Rule text is an attributed assertion, not executable code or a proof checked by
Holon. The caller must supply compatible scopes and a defensible implication.
Free-text scopes are not automatically unified, and no temporal compatibility or
semantic equivalence is inferred. A materially changed rule or premise set needs
a new justification identity. Future persistence must retain originals and record
supersession/withdrawal events, not overwrite accepted meaning.

Example: for the same door and instant, the explicit rule “closed and locked
jointly suffice for secured” uses the `closed` and `locked` propositions as one
justification for `secured`. An `inspection-confirms-secured` proposition can
provide a separate justification under a separately supplied rule. The inspection
proposition would itself have direct evidence; raw report text is not a premise.

## Structural AND/OR checking

`DerivationGraph.matching_justifications(conclusion, available)` returns the
justifications whose complete premise sets appear in an explicitly supplied set
of signed references. Any returned justification is a structurally satisfied
alternative. It does **not** decide which claims are available from evidence.

For the example:

| Supplied available premises | Matching justification |
| --- | --- |
| None | None |
| Closed only | None |
| Closed and locked | Joint door justification |
| Inspection confirms secured | Inspection justification |
| All three | Both justifications, retained separately |

There is no transitive closure: if A justifies B and B justifies C, supplying only
A does not implicitly supply B to the check for C. The later eligibility/repair
policy must explicitly determine usable premises, conflict handling and propagation.
In particular, qualitative `supported` must not be silently treated as truth, nor
`contested` silently converted to a single chosen stance.

Both signs of a premise can be represented explicitly, for example in a declared
rule identifying disagreement for review. Their simultaneous presence does not
justify any unrelated conclusion. This structural helper implements no logical
explosion, negation-as-failure, contraposition, confidence calculation or repair.

Different justification IDs may retain identical premise sets (for example,
separately attributed rule judgments). Their existence does not imply independent
support or create additional mass. Repeated identical premise references within
one justification are rejected; repetitions in the supplied availability set
are simply set membership, not counts.

## Acyclic graph invariant

`DerivationGraph` is a validated immutable snapshot. Its edges run from premise
proposition to conclusion proposition, including all premises and alternatives.
Cycle checking conservatively ignores sign. It rejects self-dependence, negative
self-dependence, indirect cycles and cycles that have an additional grounded
alternative. Allowing grounded cycles is outside this initial contract.

Every referenced proposition must be known; proposition and justification IDs
must be unique within a snapshot. IDs are nonblank and cannot contain surrounding
whitespace. Rule, actor and reason must be nonblank text. Inputs are copied to
immutable collections; premise and justification ordering is canonical. Iterative
topological sorting avoids recursion limits and provides deterministic ordering,
including disconnected propositions. `with_justification` returns a new validated
snapshot; a rejected addition does not mutate the existing graph.

Future writes must validate the candidate graph and commit atomically so concurrent
additions cannot each pass validation while jointly introducing a cycle. The
snapshot API alone does not implement persistence or concurrency control.

## Logical dependence and source lineage are separate

A premise means “this conclusion depends on this signed claim under this rule.”
Copy lineage means “these reports share an origin.” Neither establishes the other,
and neither sets the supporting/contradicting relation of an evidence link.

The next storage design must distinguish:

- Proposition references and derivation justifications (logical dependence).
- Observation/source-origin relationships (copies or shared origins).
- Existing evidence impact cluster assignments (projection assumptions).

No derivation should manufacture a new observation or independent mass merely to
fit the current evidence table. The current immutable `evidence_impact` clusters
and `binary-beta-v1` projection remain unchanged in this slice.

Future reassignment, merge and reversal operations must append events identifying
the affected records, the prior assignment/event, the proposed assignment, actor,
reason and recording time. A reversal refers to the specific mistaken event;
it does not delete history. Multiple overlapping merges and reversals need an
explicit replay rule and conflict behavior before storage implementation. Do not
silently rewrite old clusters or apply new lineage semantics through an old
projection policy. The implemented slice 2 schema/API and replay rules are specified below.

Missing lineage is not a declaration of independence. Provenance completeness
(what origin/dependency relationships are known) must remain separate from
`replay_complete` (whether inputs are reconstructible under a declared contract).
No completeness flag is added by this domain slice. Future digests must version
any added derivation/lineage/time inputs; the legacy projection digest does not
include observation time and must retain its old meaning.

## Implementation slices and handoff

| Slice | Deliverable | Status |
| --- | --- | --- |
| 1 | Derivation contract, immutable records, AND/OR checks, graph validation | Complete |
| 2 | Additive storage design/migration, derivation persistence and append-only lineage event replay | Complete |
| 3 | Shared service operations, migration/restart/rollback/concurrency tests | Complete |
| 4 | GUI premise selection and derivation/lineage inspection | Implemented; live acceptance pending |

Next: live slice 4 acceptance, then step 7 eligibility/repair policy.
Schema-2 records and old projection readouts are preserved by migration tests.
Do not add selective repair before the step 7 policy and tests are specified.

`tests/unit/test_derivation.py` provides 11 tests: joint premises and alternatives,
explicit polarity, no implicit transitive inference, cycles including grounded
alternatives, deterministic diamonds, a 1500-node chain, invalid references and
identities, immutable snapshots, malformed inputs, explicit conflicting premises,
and distinct justifications without mass aggregation. At the slice 1 checkpoint the full suite passed 104
tests. These are engineering checks of structural semantics, not inference quality.

## Slice 2: persistence and origin lineage (2026-11-07)

Implemented in `workspace/derivation_storage.py`. `DerivationStore` owns an
operation-scoped SQLite connection and exposes `add_justification`, `graph`,
`inspect_derivations`, `assign_origin`, `merge_origins`, `reverse_lineage`, and
`lineage`. Use it as a context manager. This is the persistence boundary. Slice 3 now integrates it with
Workspace, the CLI and local API; the GUI integration is slice 4. No eligibility propagation or belief repair occurs.

### Schema and compatibility

The storage opener upgrades schema 0/1/2 to **schema 3** in one transaction.
`derivation_justifications` holds each immutable justification as a single row,
including canonical signed premises, rule, actor/reason, recording time and
`derivation-v1`. The conclusion has a SQL foreign key. Premise references and
acyclicity are validated against actual persisted propositions under the same
`BEGIN IMMEDIATE` write lock as insertion. Premises are one canonical JSON value
so later insertion of child rows cannot silently extend an accepted justification.
`graph()` also validates persisted records when reconstructing the snapshot.

`lineage_events` stores ordered immutable events, their canonical request and
membership changes, actor/reason, recording time, and `origin-lineage-v1`.
Reversals reference an existing event by foreign key. Observation references in
membership payloads are validated against the persisted observation set during
writes and replay. UPDATE/DELETE triggers protect both new tables; this is still
a prototype store, not a tamper-proof ledger against direct SQL access.

No existing table content, observation, evidence sign, revision, impact cluster,
projection policy or old digest is rewritten. Old records get no invented lineage
assignment or derivation. The frozen `tests/fixtures/derivation-schema2.sql` and
its expected projection output verify this on a migrated copy. Older Holon builds
that only understand schema 2 cannot reopen schema 3. Back up a working store
before opening it with the new code; no downgrade is implemented. Only temporary
stores were opened during this implementation session.

### Origin groups and event replay

An origin group is an explicit caller-named shared-origin assertion about
observations. It is not a source-label identity, directed copy edge, evidence sign,
or the old Beta impact cluster. An observation starts with **unknown** origin
(`None`), not its own inferred independent group. `assign_origin` assigns or
reassigns one observation, including back to unknown. A no-op assignment fails.

`merge_origins` takes at least two distinct, nonempty groups and one of them as
the target. It records all current members of all specified groups, including
the target group's members. Each change retains observation ID, before/after
group, and the preceding effective event ID. The membership list is frozen at
that event: there is no permanent group alias and future observations are not
silently included. Same group strings assert a shared origin; different strings
do not prove independent sources. Directional copying, suspected relationships,
and inference of omitted lineage remain later work.

`reverse_lineage` restores the exact prior assignments and effective event heads
of a specific assignment or merge. The target must not have been reversed before,
and must still be the effective head for every affected observation. Otherwise
the reversal fails atomically: later dependent changes must be reversed first.
Overlapping merges therefore unwind in dependency order. Unrelated later changes
are allowed and retained. A new observation assigned to the target group after a
merge is not a member of the earlier event and is unaffected by its reversal.
Reversal events cannot themselves be reversed; a deliberate reapplication is a
new assignment/merge with a new event ID and attribution.

Replay processes events in sequence, validates each prior assignment/effective
head, and reconstructs current assignments. Reversals restore earlier effective
heads while leaving every event in history. Read results include events, heads,
assignments and the last sequence (`revision`). They report provenance completeness
as **unknown**: this module makes no completeness claim about real-world origins.

### Concurrency, retries, and digests

All lineage writes require `expected_revision` from a read snapshot. A stale
revision is rejected under the write lock. Retrying the identical event ID and
canonical request returns the original ID, even if the current revision has
advanced; different content (including a changed expected revision) fails.
The same justification ID and identical domain record are likewise idempotent;
a changed record under an existing ID fails. Retry does not mean reapply an event
that was later reversed: use a new ID for that deliberate action.

Concurrent graph additions cannot independently pass validation and jointly
introduce a cycle. Failed writes and migration failures roll back completely.

Two new, narrowly scoped digests leave legacy projection digests unchanged:

- `derivation-ledger-v1`: sorted persisted justification rows, including their
  recording times and premise references. Not the entire proposition/evidence store.
- `lineage-ledger-v1`: the ordered lineage event ledger including request payloads,
  membership changes and recording times. Adding an unassigned observation does
  not change this digest; changing the event history does, even if a reversal
  restores the same assignments. Observation content/time and current projections
  are not inputs to this digest.

No digest asserts complete provenance. A future combined inference/projection
input digest must explicitly version and include its additional inputs.

### Verification and next slice

14 new persistence/migration tests cover exact schema-2 preservation, failed
migration rollback, shared origin membership, overlapping merge reversal,
independent future members, unknown origin, exact retries, immutable history,
insert rollback, process restart, malformed history, cycles and concurrent writes.
At the slice 2 checkpoint the full suite passed **118 tests**; experiment 002 still passes all 12 scenarios.
Only schema-version expectations were updated in existing migration tests.

Slice 3 (now complete, described below) exposes shared Workspace/application operations and consistent
inspection results over this persistence boundary, with cross-operation atomicity
and interface integration tests. The low-level storage tests in this slice are
necessary to validate migration and write invariants; they did not by themselves complete slice 3.
GUI controls are implemented in slice 4. Justification withdrawal/supersession policy should
be specified before exposing editing of accepted derivations; existing rows must
never be overwritten.

## Slice 3: shared service and interface integration (2026-11-07)

`Workspace` now exposes `add_derivation`, `inspect_derivations`, `assign_origin`,
`merge_origins`, `reverse_lineage`, and `inspect_lineage`. Writes use the same
validated persistence boundary as slice 2, borrowing the Workspace connection.
The borrowed store cannot close that connection and never commits an outer
transaction independently. The standalone `DerivationStore(path)` remains usable.
No new schema migration or change to projection/qualitative policies is required.

### Atomic composition and read contracts

Use `with workspace.atomic():` to compose existing evidence operations and new
derivation/lineage operations. The outer transaction acquires `BEGIN IMMEDIATE`
before validation; nested operations share that lock and commit. Exceptions must
escape the block to roll back the entire composition. This is not a savepoint API:
do not catch a failed inner operation and continue the outer transaction.
`atomic(write=False)` is for a read-only snapshot, not for later lock upgrades.
Model requests and user review must remain outside write transactions.

`inspect_derivations()` returns decoded `justifications` (nested `conclusion` and
`premises` rather than JSON strings), proposition labels/scopes, topological order,
contract version and ledger digest. `inspect_lineage()` returns current assignments,
effective heads, revision, events with decoded `request`, observation records,
contract version, digest and unknown provenance completeness. Each inspection uses
one database snapshot, including labels, and neither creates revisions nor writes
history. Existing proposition/evidence inspection response shapes remain unchanged.

These are **whole-workspace** reads. Digests still use slice 2's raw persisted
ledger contract: request JSON is canonical text for lineage hashing and premise
JSON is canonical text for derivation hashing. Decoding presentation fields does
not define a new digest, and label/content arrays are not additional digest inputs.
Do not interpret the lineage inspection's decoded events as the low-level replay
input without restoring the canonical `request_json` field.

### CLI and local API

New CLI commands:

- `derive PROPOSITION_ID --id JUSTIFICATION_ID --premise PREMISE_ID supports
  --rule TEXT --actor NAME --reason TEXT` (repeat `--premise ID RELATION` for AND
  premises; `--relation` selects conclusion polarity, default `supports`).
- `inspect-derivations` and `inspect-lineage`.
- `assign-origin OBSERVATION_ID --group GROUP --event-id ID --actor NAME
  --reason TEXT --expected-revision N`; use `--unknown` instead of `--group` to
  explicitly clear the origin assignment.
- `merge-origins --group GROUP_A --group GROUP_B --target GROUP_A --event-id ID
  --actor NAME --reason TEXT --expected-revision N`.
- `reverse-lineage TARGET_EVENT_ID --event-id ID --actor NAME --reason TEXT
  --expected-revision N`.

All accept the existing global `--db PATH` before the command. IDs are explicit
for reproducible retries; fresh IDs express new assertions. Read the current
revision with `inspect-lineage` before a new lineage change. Exact retries retain
the original expected revision and event ID. Invalid CLI operations exit with
code 2 and leave no partial changes.

The local API adds `GET /api/derivations` and `GET /api/lineage` (no filters).
`POST /api/commands` accepts four additional operations under the existing
`{request_id, operation, arguments}` envelope:

| Operation | Required arguments |
| --- | --- |
| `derive` | `justification_id`, `conclusion`, `premises`, `rule`, `actor`, `reason` |
| `assign-origin` | `event_id`, `observation_id`, `group_id` (text or null), `actor`, `reason`, `expected_revision` |
| `merge-origins` | `event_id`, `group_ids`, `target_group_id`, `actor`, `reason`, `expected_revision` |
| `reverse-lineage` | `event_id`, `target_event_id`, `actor`, `reason`, `expected_revision` |

Signed references require exactly `{proposition_id, relation}`. API collections
are bounded to 1000 entries; existing 256 KiB request limits and same-origin/token
protections apply. Unexpected nested fields, invalid relations, and bool/noninteger
revisions are rejected. Stale revisions, conflicting lineage event IDs and blocked
reversals return 409; malformed inputs return 400. Derivation ID/content conflicts
remain validation errors (400). Browser command receipts commit atomically with
these new writes; exact command retries and original record/event identity retries
both preserve history without additional writes.

No endpoint edits, deletes, or withdraws a justification. The new commands record
explicit supplied rules; they neither execute those rules nor infer beliefs.
Justification lifecycle editing remains a separate contract to define before
exposing such an action. Origin changes still do not alter Beta impact clusters.

### Verification and next action

11 new service/interface tests cover composed success/rollback, borrowed connection
ownership, receipt rollback for both record types, CLI/API/service parity and
restart, merge/reversal/unknown origins, nested validation and HTTP conflict mapping,
concurrent retries, read-only consistent snapshots with an interleaved writer, and
service/API inspection after a frozen schema-2 migration. All **129 tests pass**.
HTTP handlers are tested without sockets; no new live browser or model check is
claimed by this slice.

The following slice adds GUI creation and inspection of derivations and observation-origin
history using these operations. Keep the distinction between supplied dependency
structure and current belief status visible. Preserve the unfinished step 5 manual
acceptance checklist. Step 7 will implement eligibility propagation and repair.


## Slice 4: GUI derivations and origin history (2026-11-08)

Claim detail now includes signed justifications, required premises (AND), alternative
justifications (OR), and navigation to premises and conclusions that depend on the
selected claim. The creation form searches claim/scope labels, supports signed
conclusions and premises, and requires rule, actor and reason. Empty, self and
duplicate signed premises are rejected; graph cycles remain validated by the service.

Observation detail shows its current origin and affected event history. Assignment
supports an existing/new group or explicit unknown origin. The global origin browser
shows current groups and append-only history. Merge review shows every affected
observation, including members already in the target group. Reversal controls follow
current heads and recorded reversals, and reload the ledger before presenting a review.

Forms retain stable record/event IDs and use the existing durable command receipts.
Lineage forms send the reviewed revision. A 409 disables Save and offers **Reload and
review**, which obtains fresh assignments/revision and a new event ID. Network failures
retain the exact pending command for retry. No origin edit rewrites impact clusters;
no justification becomes evidence or changes belief status. Unknown provenance is
explicitly labeled and never presented as independent.

Verification: 134 repository tests pass, including five Node-backed adapter tests for
signed payload construction, premise validation, merge membership previews, reversal
availability and scoped labels. Node is optional for Python discovery; these five tests
skip when it is unavailable. The HTTP asset check includes `structure.js`; both scripts
pass syntax checks. A temporary local server responds over HTTP, but the browser tool
cannot reach it (`ERR_CONNECTION_REFUSED`), so layout, focus and end-to-end GUI acceptance
remain pending. See the slice 4 checklist in [the browser guide](browser-workspace.md).
