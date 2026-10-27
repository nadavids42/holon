# Observation time and evidence lifecycle: implementation plan

Status: implemented and verified through the integrated CLI scenario, 2026-10-27.
Observation-time provenance, observation reuse, and reinterpretation are
implemented. The semantic
contract in `epistemic-semantic-contract.md` remains the source of the intended
record meanings. Preserve the existing CLI and SQLite data throughout.

## 1. Observation-time contract

- `observed_at` is an optional, caller-supplied instant: when the observation
  represented by the record occurred. It is not the time Holon recorded the
  input (`recorded_at`), nor necessarily the time the report's subject was true.
  If the caller cannot identify an observation instant, leave it unknown. A
  report received Tuesday about a door on Monday does not, by itself, establish
  when anyone observed the door.
- Accept an ISO 8601 date and time with seconds and an explicit UTC offset or
  `Z`, optionally with up to six fractional-second digits. Reject date-only,
  naive, malformed, or out-of-range timestamps; do not silently guess timezone
  or precision. Normalize valid instants to a consistent UTC representation for
  storage and equality. The value is a caller assertion, not an independently
  verified measurement; no model extraction is implied.
- `NULL` means unknown, including for pre-migration observations. Never fill it
  from `recorded_at`, proposition scope, or report text. Date-only precision,
  intervals, uncertainty bounds, and subject-time representation are deferred.
  A caller must not fabricate a precise instant to fit this interface.
- Add an optional `observed_at` argument to `add_report` and `--observed-at`
  to `report`, `interpret`, and report correction. A correction creates a new
  observation: its time is explicitly supplied or unknown, not silently copied
  from the old record. Show the field in inspection and the interpretation
  preview. Initially, merely supplying it does not change the model prompt,
  qualitative policy, Beta dynamics, or conflict detection; the report and
  scope remain the model's temporal inputs. Do not claim the model checked the
  separate timestamp. If a later adapter uses it, version that prompt change.

## 2. Schema upgrade and preserved history

Use the next explicit SQLite `user_version` migration to add a nullable
observation-time field. Upgrade known version-0 and version-1 stores, including
the existing targeted legacy migration, within a transaction. Fresh databases
and upgraded databases must converge on the same usable schema. A database
from a newer version must still be rejected. Do not reinterpret legacy values,
replace IDs, delete records, or backfill inferred times. Retain existing policy,
impact, correction, and revision records exactly. Opening an older workspace
can migrate it, so document backup guidance and verify migrations on copies.

Test against literal historical schemas rather than constructing a legacy
fixture from the current `SCHEMA`, which changes over time. Test a failed
migration, repeat opening, `foreign_key_check`, and preservation of the old
revision sequences. Use temporary databases, never the user's runtime store.

## 3. Retry and digest compatibility

Current report and correction retries use a source-and-proposition-scoped event
key and a digest of the request. Existing digests cannot be silently rewritten:
impact metadata is immutable. Preserve a way to recognize the existing request
format, and version the new digest semantics. A retry of an old request with
unknown observation time must still return its original IDs; a retry that adds
or changes a known time must fail as a conflict. Equivalent timezone spellings
of the same normalized instant should compare equal for a new request.

For new link and reinterpretation operations, define a canonical request that
includes operation kind, relevant observation/evidence and proposition IDs,
relation, impact inputs, interpretation, and attribution as applicable. Reuse
the existing source/proposition event-key namespace or document a deliberate
migration; do not allow a key from one operation to be mistaken for another.
No event key means a distinct request, subject to the active-link rule below.
As today, a successful retry returns original IDs and current proposition
status, not a promise to reconstruct the exact original response.

The existing projection `ledger_digest` is computed from a defined selection of
rows and does not currently include observation time. Do not silently change its
meaning. Preserve its existing definition and, if a full provenance digest is
added, give that digest a separate name and version. Observation time does not
affect `binary-beta-v1`, so adding it must not change that policy's numerical
result or the meaning of the existing digest. State clearly which fields each
digest covers; neither digest is proof that LLM inference is reproducible.

## 4. Observation reuse

Introduce narrowly scoped workspace operations, with final signatures chosen
at implementation time:

1. `record_observation(source, report, observed_at=None)` persists a single
   observation and returns its ID. It does not create a proposition, link,
   revision, or belief. Two calls are two records even if the text matches;
   this initial operation has no automatic deduplication or event-key retry.
2. `link_observation(observation_id, proposition_id, relation, ...)` creates
   evidence for an existing observation, optional accepted model interpretation,
   impact metadata, and one qualitative revision in a single transaction. It
   uses the observation's stored source; callers cannot substitute another
   source for that link. Its event key follows the compatibility contract above.
3. Keep `add_report` and `report` as a one-step convenience. Their observation,
   link, metadata, and revision still commit atomically; do not implement them
   as two separately committed public operations.

