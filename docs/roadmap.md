# Immediate roadmap

1. Minimal structured persistent belief loop: implemented; see experiment 001.
2. Optional Ollama interpretation implemented with preview, validation, and explicit acceptance; live local model verification remains.
3. Evidence withdrawal/correction: implemented and tested, including recovery,
   retained provenance, restart persistence, legacy migration, and rollback.
4. Pure binary Beta domain projector: implemented and tested. Versioned impact
   metadata, migration, and workspace/CLI integration are also implemented.
   Deterministic adversarial scenarios and explanation checks are next. Follow
   `binary-beta-implementation-plan.md` for persistence and validation slices.
5. Define comparative research criteria and run controlled evaluations.

Foundational architecture follow-up: the semantic contract is in
`epistemic-semantic-contract.md` and the implementation plan is in
`observation-provenance-lifecycle-plan.md`. Observation-time provenance,
observation reuse, and atomic evidence reinterpretation are implemented. An
integrated CLI scenario exercises these features across process restarts on a
migrated copy of a version-1 database; see `tests/integration/test_lifecycle_scenario.py`.
Temporal inference and historical quantitative replay remain future work.

The broader milestones and boundaries remain in `PROJECT_HOLON.md`.
