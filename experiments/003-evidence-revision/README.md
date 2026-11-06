# Replayable evidence-revision project world

Steps 3–4 implementation, updated 2026-11-06. This is a standard-library simulator,
deterministic scorer, and [four initial structured comparison methods](baselines.md).
It does not modify Holon's core or invoke an LLM. Development comparisons are
engineering acceptance only; no frozen research result is claimed.

See [protocol.md](protocol.md) for the research design and
[schema.md](schema.md) for executable input/output contracts and the public/private
boundary. The [research plan](../../docs/evidence-revision-research-plan.md) is
the authoritative progress tracker.

## Generate the worked correction scenario

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py generate --output runs/revision-world-smoke
```

This writes:

- `public/episode.json`: complete source/task schedule for the trusted replay driver.
- `private/episode.json`: true lineage, time-dependent facts, and offline gold labels.
- `manifest.json`: private family/condition metadata, canonical hashes, generator
  version/seed, code hashes, Git state, and Python version.

Use a new output directory each time; existing directories are refused. Generated
files under `runs/` are ignored by Git and can be reproduced from the source.
Do not send the full bundle or manifest to an acting method.

The initial report says release is November 13 and preparation is November 12.
The source later corrects the release to November 16; preparation is therefore
November 15. Delayed summaries repeat the old date. Morgan's independent
assignment and valid approvals must survive the release-date correction.

## Inspect and resume public replay

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py replay --public runs/revision-world-smoke/public/episode.json --output runs/revision-view-01
```

`view.json` contains only the source prefix available at the first task and its
finite options. `checkpoint.json` records driver progress; `responses.json` is
the accumulated answer envelope. Put one answer in a JSON file using the task ID
and option from that view, for example:

```json
{"task_id": "<ID from view.json>", "decision": "abstain", "citations": []}
```

Then resume (replace the answer-file path with your actual file):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py replay --public runs/revision-world-smoke/public/episode.json --checkpoint runs/revision-view-01/checkpoint.json --response runs/revision-answer-01.json --output runs/revision-view-02
```

Continue until `complete` is true. After task four, the view stops at a restart
marker. Resume its checkpoint in another invocation **without `--response`**;
there is no task to answer at the restart marker. Replay gives no correctness or
answerability feedback. Direct evidence reads are simply the available source
events in the view; implemented method-specific retrieval and accounting are
documented in [baselines.md](baselines.md).

## Score saved answers offline

After an episode, replace `runs/revision-final` below with the last replay output:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py score --public runs/revision-world-smoke/public/episode.json --private runs/revision-world-smoke/private/episode.json --responses runs/revision-final/responses.json --output runs/revision-scores
```

`scores.json` distinguishes physical correctness from valid justification and
reports obsolete actions, task success, answerable completion, unresolved-task
success, abstention, missing responses, and unsupported correct guesses. Correct
guesses without evidence receive no justified-success credit. All-abstain behavior
can avoid obsolete actions but fails answerable completion. Exit 0 means scoring
completed, not that a method performed well. Malformed input/output setup exits 2.

The `audit` subcommand accepts a separate audit-response envelope (same path
arguments as `score`) and measures retained, still-supported control claims.
Audit collection must be read-only with respect to the evaluated method.

## Temporal pair and candidate catalogue

The temporal pair has identical initial reports and different update semantics:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py generate --motif 5 --variant 0 --update-kind source_correction --output runs/revision-correction
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py generate --motif 5 --variant 0 --update-kind world_change --output runs/revision-world-change
```

In the correction case, the historical release date is November 16. In the
world-change case, November 13 was valid before November 5; November 16 applies
afterward. Both require November 15 preparation for the current schedule.

Generate the candidate 36-family catalogue in all four provenance conditions:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py generate --catalogue --seed 42 --output runs/revision-catalogue
```

This produces 144 paired episode views. Each family keeps its IDs, source prose,
truth, targets, task options, and scoring labels across C0–C3. Only declared
dependency edges change. C1 removes 25%, C2 75%, and C3 combines C1 omissions
with one false merge. Rounding/counts are recorded privately. The update target
is never removed. Text can still reveal lineage when a declaration is missing.

| Motif (`--motif`) | Behavior exercised |
| --- | --- |
| 0 | Copied dates, derived preparation, and delayed copies |
| 1 | An approval is withdrawn while alternative sufficient approvals survive |
| 2 | The corrected report also contains unaffected owner/room statements |
| 3 | Joint premises and branching derived claims |
| 4 | False-merge condition, approval withdrawal, and later lineage clarification |
| 5 | Historical scope, correction/world-change pairs, and unresolved late owner conflicts |

Variants change copy-graph sizes/topologies, with additional approval/support
structure where applicable. Derivation/copy depth is bounded at three. Each
episode has 12–24 fragments and six action slots. The catalogue designates four
variants per motif as development and two as validation (24/12 families).
Changing only a seed does not create a new independent family or a new split.

These are **candidate authored families**, not a validated independent sample.
Review semantic labels and family grouping before freezing a pilot, especially
whether graph-size variants should be clustered more broadly. Generating and
structurally checking the catalogue is not running validation-method outcomes.
The fixed named acceptance example must not be recycled as final held-out data.

## Validation and remaining work

The completed checkpoint passed all 67 repository tests, including 16 new
environment/scorer tests. Final verification on 2026-11-06 checked source and
artifact hashes for the 144 catalogue views and both temporal examples, and
successfully replayed the saved correction example to its first task boundary.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests/integration -p test_revision_world.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q
```

The environment tests cover reproducible generation, paired corruption, family
assignment, graph depth, available-prefix isolation, detached views, checkpoint
validation, actual subprocess restarts, future/invalid/stale citations, AND/OR
support, unaffected shared-report facts, time semantics, read-only control audits,
and indistinguishable public inputs with different unresolved private truths.
Privileged perfect-answer fixtures exist only in scorer tests, not as a research
method or a command-line option.

Step 4 is now implemented: see [baselines.md](baselines.md) for H0/LWW/RR/RB,
shared actor contracts, process persistence, cost definitions, budgets, and runnable
comparison commands. Thirteen new baseline tests bring the suite to 80 tests.
Generator v1.1 adds the unchanged shared-report room as valid alternative audit
support while preserving public schedules/IDs; regenerate bundles for new runs.
Next is **step 5: the minimal browser workspace**. Selective repair, Track E,
summary writeback and the frozen research evaluation remain later work.
