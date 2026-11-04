# Immediate roadmap

## Active plan and next action

The accepted next research direction is **evidence revision under incomplete
provenance**, extending the existing workspace. The authoritative progress tracker,
exit criteria, UI sequence, and future-session handoff are in
[the evidence revision research plan](evidence-revision-research-plan.md).

**Current checkpoint:** step 1 complete as
[experiment protocol draft v0.1](../experiments/003-evidence-revision/protocol.md).
No benchmark or UI code has been implemented. The reviewed code baseline is
`a98c576`, with 48 existing tests passing at the planning review.

**Next action:** implement adversarial Beta validation in planned
`experiments/002-binary-beta/`, following slice 4 of the Beta plan: deterministic
fixtures, expected properties, a runner, and traceable explanations. Then build
the small comparative environment under experiment 003 (step 3). The protocol
defines the study; it does not supply a runnable benchmark yet.

A minimal local GUI follows the environment and initial baselines (step 5).
Grounded chat follows later (step 10). Neither is a prerequisite for starting the
research protocol. Update this checkpoint and the plan together as work progresses.

## Existing engineering foundation

1. Minimal structured persistent belief loop: implemented; see experiment 001.
2. Optional Ollama interpretation implemented with preview, validation, and explicit acceptance; live local model verification remains.
3. Evidence withdrawal/correction: implemented and tested, including recovery,
   retained provenance, restart persistence, legacy migration, and rollback.
4. Pure binary Beta domain projector: implemented and tested. Versioned impact
   metadata, migration, and workspace/CLI integration are also implemented.
   Deterministic adversarial scenarios and explanation checks are next. Follow
   `binary-beta-implementation-plan.md` for persistence and validation slices.
5. Comparative research criteria are drafted in experiment 003; its evaluation
   harness and runs are not implemented. Follow the active plan above.

Foundational architecture follow-up: the semantic contract is in
`epistemic-semantic-contract.md` and the implementation plan is in
`observation-provenance-lifecycle-plan.md`. Observation-time provenance,
observation reuse, and atomic evidence reinterpretation are implemented. An
integrated CLI scenario exercises these features across process restarts on a
migrated copy of a version-1 database; see `tests/integration/test_lifecycle_scenario.py`.
Temporal inference and historical quantitative replay remain future work.

The broader milestones and boundaries remain in `PROJECT_HOLON.md`.
