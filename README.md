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

**Minimal persistent workspace prototype.** The repository includes a standard-library Python CLI backed by SQLite. It accepts explicitly structured reports and preserves evidence and qualitative belief revisions. No model is connected yet.

Initial development will use the existing Ubuntu workstation and RTX 5060 Ti 16 GB GPU. Additional hardware is conditional on measured experimental needs.

The first checkpoint uses deterministic policies without model calls. One model will be connected after the persistent loop works, before introducing multiple specialists.

## Run the prototype

From the repository root, using Python 3.10 or newer (no dependencies required):

```bash
export PYTHONPATH="$PWD/src"
python3 -m holon.cli propose "The lab door is closed" --scope "lab door at instant T0"
```

Copy the returned `proposition_id` into the following commands in place of `ID`:

```bash
python3 -m holon.cli report ID --source "sensor A" --text "Closed at T0" --relation supports
python3 -m holon.cli inspect ID
python3 -m holon.cli report ID --source "sensor B" --text "Open at T0" --relation contradicts
python3 -m holon.cli inspect ID
```

The status changes from `supported` to `contested`. Inspection includes both
reports and the full belief revision history. Each command is a separate process;
state persists in `runtime/holon.sqlite3`. Use `--db PATH` before the subcommand
to select another database. Back up runtime state separately; it is ignored by Git.

Evidence relations are supplied by the caller, not inferred from text. States
summarize evidence presence, not truth or calibrated confidence. Scope is explicit
caller-supplied text; temporal reasoning and corrections are not implemented.

Run the acceptance checks:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Next steps

1. Connect one model to propose structured records, with validation before storage.
2. Define and run controlled comparisons against simpler baselines.
3. Expand only when experiments justify additional mechanisms.

## Living charter

[PROJECT_HOLON.md](PROJECT_HOLON.md) is the authoritative living charter. It records agreed decisions, working hypotheses, proposed designs, open questions, experiments, and milestones. It will evolve as discussions and evidence refine the project.

## License

The repository's original code and documentation are available under the [MIT License](LICENSE). Third-party models, datasets, and dependencies retain their own licenses.
