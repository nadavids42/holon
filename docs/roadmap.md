# Immediate roadmap

## Active plan and next action

The accepted next research direction is **evidence revision under incomplete
provenance**, extending the existing workspace. The authoritative progress tracker,
exit criteria, UI sequence, and future-session handoff are in
[the evidence revision research plan](evidence-revision-research-plan.md).

**Current checkpoint (2026-11-08):** steps 1–4 are complete; step 6 slices 1–4
are implemented with the [derivation domain contract](derivation-lineage-contract.md).
Immutable signed claims and justifications represent AND premises and OR
alternatives; validated graphs reject circular dependencies. Schema-3 storage preserves
justifications and attributed origin assignment/merge/reversal history. Shared service, CLI and local API
operations now support atomic composition and decoded inspection. All 134 tests
pass. GUI derivation and origin controls are implemented; live acceptance remains
pending. Belief updates remain future work.

Step 5's GUI is implemented. The user confirmed live creation of claims and
observations, model preview/acceptance, and conflicting evidence showing contested
status. The remaining [browser walkthrough](browser-workspace.md) stays open;
the user authorized proceeding with step 6 alongside those checks.

**Next action:** run the slice 4 walkthrough in the browser guide, then specify
step 7 eligibility propagation and selective repair. The new controls record
structure only; they do not update beliefs or projection clusters.
Before a research pilot, review family grouping/labels and freeze configuration.

Grounded chat follows later (step 10). Keep the CLI and headless research harness
runnable. Update this checkpoint and the plan together as work progresses.

## Existing engineering foundation

1. Minimal structured persistent belief loop: implemented; see experiment 001.
2. Optional Ollama interpretation implemented with preview, validation, and explicit acceptance; live local model verification remains.
3. Evidence withdrawal/correction: implemented and tested, including recovery,
   retained provenance, restart persistence, legacy migration, and rollback.
4. Pure binary Beta domain projector: implemented and tested. Versioned impact
   metadata, migration, and workspace/CLI integration are also implemented.
   Deterministic adversarial scenarios and traceable explanations are complete in
   experiment 002. See `binary-beta-implementation-plan.md` for the slice history.
5. Experiment 003 has criteria, a 36-family candidate generator (four paired
   provenance conditions), replay/checkpoints, and action/control-audit scorers.
   H0/LWW/RR/RB baselines, method cost accounting, and development comparisons
   are implemented. Frozen research evaluation and later comparators remain future work.

Foundational architecture follow-up: the semantic contract is in
`epistemic-semantic-contract.md` and the implementation plan is in
`observation-provenance-lifecycle-plan.md`. Observation-time provenance,
observation reuse, and atomic evidence reinterpretation are implemented. An
integrated CLI scenario exercises these features across process restarts on a
migrated copy of a version-1 database; see `tests/integration/test_lifecycle_scenario.py`.
Temporal inference and historical quantitative replay remain future work.

The broader milestones and boundaries remain in `PROJECT_HOLON.md`.
