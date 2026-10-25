# Binary Beta projection implementation plan

Status: proposed implementation plan, 2026-10-24. This document authorizes no
claim of calibration or RFC-0002A acceptance. Implement in the slices below;
retain qualitative inspection throughout the initial implementation.

## Goal and scope

Make a belief explain its direction, evidence strength, opposing evidence,
dependencies, and response to corrections. Implement a deterministic binary
Beta projection alongside `active-presence-v2`, using the same accepted ledger.
Do not replace the ledger with a stored confidence number.

Reference: `reference/rfcs/RFC-0002A Belief Dynamics Revision.md`, especially
sections 5–9 and 12–13. RFC-0002's smoothing and normalization rules are not the
implementation target. RFC-0003's extraction reliability is distinct from
source reliability; neither becomes a probability of truth by renaming it.

The first slice has no decay, learned source reliability, categorical groups,
automatic commitment/rejection, or new model prompts. It is a deliberately
partial implementation of RFC-0002A, not full conformance.

## Mathematical contract

For each active, eligible evidence link i, record nonnegative finite raw mass
m_i and its sign. Partition records by dependency cluster c and sign s.

    M[c,s] = sum(m_i for eligible evidence in cluster c with sign s)
    E[c,s] = min(M[c,s], cap)
    a = sum(E[c,+]); b = sum(E[c,-])
    alpha = alpha0 + a; beta = beta0 + b
    mean = alpha / (alpha + beta)
    variance = mean * (1 - mean) / (alpha + beta + 1)

Proposed initial policy `binary-beta-v1`:

- Prior alpha0 = beta0 = 1, explicitly an experimental symmetric prior.
- Default new accepted-link mass = 1, meaning one unit of stipulated impact,
  not a calibrated independent Bernoulli trial or model confidence.
- Per-cluster, per-sign cap = 1. Repetition from one lineage cannot grow
  effective strength without bound. Different experimental caps require a
  different immutable policy version.
- Lambda = 0: fixed-scope historical propositions do not decay by default.
- Reject negative/nonfinite masses and invalid prior/cap parameters. Zero mass
  is permitted and contributes nothing. Detect aggregate overflow explicitly.

The bounded function f(M)=min(M,cap) is monotone and concave. It is a proposed
Holon policy choice permitted by the revision's broader family, not the RFC's
logarithmic example. Expose gamma=E/M (zero when M=0) for explanation. Raw
cluster sums remain authoritative projection inputs; capped totals cannot be
incrementally merged as if they preserved raw state.

Return both evidence strength a+b and posterior concentration alpha+beta.
The latter includes prior strength and must not be labeled observation count.
Return raw/effective positive and negative masses, active/withdrawn/excluded
counts, cluster summaries, variance, and evidence IDs. Do not call variance a
measure of source disagreement. For a>0 and b>0 expose balance
2*min(a,b)/(a+b), otherwise zero; expose min(a,b) as opposing mass. These are
continuous diagnostics, not an adjudication or calibrated conflict threshold.
Raw disagreement remains visible even where cluster weighting discounts it.

## Dependency and duplicate contract

- Default to one source-owned cluster per proposition for the same stable
  source identity. Existing source strings are caller-asserted identities;
  stable IDs do not authenticate sources or establish independence.
- Permit explicit shared cluster IDs across sources with attribution/reason
  so known copied reports share a lineage. Unknown identity uses a shared
  anonymous cluster. Distinct source clusters are provisional, not proven
  independence. Arbitrary fresh cluster overrides are not routine ingestion.
- First implement immutable cluster assignment. Later add append-only cluster
  reassignment/merge events and deterministic reprojection before claiming
  support for newly discovered shared lineage. No silent metadata rewrites.
- Add an optional caller event/idempotency key, scoped to source and
  proposition. Exact retry returns existing IDs without new revisions or
  evidence. Reusing the key with different content/metadata is an error.
