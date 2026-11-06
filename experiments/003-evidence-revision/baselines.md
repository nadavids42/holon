# Step 4: initial structured comparison methods

Implementation checkpoint: 2026-11-06. Track S only. These are development
engineering comparisons, not a frozen pilot, held-out evaluation, or evidence for
selective repair. No selective repair method or model interpreter is implemented.
The next implementation step is step 5's minimal local graphical workspace.

## Run a development episode

From the repository root, use fresh output directories:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/run.py generate --motif 0 --variant 0 --output runs/step4-world
PYTHONDONTWRITEBYTECODE=1 python3 experiments/003-evidence-revision/compare.py --public runs/step4-world/public/episode.json --private runs/step4-world/private/episode.json --output runs/step4-comparison
```

`compare.py` runs all four methods in seeded randomized order, concurrency one.
It rejects validation-designated families and existing output directories.
`--seed` controls method order; generation has its own seed. `--limit` sets the
same logical-operation budget for every method (default 100,000 per episode).
Audits have separate budgets of that size. The generated fixture size bounds the
initial Track S workload; this is not a token budget or a timing benchmark.

Each method gets only serialized public prefixes in a separate worker process.
The trusted harness retains the full schedule and private bundle. Scoring happens
after the method finishes, and no scores return to a worker. Filesystem isolation
against malicious methods is **not** supplied: these are trusted Python adapters,
not a security sandbox. A future untrusted method requires OS-level isolation.

## Method definitions

All four receive the same structured source archive, public updates, task
options, and rules. They all archive incoming sources; archive access is metered.
H0 and LWW retain incremental memory. RR and RB reconstruct query-local claims
from sources and discard the reconstruction after answering.

| ID | Implementation | Memory and query behavior | Known limitation |
| --- | --- | --- | --- |
| H0 | Actual current `holon.workspace.service.Workspace`, SQLite, `binary-beta-v1` | One proposition per key/value/subject scope, one observation per fragment; supporting links from supplied statements. Explicit source corrections withdraw only the targeted statement's links; withdrawals remove only named fragment links. Export native status, active evidence, history and projection. | No dependency propagation, automatic copy clustering, or temporal adjudication. Any queried key with a world-change event is unsupported and yields no claim. Conflicting supported values reach the common actor as a conflict. Beta means never select truth. |
| LWW | Local mechanism-class implementation | Latest arrival per exact key/subject scope, persistent fact map. Explicit corrections/withdrawals delete a matching retained target; a delayed copy can overwrite the replacement. | No lineage repair, fallback history after deleting the sole retained value, or interval splitting for world changes. Different subject scopes can remain conflicting. |
| RR | Local mechanism-class implementation | Filter by normalized task keys; expand through public references, earlier fragments and related updates; reconstruct relevant usable claims anew at every query. | Literal UUID references in supplied prose are recognized, not general language interpretation. Repeated scans are charged. Fallible declarations can cause over-invalidation until clarified. |
| RB | Local mechanism-class implementation | Reread the entire available source archive and reconstruct usable claims in arrival order at every query/audit. | Same reconstruction semantics as RR, but no filter; full repeated work is charged. No incremental/selective repair or persistent dependency graph. |

H0 does not modify production code. Its supplied positive statements become
support links; different values remain separate propositions, with exclusivity
handled by the common actor rather than invented contradiction evidence. Project
and source subject dates are recorded in proposition scope. Mapping a date to an
eligible snapshot is adapter normalization; general temporal reasoning is not
added to Holon. Native `recorded_at` timestamps are ingestion timestamps; original
public arrival/subject metadata remain in the adapter archive.

RR retrieval order is arrival order. Its initial filter selects source statements
whose normalized key is required by the task, then repeatedly scans public
references and update targets until closure. No source is truncated or ranked
by gold labels. Every lexical closure pass reads and charges the scanned text;
this deliberately simple retrieval implementation can cost more than rebuilding
on small archives. No semantic retrieval/model call or free retrieval index is
claimed. Report-content lookups use a common direct-ID archive read for all four.

RR/RB reconstruction uses declared edges and literal fragment UUID references in
public text. Intervention references identify targets rather than premises.
A correction invalidates only the named keys in its targets; unaffected keys
survive. A world change invalidates the old key at/after its effective time;
prior-time answers retain the original plus the change notice as justification.
Withdrawals invalidate target evidence. A lineage correction clears the target's
prior parent assignment. Recursion checks premise eligibility afresh, refusing
cycles or unknown references. Matching-key copies inherit that key's eligibility;
cross-key derivations require all referenced premise keys. Alternative source
records remain separate sufficient supports. These rules are limited to the
supplied structured grammar; they are not a general-purpose revision calculus.

## Common decision contract

Versions: `structured-baselines-v1`, `structured-actor-v1`.

A method emits an ordered list of claims:

```json
{"key":"release_date","value":"2026-11-16","citations":["public-fragment-id"],"status":"supported"}
```

The actor only consumes these claims and the current public task. It does not
search the archive, follow dependencies, repair state, or see private labels.
It recognizes the protocol's fixed task grammar; unknown questions abstain.
A required key must have exactly one distinct supported value. Several proofs
of the same value are alternatives: select the first in stable adapter order.
Preparation subtracts one calendar day from release. Readiness requires both
owner and a `yes` approval. Missing/conflicting prerequisites produce abstention,
even if the finite options contain only one of the conflicting values. Proposed
actions outside the allowed options also abstain. Citations are the selected
sufficient proof(s), deduplicated in order, not every retrieved record.

Audits resolve the same claim view into `assert`, `deny`, or `unresolved`.
They run on copied JSON state and, for H0, a copied database. They cannot change
live method state. Audit responses/costs are separate from task responses/costs.
The public grammar and actor must be reviewed/frozen before a scored pilot;
this checkpoint does not claim coverage of arbitrary public prose/rule changes.

## Persistence, budgets, and costs

Every boundary uses a fresh Python worker, including the required restart after
task four. The worker reloads its own JSON checkpoint and H0 SQLite database;
ingestion processes only unseen events. Prefix hashes reject changed/truncated
history. The public context and method/version/episode must match the checkpoint.
At the scheduled restart the trusted replay checkpoint also round-trips through
disk. This intentionally measures cold-worker behavior throughout, not warm
service throughput. No method state is reconstructed from private labels.

Persisted files include the source archive, ingestion position, method-specific
facts/ID mappings, counters and H0 inspection diagnostics. Snapshot sizes include
that archive and diagnostics. Transient Python peak memory is not measured.
A process crash leaves the comparison failed; there is no cross-file transactional
recovery between H0's database and the adapter JSON. Do not resume a failed run
in place; rerun in a new directory. Clean scheduled restarts are tested.

Costs are a vector:

- Logical source reads/UTF-8 source bytes, records visited, rule evaluations,
  logical writes, and Workspace inspections, grouped by ingestion, maintenance,
  retrieval, validation, and actor. Logical counters describe the instrumented
  algorithm; they are not every Python instruction or physical database I/O.
- Actual SQLite rows changed, JSON checkpoint writes/bytes, per-call input bytes,
  and peak persisted state bytes. Physical SQLite page-write bytes are not inferred.
- Worker CPU/wall time, ingestion/query wall time, plus full subprocess CPU/wall
  time including startup and checkpoint I/O (Linux/POSIX runner). Query time
  includes its retrieval/reconstruction; no fabricated per-rule latency estimates.
- Audit process/counters separately; offline scoring wall time separately.
- Model calls/tokens and retries are exactly zero in this deterministic track.

The budget counts source reads + records visited + rule evaluations + logical
writes. The first operation over budget is recorded, then the method latches
exhaustion and abstains on remaining tasks. Exhausted episodes stay in scoring
denominators. A partially completed update is not retried after exhaustion.
Input parsing, checkpoint serialization, and process startup remain charged as
bytes/time outside that logical-operation limit. Each worker has a 60-second
transport timeout. Unexpected failures/timeouts stop that method, produce abstentions for remaining
tasks, and mark the comparison failed (exit 2). All six slots remain in scoring
denominators. Artifacts and elapsed process costs are retained; unfinished work
counters are explicitly unavailable, not zero-cost claims. No failed run becomes
a success or silently disappears. Before evaluation, freeze the failure/retry
aggregation policy and add Track E's model budgets.

## Saved outputs and evidence

Top-level `manifest.json` records code hashes (including actual Holon core), Git
state, configuration, seed/order, paired input digests, and complete/failed status.
`summary.json` contains per-method task metrics and audit scores. Each method
folder contains public inputs, raw claim views, answers, costs, replay restart,
state, and offline scores. Timing and native Holon UUIDs/timestamps vary between
runs; canonical action/citation responses and logical work are deterministic.
Existing results cannot be overwritten. Exit 0 means all methods were run and
scored, not that all methods succeeded at their tasks.

Generator **v1.1** corrects a discovered label omission: the shared report's
unchanged `room` statement is an alternative valid room-audit citation. Only its
release statement was corrected. Public schedules/IDs are unchanged from v1;
private labels/metadata and source hashes change. This is a documented pre-pilot
label amendment, not a change to the success thresholds. Generate fresh bundles
for step 4; old saved v1 bundles retain their original labels.

All 80 repository tests pass, including 13 baseline acceptance tests.
Acceptance tests cover expected H0 conflict/LWW stale-copy failures, RR/RB
correction and world-change histories, alternative approvals, incomplete lineage,
private-truth independence, unknown-task/conflict abstention, budget exhaustion,
link-local updates in real SQLite, checkpoint retry identity, audit immutability,
and the full subprocess harness. Synthetic unresolved tests are engineering
checks; the comparison CLI does not run validation-designated families.

Next: **step 5, UI-1 through UI-5**, using the existing Workspace service.
Before the research pilot: review family grouping and gold labels, freeze actor
and baseline configuration, add the required retrieval/history-preserving
comparators, implement selective repair, and run the declared evaluation. Track E,
chat/extraction, model cost limits, and self-generated summary writeback remain
later work. Do not infer a research advantage from this worked-example smoke run.
