# Project Holon

An experimental persistent cognitive architecture combining specialized neural models with a shared, evidence-driven workspace for memory, belief revision, and coordinated reasoning.

Holon investigates whether a system of cooperating cognitive components can develop more coherent, calibrated, and adaptable behavior over time than simpler approaches under comparable resource budgets.

## Core idea

The shared cognitive workspace is the architectural center. It preserves knowledge and its history independently of any model or conversation, distinguishing:

- **Observations:** what the system encountered.
- **Propositions:** claims that can be evaluated.
- **Evidence:** support, contradiction, or qualification of those claims.
- **Beliefs:** the system's current, revisable stance toward a claim.
- **Meta-beliefs:** assessments of beliefs and the processes that produced them.

Specialists contribute through explicit interfaces. An executive coordinates attention and priorities, while separate permissions govern external actions. Provenance, unresolved contradictions, and uncertainty remain inspectable.

## Research directions

- Persistent memory and evidence-sensitive belief revision.
- Specialized components with shared awareness and selective participation.
- Asynchronous, event-driven cognition with bounded compute and loop controls.
- Development through accumulated experience, with pretrained priors distinguished from acquired evidence.
- Controlled comparisons, mechanism ablations, and reproducible evaluation.

These are research directions and hypotheses, not demonstrated capabilities. Holon makes no claim of consciousness, general intelligence, or superiority to a strong single-model system.

## Current status

**Charter and experimental design stage.** This repository currently contains the project charter and repository documentation. There is no runnable implementation or installation procedure yet.

Initial development will use the existing Ubuntu workstation and RTX 5060 Ti 16 GB GPU. Additional hardware is conditional on measured experimental needs.

The first prototype will use one model and deterministic policies to establish a minimal persistent epistemic workspace before introducing multiple specialists.

## Planned first steps

1. Select a narrow belief-revision benchmark and define success and failure criteria.
2. Specify minimal schemas for observations, propositions, evidence, beliefs, and meta-beliefs.
3. Build the workspace with provenance, revision history, and contradiction tracking.
4. Add inspection, replay, and cost accounting.
5. Compare against controlled baselines before expanding the architecture.

## Living charter

[PROJECT_HOLON.md](PROJECT_HOLON.md) is the authoritative living charter. It records agreed decisions, working hypotheses, proposed designs, open questions, experiments, and milestones. It will evolve as discussions and evidence refine the project.

## License

The repository's original code and documentation are available under the [MIT License](LICENSE). Third-party models, datasets, and dependencies retain their own licenses.