- Same text alone is not an event identity: identical sensor readings may be
  distinct events. Distinct unkeyed records remain in provenance, but their
  source cluster is capped. No global text deduplication or automatic semantic
  clustering in this milestone.

## Slice 0 — finish the existing evidence lifecycle

Completed: lifecycle/CLI integration tests and documentation added; full suite
passes (13 tests). Legacy revisions migration now explicitly begins a transaction
before schema changes. Validation used temporary databases, not the runtime store.

Files: `src/holon/workspace/{storage,service}.py`, `src/holon/cli.py`, integration
tests, README and architecture documentation.

The working tree already contains withdrawal/correction changes, but dedicated
tests and documentation are unfinished. Stabilize these before expanding the
schema. Verify supported → contested → supported on withdrawing the contrary
link, and insufficient_evidence after withdrawing every link. Verify atomic
replacement, unchanged original observations, actor/reason retention, repeated
withdrawal rejection, restart persistence, old-schema migration, and rollback
when a correction fails after creating its replacement.

Exit: lifecycle tests pass and existing interpretation acceptance still works.

## Slice 1 — pure domain projection

Completed: immutable domain types and `project_binary` implemented in
`src/holon/domain/projection.py`. Tests cover the mathematical contract,
permutations, combined raw ledger partitions, directionality, lifecycle filtering,
and numeric range safety. Full suite: 23 passing tests. Persistence and CLI
integration remain slices 2–3; no runtime database changes were needed.

Add `src/holon/domain/projection.py` with immutable policy, input, cluster
summary, and result types. No SQLite, model calls, wall-clock reads, or writes.
Caller supplies the eligible ledger snapshot and full immutable policy.
Use deterministic ordering and stable summation (`math.fsum`) for reproducible
floating-point aggregation. Keep evidence presence rules in `records.py`.

Test the prior, one-sided evidence, balanced disagreement, zero mass, cap
boundaries, and invalid numbers. Test permutations and partitioned ingestion
using raw cluster summaries, not capped intermediate totals. Fix numeric
tolerance at relative/absolute 1e-12 for the initial bounded synthetic suite;
large-value safety tests must fail cleanly rather than emit NaN/Infinity.

Exit: same ledger/policy produces the same result; duplicates from one cluster
saturate while independent stipulated clusters can add strength. A new positive
record cannot reduce the mean, and a negative one cannot increase it, with all
other inputs held fixed.

## Slice 2 — versioned persistence and migration

Completed: transactional schema version 1, immutable policy/impact metadata,
explicit legacy assumption annotation, and copy-based migration rehearsal.

Add explicit transactional schema migrations and a schema version. Preserve
existing observation/evidence IDs, interpretation metadata, revisions and
withdrawals. Avoid relying on positional INSERT statements as schemas evolve.

Prefer additive tables: immutable projection policies; per-evidence impact
metadata (mass, semantics/mapping version, cluster, optional idempotency key);
and migration-run metadata recording assumptions and coverage. Enforce foreign
keys, uniqueness, and application numeric validation. Store a dynamics version
separately from policy identity. Policy IDs resolve to immutable parameters
and a canonical content digest.

Legacy evidence has sign/source but no explicit mass or dependency semantics.
Keep legacy inspection unchanged. By default, report the new projection as
`replay_incomplete` when required metadata is absent; do not silently drop old
evidence and present a complete result. Offer an explicit migration operation
that attaches unit-impact/source-cluster assumptions as auditable sidecar
records and labels the result `replay_approximate`. Never invent observation
times, source reliability, or calibrated evidence weights. Fresh versioned
records can be `replay_complete` under the declared experimental contract.
Coverage classification is separate from the legacy belief status.

Exit: old stores open safely, migration is repeatable, failures roll back, and
all legacy provenance/revision sequences survive. A database-copy rehearsal
precedes migration of the user's working database.

## Slice 3 — workspace integration and CLI

