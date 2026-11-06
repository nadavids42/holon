# Adversarial binary Beta validation

Implemented engineering acceptance milestone, 2026-11-05: **12/12 scenarios
passed**, with **51/51 repository tests passing**, including runner integration
and deliberate-failure checks. No production code changes were required.

From the repository root, using Python 3.10+ and the standard library:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/002-binary-beta/run.py --output runs/beta-validation
```

Choose a **new** output directory on each saved run. The runner refuses to
overwrite an existing directory. `runs/` is Git-ignored. Without `--output`, it
prints the complete JSON report to stdout. Exit codes are 0 for all checks
passing, 1 for scenario failures, and 2 for fixture/output setup errors.

The runner creates and removes temporary databases, uses actual CLI subprocesses
for restart checks, and never opens `runtime/holon.sqlite3`. No Ollama server or
model is needed. Imports resolve against this checkout's `src/` directory.

Run all repository tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -q
```

## Inputs and results

- [protocol.md](protocol.md): acceptance criteria fixed before the initial run.
- [fixtures.json](fixtures.json): deterministic input groups and explicit expected
  values. Hundreds of repeated reports expand to distinct evidence identities.
- [legacy-v0.sql](legacy-v0.sql): frozen old-schema fixture, migrated only on a copy.
- [run.py](run.py): scenarios, independent rational-arithmetic readout checks,
  result capture, and explanation rendering.
- [example.md](example.md): saved explanation from the passing canonical run,
  including every input record, cluster multiplier, and readout field.

A saved run contains `results.json` and `explanation.md`. JSON includes per-case
verdicts, tracebacks on failure, evidence/checkpoint snapshots, seed, policy and
dynamics versions, source/fixture hashes, Git commit/working-tree status, and
Python/SQLite versions. Scenarios continue after an independent failure.

The fixtures and their readouts are reproducible. Workspace-generated UUIDs and
timestamps vary between fresh runs; their exact values/digests are preserved for
within-ledger restart checks. Different fresh runs need not have byte-identical
JSON. Hashes identify the tested source files even before a commit exists.

## What the checks demonstrate

- No evidence and balanced opposing evidence can share mean 0.5 while having
  different strength, variance, and opposing mass.
- Five hundred copies in one declared cluster contribute raw support 500 but
  effective support 1; ten separately stipulated origins contribute 10.
- Caps apply separately to support and contradiction. Recombine raw ledger
  partitions before projection; capped totals are not additive.
- Exact keyed retries add nothing; changed requests fail without partial writes.
- Corrections and reinterpretations preserve lineage and history. Other links
  to a reused observation survive. Withdrawing all links restores the prior.
- Initialized-store reads are unchanged across service and CLI restarts.
- Legacy metadata is never silently invented: readout is blocked until explicit
  annotation, and annotated legacy coverage remains approximate.
- Invalid input and injected transaction/migration failures preserve the store.
  Accepted finite masses with an overflowing aggregate produce an explicit
  read error without corrupting the ledger; withdrawal can restore readability.

## Interpretation limits

A zero-mass active support link yields qualitative `supported` with a prior
quantitative readout. Opposing active evidence yields `contested` even when the
Beta mean favors support. Neither result resolves truth or supplies a calibrated
probability. Separate source strings do not prove independence.

The example includes a supplied pure-projector exclusion; persistent eligibility
and dependent-conclusion repair are not implemented by this milestone.

Step 2 is complete. Next build the small replayable project environment for
[experiment 003](../003-evidence-revision/protocol.md), following
[the maintained research plan](../../docs/evidence-revision-research-plan.md).
