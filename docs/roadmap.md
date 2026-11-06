# Immediate roadmap

## Active plan and next action

The accepted next research direction is **evidence revision under incomplete
provenance**, extending the existing workspace. The authoritative progress tracker,
exit criteria, UI sequence, and future-session handoff are in
[the evidence revision research plan](evidence-revision-research-plan.md).

**Current checkpoint (2026-11-06):** steps 1–4 are complete: protocol,
[adversarial Beta validation](../experiments/002-binary-beta/README.md),
[the replayable environment](../experiments/003-evidence-revision/README.md), and
[H0/LWW/RR/RB structured baselines](../experiments/003-evidence-revision/baselines.md).
All 12 adversarial scenarios and 80 repository tests pass. Core behavior is
unchanged. The common actor/harness persists method state across processes,
meters work and runtime, isolates audits, and scores development episodes offline.
These are engineering smoke comparisons, not a frozen research evaluation.

**Next action:** step 5, UI-1 through UI-5: the local browser workspace for
observations, interpretation, acceptance, inspection and correction. Start with
the service/API boundary; preserve CLI behavior. Before a research pilot, review
candidate family grouping/labels and freeze the actor/baseline configuration.

Grounded chat follows later (step 10). Neither is a prerequisite for starting the
research protocol. Update this checkpoint and the plan together as work progresses.

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
   Baselines, complete method cost accounting and comparative runs remain next.

Foundational architecture follow-up: the semantic contract is in
`epistemic-semantic-contract.md` and the implementation plan is in
`observation-provenance-lifecycle-plan.md`. Observation-time provenance,
observation reuse, and atomic evidence reinterpretation are implemented. An
integrated CLI scenario exercises these features across process restarts on a
migrated copy of a version-1 database; see `tests/integration/test_lifecycle_scenario.py`.
Temporal inference and historical quantitative replay remain future work.

The broader milestones and boundaries remain in `PROJECT_HOLON.md`.