Completed: snapshot projection, optional inspection, CLI commands, report/correction
impact and retry metadata, shared cluster attribution, and correction lineage.
Integration tests cover replay coverage, restart, no-write reads, retries, and rollback.

Add a workspace projection read method. Load evidence, withdrawals, metadata,
and policy in one SQLite snapshot, then call the pure projector. Projection
reads create no evidence, revisions, or persisted confidence updates.

Add `holon project PROPOSITION_ID --policy binary-beta-v1` and an optional
projection section on inspection. Preserve the existing `status`, `evidence`,
and `history` fields. The projection includes dynamics/policy versions and
digest, ledger-input digest, replay coverage, excluded evidence and reasons,
and the quantitative explanation. No projection cache yet.

Extend report/correct ingestion with optional mass and event-key inputs;
document the unit-impact default and source-cluster assignment. Interpretation
continues to propose only a relation/reason and requires existing acceptance;
the selected experimental policy supplies impact, not the LLM. Correction
creates replacement metadata and withdraws the old link atomically. A corrected
reading normally retains its lineage unless an explicit reason justifies a
different one. A replacement is not automatically independent corroboration.

Exit: CLI restart/replay agrees with direct projection, repeated reads do not
write, correction has the same quantitative result as projecting the remaining
active records, and failed contributions change neither view.

## Slice 4 — adversarial checks and usable explanations

Add `experiments/002-binary-beta/` with deterministic fixtures, expected
properties and a small runner recording policy/dynamics versions and results.
No Ollama call is required. Fix acceptance criteria before running it.

| Scenario | Required result |
|---|---|
| No evidence vs balanced strong evidence | Same possible mean; different strength and opposing mass |
| One assertion vs many independent stipulated clusters | Different strength; no automatic commitment |
| Hundreds of reports from one cluster | Bounded effective mass; raw count remains visible |
| Same keyed event retried | No additional record, mass or revision |
| Two sources sharing declared lineage | One cluster cap, not two |
| Random permutations / batch partitions | Same final projection within declared tolerance |
| Withdrawal / replacement | Only active eligible evidence contributes; history remains |
| All evidence withdrawn | Exact return to configured prior |
| Restart / repeated inspection | Same projection; no read-induced writes |
| Legacy missing metadata | Explicit incomplete/approximate coverage, no invented confidence |
| Invalid/huge numeric input | Rejected or fails explicitly, no partial transaction |

Document examples in README and update architecture/roadmap. Record divergences
between qualitative and Beta views without calling a favored mean resolved
conflict. Technical correctness of these checks does not establish empirical
calibration or satisfy the full RFC acceptance program.

Exit: all existing tests and the new lifecycle/projection/integration tests
pass; a saved example explains each number back to its contributing records.

## Follow-on work, in dependency order

1. Append-only cluster merge/reassignment with audit and replay tests.
2. Separate observation time, ingestion time and validity; define historical
   queries over both event knowledge and world time before adding `--as-of`.
   Current inspection alone is the initial supported temporal contract.
3. Optional shared-rate exponential decay per relation policy. Keep fixed-time
   historical claims nondecaying unless a justified policy says otherwise;
   test semigroup, silence neutrality and read-schedule invariance.
4. Source-reliability scoring ledger with independent outcomes/proxy labels,
   explicit semantics, and causal exclusion. Keep extraction quality distinct.
5. Commitment/rejection policy with calibrated mass mapping, evidence minima,
   posterior predicates, conflict constraints and preregistered validation.
6. Dirichlet groups only when alternatives/exhaustiveness and unknown mass are
   explicitly modeled. Do not normalize unrelated binary projections.

## Delivery sequence

Implement slices 0–1 first, then 2–3, then 4. Each slice should be reviewable
independently. No automatic commits, production database migrations, or legacy
status replacement are part of this planning task. The first useful result is
an inspectable quantitative projection with bounded repetition and faithful
withdrawal recovery, not a new autonomous decision mechanism.
