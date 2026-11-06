# Project-world JSON contracts v1

Executable validators: `revision_world/schema.py`. All record fields are exact;
unknown fields are rejected rather than silently forwarded to a method. Dates
are ISO calendar dates; recording/known observation instants need UTC offsets.
Canonical digests use sorted compact JSON with nonfinite values forbidden.

## Public schedule (trusted driver input)

Top-level fields: `schema_version`, `episode_id`, `project_id`, `rules`, `events`,
`audit_queries`. Version is `revision-world-v1`. IDs are opaque UUIDs. The seed,
family, condition, split, truth, gold answers, and complete lineage are absent.

Each event has `index`, `id`, `kind`, `payload`. Indexes are contiguous from zero.
Kinds are `source`, `task`, and `restart`. There are six tasks and exactly one
restart after task four. This is a **complete future schedule for the trusted
driver**, not a file that should be passed to an acting method.

Source payload:

| Field | Meaning |
| --- | --- |
| `id` | Immutable fragment identity; distinct copies have distinct IDs |
| `source_id`, `version` | Public source-local identity/version, not a truth or independence guarantee |
| `recorded_at`, `observed_at`, `subject_time` | Separate recording instant, optional observation instant, and subject date |
| `statements` | Supplied-structure assertions: list of `{key, value}` string pairs |
| `text` | Original authored report text, including source references where appropriate |
| `dependencies` | Fallible declarations of `{parent, kind}` with `kind` equal to `copy` or `premise` |
| `update` | Null or `{kind, targets, effective_at}`; source correction, world change, withdrawal, or lineage correction |

Parents/targets must refer to earlier fragments. This rejects dangling, forward,
and circular references in the public schedule. Updates name direct targets;
they never expose a privileged affected-descendant list. The changed statement
is identified by the update's `statements` keys. World changes require an
effective date. Source corrections do not silently invalidate every statement
in a multi-fact report. Known independence is not inferred from source names.

Task payload: `id`, `query`, `subject_time`, `options`. Options are a finite list
of action strings plus `abstain`; option order is seeded and paired across
conditions. Actions include `reported_release:DATE`, `prepare_on:DATE`,
`owner:NAME`, `ready:yes/no`, and `release_on:DATE` for historical questions.
Public rules explicitly define the one-calendar-day offset and AND/OR approval
requirements. No hidden business-day calendar or implicit authority rule is used.

Audit query: `{after_task_id, claims: [{key, value}]}` after tasks four and six.
These are candidate statements to assess, not labels saying they are true. The
replay view reveals each audit only after its task is answered. A later method
adapter must conduct audits on a snapshot and discard any audit-induced state.

## Private world and scoring record (evaluator only)

Top-level fields: `schema_version`, `episode_id`, `public_digest`, `metadata`,
`truth`, `lineage`, `tasks`, `audits`. The digest binds the record to one exact
public schedule, including its provenance condition.

`metadata` records generator version, seed, candidate family ID, motif, variant,
development/validation designation, C0–C3 condition, omitted-edge counts by kind,
and false merges. `truth` includes release and owner validity intervals.
`lineage` retains true `{child, parent, kind}` edges, independent of corrupted
public declarations. A world change creates two release validity intervals;
a source correction has only the corrected historical value.

Each private task record has:

- `task_id`, `boundary`: public task identity and available-event boundary.
- `physical_decision`: action consistent with the simulated world (or the named
  report's actual text for a report-content lookup).
- `answerable`: whether exposed evidence can justify one action under public rules.
- `support_sets`: alternative sufficient sets of fragment IDs; each set is an
  AND and alternatives are OR. Every cited fragment must already be available.
- `obsolete_decisions`: specifically superseded actions for obsolete-action scoring.
- `stratum`: `lookup`, `affected`, `control`, or `historical`.

Private audits match the public audit questions and add valid `support_sets`.
These are predetermined still-supported controls, not a count of stored rows.

The schema validator checks references, boundaries, bindings, and structural
consistency. It cannot establish that an authored gold label is scientifically
correct. Semantic acceptance tests and later independent fixture review are
required; changing a gold label is not a legitimate way to fix a losing method.

## Method response and read-only audit response

One task response is exactly:

```json
{"task_id": "<pending task ID>", "decision": "prepare_on:2026-11-15", "citations": ["<fragment ID>"]}
```

An abstention is `decision: "abstain"` with an empty citations list. Responses
cannot carry gold labels or extra fields. Unknown/out-of-vocabulary/duplicate
task responses are malformed and rejected. A syntactically valid missing,
stale, future, or invented citation is an incorrect answer, scored offline;
replay does not reveal grading feedback.

A response file wraps these rows with `schema_version`, `episode_id`,
`public_digest`, `responses`. Missing task rows count as failures over the full
six-slot denominator; they are not silently dropped. A response from a different
episode or provenance condition fails the digest check.

An audit response has `schema_version`, `episode_id`, `public_digest`,
`after_task_id`, and `claims`. Each claim has `key`, `value`, `stance`
(`assert`/`deny`/`unresolved`), and `citations`. Omitted control claims are not
retained. The output reports a numerator, denominator, and rate.

For a justified action, citations must contain at least one complete sufficient
support set and must contain no IDs outside the union of valid support sets for
that task. Redundant valid alternatives are allowed; stuffing the response with
unrelated or superseded sources is not. This is a conservative, explicit scoring
choice. Current v1 accepts direct source-fragment citations only; a future adapter
must expand memory references to validated public evidence before scoring.

Physical correctness, justified success, obsolete actions, abstention, missing
responses, and unsupported correct guesses are distinct output fields. An
unanswerable task can be physically guessed correctly while failing justified
success; justified abstention succeeds there. Undefined rate denominators are
JSON null, not fabricated perfect scores.

## Replay checkpoint and boundary

Checkpoint fields: `schema_version`, `public_digest`, `cursor`, `responses`.
Restoration replays public event order and validates every saved response; it
rejects skipped unanswered tasks, extra responses, invalid cursors, and mismatched
schedules. At the restart marker, `advance` is blocked until restoration. The CLI
tests perform this restoration in a new process. Future method-owned state must
also be persisted by its adapter; v1 checkpoints only the environment and answers.

The method-facing view contains only identity/rules, the event prefix, the pending
task, already-reached audit queries, restart requirement, and completion status.
It is a detached JSON copy. Methods must receive this view, not the `Replay`
object, checkpoint, full schedule, manifest, private file, or generator inputs.

This is an application data boundary, **not an operating-system security sandbox**.
The driver/evaluator are trusted. Step 4 must keep complete schedules and private
files outside method inputs and withhold scores until episodes end. A later
untrusted executable adapter would need process/filesystem isolation as well.