Proposed CLI entry points are `observe --source ... --text ... [--observed-at ...]`,
`link OBSERVATION_ID PROPOSITION_ID --relation ...`, and
`inspect-observation OBSERVATION_ID`. Observation inspection shows its content,
times, and associated links with proposition IDs and active/withdrawn state;
existing proposition inspection continues to show the shared observation ID.
CLI names and output fields should be finalized during implementation without
breaking existing commands.

For newly created links, reject a second active link for the same observation
and proposition, even with the opposite relation: use reinterpretation to
replace the first judgment. An exact event-key retry returns the existing link
before this check. Do not merge or rewrite any legacy duplicates; keep them
inspectable and withdrawable. Enforce the rule transactionally in supported
operations, and test legacy duplicates explicitly. Different propositions may
link to the same observation. The rule does not infer independence across
different observations or automatically combine clusters.

Existing `interpret` remains a preview-and-accept workflow that creates a new
observation only on acceptance. Add a separate interpretation of an existing
observation using the same provider boundary and explicit acceptance, either as
a clearly named CLI mode or a dedicated command. It must use stored source and
report, not create another observation; abstained, declined, or failed proposals
create no link or revision. The first iteration need not store rejected model
proposals. Avoid holding a write transaction open during a model call or human
approval; revalidate the active-link rule when committing.

## 5. Reinterpretation versus report correction

Introduce `reinterpret_evidence(evidence_id, relation, actor, reason, ...)` and
a corresponding `reinterpret` CLI command. It creates a replacement evidence
link for the **same observation and proposition**, withdraws the old link with
actor/reason/time and replacement ID, writes metadata, and appends the revised
qualitative state in one transaction. It must reject an already withdrawn link
unless an exact event-key retry is recognized. Other links to the observation
remain untouched. The old link, its model metadata, and prior revisions remain
inspectable.

For a manual reinterpretation, record actor and reason as caller attribution in
the withdrawal/supersession record; do not invent a model or pretend a model
approved it. If a model proposes the new relation, retain its model, reason,
and prompt version on the new link and require explicit acceptance before the
transaction. Keep the user-supplied correction reason distinct from the model's
reason. An LLM-assisted reinterpretation may reuse the existing-observation
preview path but must commit via this atomic operation, not as a separate link
followed by withdrawal. Revalidate the original link after preview.

Default replacement impact mass to the original link's stored mass and retain
its cluster and cluster attribution as lineage; allow a deliberate mass override
only if explicitly supplied and represented in the retry digest. Do not treat
this as evidence that cluster membership is objectively correct. If legacy
impact metadata is absent, do not invent a mass or cluster: require explicit
legacy annotation through the existing migration operation before quantitative
reinterpretation, or fail clearly without changing records. This avoids
silently turning incomplete replay into a complete result.

Keep `correct` as the existing atomic report-correction workflow: it creates a
replacement observation and link and withdraws the selected old link. It acts
on that link only; it does not silently replace every link to an observation.
Its current retained cluster behavior remains in effect. Add optional explicit
observation time to the new report, and retain the original unchanged. Other
links to the original remain active unless separately withdrawn or reinterpreted.
Existing correction records are not retroactively classified as report versus
interpretation corrections; their intent may be unknown.

## 6. Verification by increment

**Time increment:** test UTC/offset normalization, invalid and ambiguous input,
unknown time, different recording/observation/subject times, `report`,
`interpret` preview and acceptance, correction, restart, and migration from
literal version-0 and version-1 fixtures. Test old and new event-key retries,
conflicts, unchanged Beta results, and documented digest semantics.

**Reuse increment:** test one observation linked to two propositions, no new
observation for the second link, standalone unlinked observation inspection,
different identical reports remaining separate, duplicate active-link rejection,
legacy duplicates, invalid IDs, atomic rollback, event-key conflicts, and
explicitly accepted or declined model proposals for an existing observation.
Verify the existing single-step report remains atomic and compatible.

**Reinterpretation increment:** test support-to-contradiction and the reverse,
same observation/proposition and new evidence identity, retained old reasoning,
attribution, mass and cluster, unchanged other links, correction versus
reinterpretation, missing impact metadata, duplicate and conflicting retries,
and injected failures at replacement, metadata, withdrawal, and revision writes.
Repeat after restart; compare qualitative and quantitative readouts.

**Final integration:** exercise all three increments through the CLI across
processes and an old database copy, then run the full existing test suite.
Update the semantic contract's current-support table, README examples,
architecture, and roadmap only as the corresponding features actually land.
Do not claim model classification quality based on mocked adapter tests; live
Ollama checks are separate and optional.

## 7. Scope and unresolved decisions

This plan does not add automated time extraction, time-bounded proposition
semantics, semantic resolution, automatic dependence inference, dependency
reassignment, calibrated reliability, decay, or historical Beta replay. It
also does not require a general repository framework or database change. The
exact CLI spelling and internal request-version storage are implementation
choices, subject to the compatibility and acceptance conditions above.
