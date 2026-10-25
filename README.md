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

**Minimal persistent workspace prototype.** The repository includes a standard-library Python CLI backed by SQLite. It accepts explicitly structured reports and preserves evidence and qualitative belief revisions. An optional Ollama adapter proposes report interpretations for explicit human acceptance.

Initial development will use the existing Ubuntu workstation and RTX 5060 Ti 16 GB GPU. Additional hardware is conditional on measured experimental needs.

The core loop uses deterministic policies without model calls. Optional model interpretation feeds accepted proposals into the same loop. Multiple specialists remain deferred.

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
caller-supplied text; temporal reasoning is not implemented.

### Withdraw or correct evidence

Copy an `evidence_id` from report output or inspection in place of `EVIDENCE_ID`:

```bash
python3 -m holon.cli withdraw EVIDENCE_ID --actor "Nick" --reason "Incorrect interpretation"
```

Withdrawal applies to that evidence link. The original observation and link
remain inspectable, with the actor, reason, and withdrawal time. Beliefs use
only active evidence: withdrawing the contrary link restores `supported`;
withdrawing every link yields `insufficient_evidence`.

To withdraw a link and replace it with a corrected report atomically:

```bash
python3 -m holon.cli correct EVIDENCE_ID --actor "Nick" --reason "Sensor report misread" --source "sensor B" --text "Closed at T0" --relation supports
```

Inspection links the withdrawn evidence to its replacement and retains every
revision. Correction supplies a caller-assigned relation; it does not invoke
the model. Actor attribution is caller-supplied, not authenticated. A withdrawn
link cannot be withdrawn or corrected again; correct its active replacement
if another correction is needed. Invalid or failed corrections roll back.
Existing databases are upgraded automatically on opening; back up runtime
state before using a newer version against an older database.

Run the acceptance checks:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Interpret a natural-language report

With Ollama running and a model already installed, use an existing proposition ID:

```bash
holon interpret ID --source "sensor B" --text "At T0, sensor B detected that the lab door was open." --model qwen3:14b
```

The default model is `qwen3:14b`; select an installed model with `--model`.
Use `ollama list` to check installed models. The default server is
`http://127.0.0.1:11434`; override with `--host` and `--timeout` (seconds,
default 120) if needed. No model download or server startup is performed by Holon.
The full claim, scope, and report are sent to the selected server.

The command previews the relation, reason, source, original report, and model.
Only `y` or `yes` at the acceptance prompt stores supporting/contradicting evidence.
Declining, EOF, uncertain/unrelated results, invalid model output, or failed requests
produce no evidence or belief update. Accepted interpretations preserve the model
identifier, prompt version, and reason separately from the verbatim report.
Existing databases gain an additive metadata table automatically.

The model evaluates the existing claim only; it does not invent claims or establish
truth. Ambiguous or missing observation time should yield `uncertain`. Model
classification can still be wrong, so inspect the preview before accepting.

## Binary Beta projection

New reports and accepted model interpretations now retain versioned stipulated
impact metadata. The default mass is 1; it is an experimental impact unit, not
model confidence. Reports from the same source string share a dependency cluster.
Each cluster contributes at most one unit per sign under `binary-beta-v1`.
Different source strings do not prove independence.

```bash
holon project ID
holon inspect ID --projection
holon report ID --source "sensor A" --text "Closed at T0" --relation supports --mass 0.5 --event-key reading-001
```

`project` returns replay coverage, policy/dynamics versions and input digests,
per-evidence metadata, and a `readout` containing the Beta parameters,
mean/variance, raw/effective mass, cluster multipliers, and conflict diagnostics.
It does not change qualitative status or write a belief revision. Repeating a
report/correction with the same `--event-key` and identical request returns the
existing IDs without adding evidence. Keys are scoped to source and proposition;
changed content or metadata under the same key is rejected. The returned status
on a retry is the current qualitative status. Identical text without an event key
remains a separate raw report, subject to the source-cluster cap.

For reports known to share an origin across sources, give each the same explicit
cluster and attribution:

```bash
holon report ID --source "document B" --text "Closed at T0" --relation supports --cluster-id original-document --cluster-actor "Nick" --cluster-reason "Copied from the same document"
```

`correct` also accepts `--mass` and `--event-key`. Corrections retain the original
cluster, even when the source label changes. Source identity and attribution are
caller assertions. Cluster reassignment and learned reliability are future work.

Opening an older database performs an atomic, versioned schema upgrade without
inventing evidence metadata. Back up the database before first use with this
version. A proposition with missing legacy metadata reports `replay_incomplete`
and `readout: null`. To explicitly attach unit-impact/source-cluster assumptions:

```bash
holon migrate-impacts ID --actor "Nick" --reason "Accept experimental unit-impact assumptions for legacy reports"
holon project ID
```

That operation preserves originals and records its assumptions; coverage becomes
`replay_approximate`. Repeating it adds nothing when no records need annotation.
Fresh records under the declared impact contract are `replay_complete`, which
means reconstructible under that experimental contract, not empirically calibrated.
Policy and impact metadata are append-only. The original qualitative inspection
and revision history remain available independently.

## Next steps

Run the deterministic adversarial scenarios and explanation checks in
[the implementation plan](docs/binary-beta-implementation-plan.md), then use the
results to guide temporal policy and reliability work. The pure projector,
persistent metadata, explicit legacy annotation, and CLI integration are implemented.

## Living charter

[PROJECT_HOLON.md](PROJECT_HOLON.md) is the authoritative living charter. It records agreed decisions, working hypotheses, proposed designs, open questions, experiments, and milestones. It will evolve as discussions and evidence refine the project.

## License

The repository's original code and documentation are available under the [MIT License](LICENSE). Third-party models, datasets, and dependencies retain their own licenses.
