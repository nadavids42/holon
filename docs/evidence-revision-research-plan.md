# Evidence revision research and interface implementation plan

Status: steps 1–4 complete; step 5 (first graphical workspace) is next.
Recorded: 2026-11-03 (America/New_York).
Checkpoint updated: 2026-11-06 (Etc/UTC).

## Start here: current state and next action

This is the authoritative progress tracker for the next bounded Holon study.
The [charter](../PROJECT_HOLON.md) remains authoritative for the broader project.
The [roadmap](roadmap.md) points here; earlier implementation plans retain their
historical checkpoints and detailed acceptance criteria.

- **Current phase:** steps 1–4 complete: protocol, adversarial Beta validation,
  replayable project environment, and initial structured comparison methods. Step 5 is next.
- **Original review baseline:** `a98c576cd973dd342b1f2f6eb94da08ab190f66a`,
  matching the GitHub default-branch head and local checkout at review time.
  Step 2 started from local commit `5d8aa9a` (the plan/protocol documentation);
  run manifests identify the added validation code by source hashes and dirty
  status until it is committed.
- **Current verification:** 12/12 experiment 002 scenarios and 80/80 repository
  tests passed on 2026-11-06, including 16 environment/scorer and 13 baseline tests, plus runner
  failure detection under `python -O`.
  The step 3 handoff on 2026-11-06 verified source and artifact hashes for all 144
  catalogue views and both temporal examples, plus the saved-example replay CLI.
  Step 4 saved four complete development comparisons (copied date, shared report,
  correction, and world change) under `runs/step4-acceptance-20261106/`; their
  recorded source hashes were verified. These ignored artifacts are reproducible
  with the baseline commands; all four methods retained the audited controls.
  The original review baseline had 48 passing tests. Run the current suite with
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q`.
  This establishes existing engineering behavior, not comparative effectiveness
  or live model interpretation quality.
- **Work completed:** repository/code review, research direction selection,
  sequencing, and [experiment protocol v0.1](../experiments/003-evidence-revision/protocol.md).
  The protocol defines scenarios, metrics, baseline access, budgets, practical
  decision thresholds, and stop conditions. No selective repair mechanism, GUI,
  API, chat interface, or frozen comparative evaluation is implemented.
  [Experiment 002](../experiments/002-binary-beta/README.md) now supplies the
  adversarial engineering runner, fixed fixtures, frozen legacy migration input,
  traceable JSON reports, and a saved explanation. Core behavior is unchanged.
  [Experiment 003's environment](../experiments/003-evidence-revision/README.md)
  now has strict public/private schemas, seeded generation of 36 candidate
  families × four conditions, prefix-only replay/checkpoints, offline action and
  control-audit scoring, and correction/world-change acceptance cases.
- **Step 4 implementation:** [baseline contract and commands](../experiments/003-evidence-revision/baselines.md).
  H0 uses the unchanged Workspace service; LWW, RR, and RB are local mechanism-class
  implementations. One deterministic actor, subprocess replay, method checkpoints,
  separate read-only audits, bounded logical work, and offline scoring are wired.
  Development smoke comparisons are engineering acceptance, not research findings.
  Generator v1.1 fixes the shared report's valid room-audit alternative; public
  schedules are unchanged, and the label amendment is documented in the protocol.
- **Next concrete action:** step 5, UI-1 through UI-5: expose the existing
  observation → interpretation → acceptance → inspection → correction workflow
  through a local browser. Start with the service/API boundary and workspace
  selection; keep the CLI and browser behavior equivalent. General chat and
  research dashboards are later work. Do not begin selective repair in this step.
- **Blockers:** none identified for step 5. UI framework selection remains open.
  Before a research pilot, review candidate family grouping and gold labels,
  freeze baseline/actor configuration, and add required later comparators.
  Track E model configuration, budgets, summary writeback and powered final study
  size remain future work. The current comparison command is development-only.

Experiments 002 and 003 are runnable; their READMEs contain verified commands.
Experiment 003 runs the environment, scorer, and four initial Track S methods.
It does not yet implement the selective repair research candidate.

## Decision and research question

Pursue **evidence revision under incomplete provenance**, opportunity 1 in
*AI_Systems_Research_Gaps_2026-11-03.md*. Extend the current Python/SQLite/Ollama
architecture; a rebuild is unnecessary.

Working question:

> When evidence changes and provenance is incomplete, does selective repair
> reduce obsolete actions while retaining valid knowledge, compared with
> rereading available sources?

Example: a release date is corrected, several summaries repeat the obsolete
date, and other facts from those summaries remain valid. Repair should prevent
actions based on the obsolete date without discarding independently supported
information or recreating the old claim in later summaries.

The candidate contribution is a controlled result about repair under missing or
incorrect lineage, including its cost and failure boundaries. Belief revision,
dependency graphs, and cascading retraction are not themselves novelty claims.
If source-filtered rereading performs as well at lower full-lifecycle cost, the
extra machinery has not earned its complexity for that workload.

Opportunity 1 is the closest continuation because evidence identity, lifecycle,
history, and deterministic projection already exist. Information acquisition
would additionally need a checking/action policy; rule governance needs rule
extraction and enforcement; tool recovery needs external-effect tracking; authority
propagation needs trust principals and enforceable field-level boundaries. Those
remain separate future studies, not requirements for this one.

## Existing capabilities and gaps

| Capability | Current implementation | Remaining work for this study |
| --- | --- | --- |
| Observations and scoped propositions | Separate persistent records; observation reuse across claims | Derived conclusions and explicit premise relationships |
| Evidence lifecycle | Withdrawal, report correction, and link reinterpretation with atomic updates and retained history | Repair across dependent conclusions; alternative justifications |
| Dependency handling | Immutable source/shared clusters cap repeated impact | Versioned lineage changes; missing/wrong lineage; copy lineage distinct from logical dependence |
| Quantitative readout | Pure binary Beta projector, persistent metadata, policy/input digests | Repair-aware eligibility and controlled comparisons; no assumed calibration |
| Time | Recording time and optional observation time | Minimal subject-time/validity semantics for changes versus corrections |
| Interpretation | Ollama classifies a report against an existing proposition; explicit acceptance | Proposed claims and derivations; extraction evaluation and full attempt logging |
| Interface | CLI over `Workspace`; preview/accept orchestration partly in CLI | Shared application operations, browsing/search, local API, GUI, grounded chat |
| Evaluation | 80 passing engineering tests; experiment 002 adversarial checks; experiment 003 environment, initial baselines, costs and development scoring | Frozen pilot/evaluation, later comparators, model costs, statistical analysis |

Relevant implementation: `src/holon/workspace/service.py`,
`src/holon/workspace/storage.py`, `src/holon/workspace/metadata.py`,
`src/holon/domain/projection.py`, `src/holon/inference/`, and `src/holon/cli.py`.
Relevant contracts: [epistemic semantics](epistemic-semantic-contract.md),
[architecture](architecture.md), [Beta plan](binary-beta-implementation-plan.md),
and [observation lifecycle plan](observation-provenance-lifecycle-plan.md).

## Progress tracker

Use `not started`, `in progress`, `blocked`, or `complete`. Completion requires
the exit evidence specified below, not just code or a passing demonstration.

| Step | Deliverable | Status | Completion evidence |
| --- | --- | --- | --- |
| 1 | Research protocol and criteria | Complete (draft v0.1) | [Protocol](../experiments/003-evidence-revision/protocol.md): world/update semantics, comparisons, scoring, paired conditions, budget and decision rules; documentation checks passed; no runs |
| 2 | Adversarial projection validation | Complete | [Experiment 002](../experiments/002-binary-beta/README.md): 12/12 scenarios, 51/51 tests; [saved explanation](../experiments/002-binary-beta/example.md); temporary stores only; no core changes |
| 3 | Replayable project environment | Complete | [Experiment 003 environment](../experiments/003-evidence-revision/README.md), [schemas](../experiments/003-evidence-revision/schema.md), 16 new tests; 36 candidate families/144 views; actual process restart and private-file-free replay verified; no comparative runs |
| 4 | Inexpensive comparison methods | Complete | [Track S baselines](../experiments/003-evidence-revision/baselines.md): H0/LWW/RR/RB, shared actor, subprocess persistence, cost/budget accounting, separate audits; 13 new tests; development acceptance only |
| 5 | First graphical workspace (UI-1 through UI-5) | Not started | — |
| 6 | Derivation and lineage contract/storage | Not started | — |
| 7 | Selective repair with known dependencies | Not started | — |
| 8 | Incomplete/incorrect dependency handling | Not started | — |
| 9 | Temporal changes and delayed corrections | Not started | — |
| 10 | Language extraction and conversational use | Not started | — |
| 11 | Pilot, frozen evaluation, and findings | Not started | — |

The default order is 1–11. Step 5 is an early usability milestone, not a
prerequisite for the research protocol or headless experiments. UI research views
grow alongside steps 6–9; grounded conversational use belongs in step 10.
If interface work expands beyond the first milestone, defer polish and continue
the research through the CLI/service. Preserve a runnable headless harness.

## Implementation steps and exit criteria

### 1. Define the experiment

Write `experiments/003-evidence-revision/protocol.md`. Define evidence identity,
available sources, source versions, tasks, action correctness, and the distinction
between a false original report, a mistaken interpretation, and a later world
change. Start with one interpreting agent and one deterministic workspace.
Specify metrics, baseline access, resource accounting, and pilot stop conditions.
Record numerical thresholds as explicit design choices before running the pilot;
the chosen targets are now recorded in protocol v0.1, not empirically validated.

**Exit:** another reader can determine what would favor Holon, favor a simpler
baseline, or invalidate the comparison without seeing any experimental result.

### 2. Finish projection validation

Completed 2026-11-05: 12 scenarios and 51 repository tests pass. See
[experiment 002](../experiments/002-binary-beta/README.md) for reproduction and
[the saved explanation](../experiments/002-binary-beta/example.md) for traceability.

Complete slice 4 of the existing Beta plan in `experiments/002-binary-beta/`.
Cover repeated copies, shared origins, no evidence versus balanced disagreement,
retries, permutations, withdrawals/replacements, missing metadata, invalid inputs,
and restart consistency. Save explanations tied to contributing records and
record code, policy, and dynamics versions. Use temporary databases or copies.

**Exit:** the existing suite and deterministic scenario runner pass; every
reported quantity can be traced to its inputs. No calibration claim follows.

### 3. Build the replayable environment

Completed 2026-11-05: generator, strict schemas, public-prefix replay/checkpoints,
offline action/control-audit scorers and command-line tools. Six motif groups
provide 36 candidate configurations and C0–C3 views; the 24/12 split is a candidate
assignment requiring review before the pilot. Tests establish reproducibility,
boundary separation, time semantics, AND/OR support, and scoring failure cases.
The full suite passes 67 tests. No method comparisons or model runs occurred.

Create a small deterministic project-world generator and event runner under
`experiments/003-evidence-revision/`. Begin with a handful of manually inspectable
scenarios, then expand to 30–50 pilot families. Include copied reports,
independent support, branching dependencies, corrections, and later summaries.
The simulator's truth and complete lineage are private scoring data; ordinary
methods receive only their declared evidence view. Include scored decisions,
such as choosing a preparation date, rather than only memory inspection.

**Exit:** a seed and event schedule reproduce the same world and scores across
process restarts; hidden truth does not leak into the agent's inputs.

### 4. Establish comparison methods

Completed 2026-11-06: four initial Track S methods share one harness, actor,
public archive and offline scorer. H0 uses the actual unchanged core. The other
three are mechanism-class implementations. Restart persistence, cost vectors,
budget exhaustion and read-only audits are tested; the runner refuses validation
families. See [the baseline contract](../experiments/003-evidence-revision/baselines.md)
for exact semantics, unsupported capabilities and remaining pre-evaluation work.

Implement unchanged Holon, last-write-wins facts, source-filtered rereading, and
full rebuilding from available evidence. Before the final study, add a retrieval
baseline and a documented history-preserving revision baseline. Record whether
each is an actual external implementation or a reimplemented mechanism class.
Match accessible evidence and actor/model configuration, and account for actual
ingestion, maintenance, retrieval, validation, retry, token, and runtime costs.

**Exit:** all initial methods run through one harness and scorer. Their known
limitations, budgets, and differing input representations are explicit.

### 5. Add the first graphical workspace

Complete UI-1 through UI-5 below using the existing service and semantics.
The first milestone is the current observation → interpretation → acceptance →
inspection → correction workflow, entirely through a local browser.

**Exit:** no manual UUID copying is necessary for that workflow; CLI and GUI
produce equivalent workspace state and history. This is not yet general chat.

### 6. Represent derivations and lineage

Define premise sets with AND semantics within a justification and OR semantics
across alternative sufficient justifications. Keep logical dependence separate
from copy/source lineage and from evidence sign. Begin with acyclic derivations;
reject circular support. Design additive schema migrations and append-only
lineage reassignment/merge/reversal events with attribution and reasons.
Preserve old projection policies and metadata; do not silently rewrite clusters.

Track provenance completeness separately from replay coverage. Today's
`replay_complete` means reconstructible inputs under the declared contract, not
complete knowledge of real dependencies. Version any expanded input digests:
the existing projection ledger digest does not include observation time.

**Exit:** represent joint premises, alternative support, shared origins, and a
reversed mistaken lineage assignment without deleting history. Migration/replay
tests preserve the old checkpoint. Full historical as-of querying is not required.

### 7. Repair known dependencies

On evidence changes, identify affected justifications and recompute their
eligibility, retaining conclusions with surviving independent support. Distinguish
temporary loss of derived support from an explicit permanent withdrawal; allow
later restoration through recorded transitions. Explain each repair and retain
original reports. Keep qualitative status and projection eligibility consistent
under versioned policies. Derived restatements must not mint independent mass.

**Exit:** correct selective repair, alternative-support retention, bounded copy
impact, rollback, and restart behavior pass deterministic scenarios. Compare
incremental results with full recomputation as an engineering oracle.

### 8. Handle incomplete or incorrect dependencies

Represent known, suspected, and unknown lineage separately from uncertainty about
claim truth. Add a bounded fallback for inadequate provenance: retrieve related
sources, reread, broaden repair, or mark for review. Retrieval must be able to
find candidates beyond the known dependency graph. Missing links imply neither
independence nor lack of support. Log triggers, work performed, and unresolved
cases; hidden omissions may be undetectable, so make no universal repair claim.

**Exit:** controlled missing-edge and wrong-merge conditions expose both successes
and failures. Compare selective repair with and without fallback and charge its
complete cost. Oracle lineage is diagnostic only.

### 9. Add bounded temporal semantics

Use explicit scoped versions or validity intervals to distinguish correction of
an originally false report from a later change in the world. Separate subject
time from recording and observation time. Add delayed/out-of-order updates and
test that historical truths remain historically valid while current decisions
use appropriate evidence. Avoid building a general temporal reasoning engine.

**Exit:** matched scenarios distinguish correction from change and arrival order
does not silently replace subject-time semantics; unknown times remain unknown.

### 10. Add extracted structure and grounded conversation

Extend the existing interpretation boundary to propose claims, source references,
and derivations using validated schemas and versioned prompts. Log attempts,
failures, abstentions, and acceptance separately from accepted epistemic records.
Use explicit review interactively. Declare a separate automated acceptance policy
for experiments, without hidden human help for Holon alone.
Compare supplied correct structure, deliberately damaged structure, and real
model-extracted structure. Implement UI-7 and UI-8 over the same operations.

**Exit:** the full language-to-action loop is measurable; answers cite stored
evidence, proposed writes require review interactively, and extraction errors can
be separated from repair errors. Uncertain/unrelated proposals do not become facts.

### 11. Pilot, freeze, and evaluate

Measure obsolete-action rate, false retraction, retained valid knowledge,
resurrection of superseded claims, task completion, abstention/review burden, and
full lifecycle cost. Measure calibration only for a defined probability output.
Use family-disjoint development, validation, and final test sets; repeated model
samples are not independent scenario families. Use paired comparisons and
uncertainty intervals clustered by family. Choose final sample size from pilot
variance and the smallest useful effect, then freeze policies, prompts, models,
sampling settings, and data before held-out runs.

Include mechanism ablations and accuracy/cost comparisons across lineage quality,
history length, reuse, and update frequency. If feasible, add a small independently
annotated public-data transfer set, reporting it separately from synthetic results.
Publish fixtures, seeds, schedules, prompts, scoring, configurations, failures,
and negative findings where redistribution is permitted.

**Exit:** a reproducible, bounded conclusion states when repair helps, when simpler
methods win, and where evidence is insufficient. A positive outcome is not required.

## Interface workstream

Proposed design: a local browser interface over shared Python application
operations. A thin FastAPI layer is a candidate, not a finalized dependency
decision. Keep UI dependencies optional and preserve the independent CLI.
No hosted deployment, remote access, or desktop packaging is needed initially.

| ID | Work | Status | Exit evidence |
| --- | --- | --- | --- |
| UI-1 | Extract model preview/acceptance orchestration from the CLI into shared operations | Not started | Both interfaces use identical validation and update semantics |
| UI-2 | Add proposition/observation listing, search, and filtering | Not started | Users select records without UUID knowledge |
| UI-3 | Add local API/browser shell with operation-scoped database connections and transactions | Not started | Read/write boundaries and errors are tested; no shared unsafe SQLite connection |
| UI-4 | Add claim, observation, evidence, history, and projection views | Not started | Current support, conflict, withdrawals, and provenance are inspectable |
| UI-5 | Add report forms, interpretation previews, and correction controls | Not started | Explicit acceptance, safe repeated submissions, and stale-preview revalidation |
| UI-6 | Add dependency, alternative-support, and repair views during steps 6–9 | Not started | Before/after state and reasons for repair are visible |
| UI-7 | Add grounded conversational questions during step 10 | Not started | Answers reference actual records and expose unknowns/conflicts |
| UI-8 | Add conversational change proposals and interface parity checks | Not started | Natural-language requests produce reviewable operations; chat/GUI/CLI agree |

Conversation history is not automatically accepted evidence. The model proposes
operations; the service validates and applies accepted changes. A natural-language
request that does not identify a claim or correction unambiguously needs
clarification. Do not disguise experimental projection means as truth confidence
in the interface. Streaming and visual polish can follow the first usable flow.

## Session handoff rules

At the beginning of a future session:

1. Read this document and `docs/roadmap.md`; inspect working-tree changes and
   current commits before assuming the recorded baseline is still current.
2. Read the contracts and implementation relevant to the next incomplete step.
3. Resume the **next concrete action** above or any recorded in-progress work.
   Planning acceptance is not evidence that a later step has been implemented.
4. Keep the user's current task scope authoritative. This plan does not authorize
   automatic commits, deployment, or migration of the user's working database.

At the end of each implementation session:

1. Update the tracker and affected UI rows with status, artifact paths, and
   verification evidence. Record commit IDs only when commits actually exist.
2. Update the top checkpoint with the exact next action, unfinished work, blockers,
   and current verification result. Do not mark a step complete without its exit.
3. Keep the roadmap's next action aligned; update architecture and semantic
   contracts when implemented behavior changes. Preserve historical decisions.
4. Record scope/order changes and their reasons in the session log below.
5. Keep generated runs in ignored runtime/output locations with reproduction
   instructions; commit protocols, fixtures, and scoring code when authorized.

## Session log

| Date | Work completed | Verification | Next action |
| --- | --- | --- | --- |
| 2026-11-03 | Reviewed current repo, selected opportunity 1, documented research/UI sequence and handoff tracking | GitHub/local baseline `a98c576`; 48 existing tests passed; no implementation changes | Step 1: draft experiment 003 protocol and pre-result criteria |
| 2026-11-03 | Completed step 1 protocol draft v0.1; specified pilot conditions, scoring, baselines, budgets, practical margins, and freeze requirements | Documentation links/consistency checked; no benchmark code, experiments, or new application test run | Step 2: implement experiment 002 adversarial Beta checks |
| 2026-11-05 | Completed step 2: deterministic adversarial runner, fixed inputs, frozen legacy schema, JSON diagnostics and saved explanation; added runner integration tests | 12/12 scenarios; 51/51 repository tests; wrong expectation detected under Python optimization; core behavior/runtime database unchanged | Step 3: small replayable project world and deterministic scorer for experiment 003 |
| 2026-11-05 | Completed step 3: seeded project-world generator, public/private contracts, resumable public replay, offline action and retention scoring, candidate catalogue | 16 new environment/scorer tests; 67/67 full suite; 144 paired views structurally checked; no models or comparative outcomes | Step 4: implement four baseline adapters, shared actor contract, restart persistence and cost counters on development cases |
| 2026-11-06 | Completed step 4: H0/LWW/RR/RB, common structured actor, process-boundary persistence, costs, budgets and audit isolation; corrected shared-report room audit labels in generator v1.1 | 13 new baseline tests; 80/80 full suite; development-only smoke comparisons, no research conclusion | Step 5: minimal browser workspace, UI-1 through UI-5 |

## References and scope of review

- Source assessment: *AI_Systems_Research_Gaps_2026-11-03.md*,
  [saved research document](https://chatgpt.com/library?file_id=libfile_ba6f30b2327c8191b07e44fb8719cf78&account_id=personal).
  This plan is self-contained; access to that document is not needed to resume.
- [Reviewed Holon commit](https://github.com/nadavids42/holon/commit/a98c576cd973dd342b1f2f6eb94da08ab190f66a).
- [BELIEFMEM](https://aclanthology.org/2026.findings-emnlp.576/): prior work on
  history-preserving belief revision; use for comparison and novelty boundaries.
- [CPB](https://arxiv.org/html/2609.30813v1), Appendix S: correction was untested
  by its compared policies; this motivates investigation, not a guarantee of novelty.
- [FastAPI documentation](https://fastapi.tiangolo.com/): candidate interface layer.

The planning review established fit with the current code and checked these close
research references. It was not a new exhaustive literature review. Recheck
related work before freezing any publication-level novelty claim.
