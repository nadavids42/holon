# Experiment 003: Evidence revision under incomplete provenance

Status: protocol draft v0.1, 2026-11-03 (America/New_York).
Implementation checkpoint, 2026-11-06: environment and initial Track S H0/LWW/RR/RB
methods are implemented with a common actor, persisted process-boundary state,
cost accounting and isolated audits. See [baselines.md](baselines.md) for exact
method semantics, commands, limits and the generator v1.1 label amendment.
Development engineering comparisons exist; no frozen evaluation or selective
repair result exists. Research thresholds remain v0.1.
This is a local pre-result design, not an externally registered preregistration.

Parent: [research plan and progress tracker](../../docs/evidence-revision-research-plan.md).
Prerequisite: [binary Beta validation, slice 4](../../docs/binary-beta-implementation-plan.md).
Semantics: [epistemic contract](../../docs/epistemic-semantic-contract.md).
Reviewed code baseline: `a98c576cd973dd342b1f2f6eb94da08ab190f66a`.

## 1. Question, hypothesis, and scope

**Question:** When evidence changes and provenance is incomplete, does selective
repair reduce obsolete actions while retaining valid knowledge, compared with
rereading available sources?

**Candidate mechanism:** record derivations and alternative justifications;
recompute affected evidence eligibility after updates; reread sources when known
lineage is inadequate. Separate copy lineage from logical dependence. Retain
original records and explain changes. These are hypotheses to implement and test,
not capabilities demonstrated by current Holon.

**Primary comparison:** selective repair with bounded rereading versus
source-filtered rereading, using the same available evidence and resource limits.
The primary operating regime is imperfect provenance. Complete-lineage results
are a diagnostic control, not sufficient evidence for the research claim.

Start with one agent, one local workspace, and a synthetic project-planning
environment. Keep model weights fixed. Actions affect only the simulator. Do not
introduce multiple specialists, learned source reliability, automatic probability
calibration, real external tools, or a general temporal reasoning engine.

The study must be able to conclude that a simpler method is preferable. It does
not test whether Holon is generally intelligent or whether belief revision is new.

## 2. Bounded project world

An episode concerns one fictional project. Its initial target size is 8–12
scorable facts, 12–24 short source fragments, and a derivation depth of at most
three. Facts concern release dates, project owners, required approvals, and
preparation tasks. All interpretation rules needed for scoring are supplied in
the public task specification, including calendar conventions; no business or
calendar knowledge may be required implicitly.

For example, preparation is due one **calendar day** before release, not an
unstated business-day rule. Explicit conjunctions can require both an approved
release and an available owner; alternatives can allow either of two independently
valid approval records to satisfy a prerequisite.

The simulator owns three distinct views:

| View | Contents | Access |
| --- | --- | --- |
| World/scoring state | Actual facts over subject time, true lineage, valid support sets, acceptable actions, answerability labels | Generator and scorer only |
| Available source archive | Reports, source-local versions, fragments, published corrections, declared references, public rules | All ordinary methods through the same interface, up to the current arrival boundary |
| Method state | Its own accepted claims, memory, inferred links, summaries, pending reviews, and logs | That method and diagnostic inspection |

World truth is not automatically source truth. Some observations contain errors;
some answers cannot be established from the exposed record. The scorer keeps
physical correctness and evidence-justified correctness separate. A lucky guess
without available justification does not count as justified task success.

There is no future-source access. Filters may use public project/source/version
metadata, but not hidden labels such as `obsolete`, `copied`, or `gold_parent`.
Opaque IDs, filenames, and output ordering must not encode those labels.

## 3. Identity, time, and update contract

- A source has a stable public identity; a published version and its fragments
  have distinct stable IDs. Exact event retries reuse their event IDs. Identical
  text in another event remains a distinct observation.
- A claim is scoped to project, subject, and subject time or interval. Rewording
  is not automatically a new fact, and similarly worded claims in different
  scopes are not automatically identical.
- An evidence link relates an observation to a claim with an interpretation.
  A derivation records required premises and alternative sufficient premise sets.
  Multiple summaries do not establish independent corroboration.
- The event schedule separates arrival order, recording time, optional observation
  time, and subject time. An unknown time remains unknown. A monotonically
  increasing event index identifies the available-information boundary.
- Every intervention names public source/fragment/claim references, not a private
  list of all affected descendants. Mapping to Holon IDs is an adapter function.

The fixture author must choose the correct update type:

| Update | Meaning | Expected treatment |
| --- | --- | --- |
| Recording correction | The stored transcription/attribution differs from what was received | Retain original; add corrected observation and replacement evidence, matching `correct` semantics |
| Reinterpretation | The observation is accurate as a record, but its evidence relation was misclassified | Retain observation; replace the selected link, matching `reinterpret` semantics |
| Source correction | The source later says its earlier assertion was wrong | Record a new observation with an explicit correction reference; preserve the accurately recorded original report |
| Withdrawal | A specified evidential use is no longer accepted, without replacement | Deactivate that link with a reason; reconsider affected justifications |
| World change | A formerly correct fact changes at a later subject time | Preserve historical validity; revise current applicability |
| Lineage correction | A copy relationship or independence assertion is discovered to be wrong | Append revised lineage; recompute affected eligibility/weight without rewriting the original assignment |

Current Holon withdrawal/correction is **link-local**. Do not covertly turn it into
source-wide revocation in an adapter. A source correction or multi-fragment
correction must explicitly identify its scope, and any propagation is part of
the tested mechanism. Rejecting a premise invalidates a justification, not
necessarily its conclusion if another sufficient justification survives.

For initial structured cases, published source corrections explicitly identify
which statement they supersede. Source identity is stipulated, not authenticated.
Conflicts without a specified resolution remain unresolved; do not silently add
source ranking, last-arrival authority, or an omniscient truth resolver.

## 4. Episode and task contract

Each scored episode has six action slots in this order:

1. Ingest the initial reports, copies, independent facts, and public rules.
2. Answer two initial tasks: a source-content lookup about the eventual update
   target (for example, which date a named report states), and one control task
   about unaffected information. The lookup tests the report's content, not
   whether its possibly erroneous assertion is true in the world.
3. Deliver the correction/change intervention. Allow the method its declared
   maintenance and rereading operations, charged to its episode budget.
4. Answer two tasks: an affected decision and an independent-support/control
   decision. Force a process restart after this checkpoint.
5. Deliver a delayed old report or summary, plus a matched unrelated update.
6. Answer two further tasks testing obsolete-action recurrence and retained
   valid information. Export final diagnostic state.

The action vocabulary is a finite set of simulator choices for each task plus
`abstain`. For example: `prepare_on(date)` with explicit candidate dates. Each
answer includes a decision and cited public source or method-memory references.
The adapter emits a canonical JSON envelope; free-text rationale is optional and
is not graded for truth. Never ask an LLM to be the unquestioned scoring oracle.

Read-only audits after each update query a fixed set of atomic claims for
`assert`, `deny`, or `unresolved`, with supporting references. Audits run on a
snapshot, provide no feedback, and cannot change the live method state. Their
inference cost is reported separately from task cost, equally for all methods.
This permits comparison with methods that do not maintain a Holon-style ledger.

An answerable task has sufficient available evidence under the public rules to
determine one allowed action. On such tasks, abstention is incomplete work.
For deliberately unresolved tasks, abstention is the justified answer; reporting
the hidden true action by guessing does not count as justified success. Report
these strata separately. Public sufficiency labels are never supplied to methods.

### Worked acceptance scenario (not evaluation data)

Use a fixed planning instant before either candidate release date. A schedule
erroneously says release is November 13; two summaries repeat it. A separate
signed assignment says Morgan owns preparation. The public rule sets preparation
one calendar day before release. A source correction explicitly replaces the
release date with November 16, saying the earlier date was a mistake. It does not
revoke Morgan's assignment. A delayed summary later repeats November 13.

After correction, the correct preparation action is November 15 and the owner
remains Morgan. The delayed summary does not reinstate November 12 preparation.
The schedule's original report is preserved as history. A matched *world-change*
case instead makes November 13 valid before an effective change and November 16
valid afterward; historical questions then differ from the correction case.

The named example is a development smoke test only. Held-out families must use
different underlying event/support structures, not merely different names/dates.
Post-correction answerable cases must expose sufficient correct evidence to
support the scored action. Do not penalize an initial source-content lookup for
failing to discover an error the source has not yet disclosed.

## 5. Scenario families and provenance conditions

Develop six motif groups; initially author six distinct families per group for
36 pilot families. Each family has its own event/support topology and paired
conditions. A motif is not itself an independent statistical observation.

| Motif | Failure being tested |
| --- | --- |
| Copied date and derived task | Obsolete conclusion survives after its sole origin is corrected |
| Alternative sufficient support | Valid conclusion is discarded when only one justification fails |
| Shared report with unrelated facts | Correction wrongly invalidates other fragments/claims |
| Joint premises and branching descendants | Partial repair misses a dependent branch or loses valid alternatives |
| False merge and later lineage correction | Independent support is collapsed and cannot be restored |
| Time/scope and delayed arrival | A world change, past truth, or delayed report is confused with correction |

For each family, construct the following paired provenance views:

| Condition | Manipulation |
| --- | --- |
| C0: complete | Correct declared copy links and derivation premises; diagnostic ceiling for supplied structure |
| C1: moderate missing | Remove 25% of eligible dependency declarations |
| C2: severe missing | Remove 75% of eligible dependency declarations |
| C3: incorrect lineage | C1 omissions plus one false merge of two distinct origins supporting a relevant claim |

Eligible declarations include copy-parent and logical-premise references; report
omissions for each type separately. Select using recorded seeds, exclude the
intervention's explicit correction target, round to the nearest count with at
least one omission where possible, and publish actual counts. A family needs
at least four eligible declarations and an independent pair for C3. Generation
must guarantee those requirements rather than dropping inconvenient cases later.

Omissions are not advertised to the method. A missing field is an empty or absent
declaration, not a truth label asserting independence. False merges are fallible
lineage annotations, not authoritative corrections. A later public discovery may
reverse them. Original prose can still suggest a dependency; do not erase those
clues merely to ensure failure. Measure recovered versus unresolved dependencies.

The primary structured comparison weights C1, C2, and C3 equally within each
family. Report C0 and each imperfect condition separately as well. Do not pool
the oracle condition into a claimed imperfect-provenance advantage.

History length, copy count, reuse frequency, and update frequency are secondary
sweeps after the core pilot. Freeze their grids and weighting before validation;
do not expand into a full factorial design without a measured need.
Add a separately reported summary-writeback extension before claiming resistance
to self-generated resurrection: each method produces a summary at the same
scheduled checkpoint and may use its own summary on the next task. Charge its
generation and ingestion, preserve references, and compare writeback on/off.
The core delayed-source scenario alone tests stale external input, not that loop.

## 6. Experimental tracks and model boundaries

**Track S — supplied structure:** all methods receive the same normalized claims,
relations, scopes, explicit updates, and the condition's fallible dependency
annotations. Only lineage is deliberately damaged in C1–C3. This isolates repair
from extraction. A common deterministic decision executor consumes each method's
claim/support view and public task rules. It has no hidden lineage, performs no
source search or repair, and abstains on unresolved prerequisites. Its schema,
conflict rule, and adapter tests must be frozen before comparison.

**Track E — extracted structure:** methods receive the same raw reports and
public metadata. A common fixed interpreter proposes claims and dependencies;
methods apply their declared acceptance and maintenance policies. Use the same
fixed actor model and task prompt across methods. A paired extraction stream can
be cached for isolation, but charge its logical compute to every method that uses
it; never report cached shared extraction as free Holon ingestion. Report raw
source availability and actual extracted-edge quality. C0 means complete *public
declarations* here, not guaranteed correct model extraction.

Initially use the existing `qwen3:14b` configuration if available; freeze the
actual model digest, Ollama version, prompt versions, context limits, sampling
parameters, and hardware at run time. A model tag alone is insufficient. Use
three repeated seeds per Track E family/condition/method for the validation
pilot, with matched seed schedules and independent state. Even if a provider
cannot guarantee seeded determinism, retain repeat IDs and record that limit.

Run the structured pilot first. Start extracted development with a small subset
of development families; complete the declared validation set before making a
validation claim. A second fixed model configuration is a later robustness check,
not a prerequisite for the first pilot or a model to tune on test outcomes.

No human fixes an individual method's evaluation state mid-run. Interactive UI
acceptance is outside the benchmark. An automated acceptance policy is explicit,
versioned, and identical where operations are shared. Invalid output is logged;
allow one schema-repair retry per request, charged to the same budget. A second
invalid response yields abstention/error, never hand-edited success.

## 7. Methods and ablations

| ID | Method | Required behavior |
| --- | --- | --- |
| H0 | Current Holon checkpoint | Existing local lifecycle and projection only; no added cross-claim repair; expose status/evidence without treating Beta means as truth probabilities |
| LWW | Last-write-wins facts | Latest arrived value per scoped key, with explicit link-local correction handling; no inferred lineage repair |
| RR | Source-filtered rereading (primary baseline) | Retrieve relevant available source fragments using public project/entity/source/version metadata and lexical matching; reread corrections and original fragments; recompute task answers without a persistent derivation graph |
| RB | Full rebuilding | Reconstruct current usable claims from all available sources in arrival order, respecting explicit supersession and scope; consumes ordinary evidence, never hidden truth |
| SR | Selective repair plus fallback | Affected-justification repair, alternative support, versioned lineage, bounded source rereading on inadequate provenance |
| SR-NF | No fallback ablation | Same SR policy with rereading fallback removed |
| SR-NA | No alternatives ablation | Same SR policy with only the deterministic first justification retained; fixed ordering, not a favorable choice per case |
| SR-OC | Oracle-lineage diagnostic | SR supplied with true lineage; excluded from deployable comparisons and charged separately |

H0 must remain a faithful checkpoint. A compatibility adapter may normalize IDs,
load supplied records, and expose snapshots; it must not perform graph repair,
temporal adjudication, or source-wide correction on H0's behalf. Unsupported
capabilities are recorded, not retrofitted. All methods may consult the same source
archive; choosing not to retain/reread it is a method decision, not denied access.

Before final held-out testing, add hybrid lexical/semantic retrieval over available
sources and a documented history-preserving revision baseline. Label adaptations
as mechanism-class implementations unless the external system itself was run.
Freeze and validate their configurations with the same development budget. If a
required baseline cannot be implemented faithfully, narrow the claim and record
the omission before test; do not call an incomplete comparison comprehensive.

RR's filters must expand to earlier versions and correction references relevant
to the query, not just the latest fragment. RB must actually rebuild on the
declared schedule, not use hidden corrected facts. Freeze retrieval ordering,
tie-breaking, chunking, truncation, and fallback triggers on development data.

## 8. Budgets and cost accounting

Track S is initially bounded by fixture size; count source reads, records visited,
rule evaluations, writes, peak state size, and elapsed CPU/wall time. Record total
work as well as update and query latency. No arbitrary conversion from a database
operation to an LLM token is permitted.

For Track E, use two chosen pilot episode budgets: **32,768** and **131,072**
total input-plus-output model tokens across ingestion, maintenance, retrieval
interpretation, summaries, retries, and six tasks. The larger budget is the
primary comparison; the smaller is a resource-sensitivity check. These are design
limits, not measured runtime/cost estimates. Reserve 25% for answering the six
tasks, divided equally; unused task allocations may roll forward, never backward.
Common prompts count. Enforce the limit before each call using recorded input
length and capped output, and mark exhaustion rather than dropping the episode.

Use the same model context/output caps for all methods. Before first scored runs,
calibrate those caps and request timeouts with neutral transport fixtures that do
not contain evaluation families, then record them in the run manifest. If even
the minimal common task prompt cannot fit, amend this draft's budget before any
scored run and retain the old version. Never adjust a cap selectively for Holon.

Source access is identical and read counts/bytes are measured; inference on
reread content is charged. No method has free background consolidation. Cold
startup/load time and warm inference time are reported separately. Randomize or
counterbalance run order and fix concurrency to avoid confounding model-load or
machine-load effects. Report actual expenditure as well as nominal limits.

Report costs as a vector: model tokens/calls, model execution time, total wall
time, source reads/bytes, storage writes/size. Do not collapse it into one monetary
score without a separately declared pricing model. For cached runs, report both
physical run time and uncached-equivalent logical cost. Calibrate cache savings
on a declared uncached sample before claiming a speed advantage.

UI interaction, evaluator audits, and scoring costs are separate columns. Include
all method-requested checking in method cost. Timeouts, retries, and exhausted
budgets remain in the denominator and consume work already spent.

## 9. Metrics and denominators

Compute rates within family/condition/repeat, then average repeats and conditions
within family. Give each family equal weight. Preserve counts and `not applicable`
when a diagnostic denominator is zero; never turn an absent opportunity into a
perfect score. Each core family must contain answerable post-update affected
tasks and still-supported control claims.

| Metric | Definition |
| --- | --- |
| Obsolete-action rate (primary) | Post-update answerable affected tasks selecting an action tied to an explicitly superseded/invalid premise, divided by all such task opportunities; abstentions are not obsolete actions |
| Justified task success | Correct actions with an available valid justification, plus appropriate abstentions on unresolved tasks, divided by task slots; report answerable and unresolved strata separately |
| Answerable completion | Correct justified non-abstaining actions divided by answerable task slots; errors/timeouts count as failures |
| Valid-knowledge retention | Still-true, still-supported control claims asserted with a surviving valid justification at a read-only audit, divided by the predetermined control-claim set |
| False retraction | Among control claims correctly asserted before intervention and still supported afterward, fraction changed to deny/unresolved; report the pre-update assertion coverage alongside this conditional rate |
| Resurrection | Eligible sequences where an obsolete claim is correctly made unusable after correction but later becomes usable/asserted after a stale echo, divided by such sequences without genuine new support; also report final obsolete assertions over all targeted claims |
| Repair delay | Event/task slots from available correction to the first appropriate revised answer; unrepaired cases are censored and reported, not assigned zero delay |
| Provenance quality | Extracted/maintained copy-edge and premise-edge precision/recall against hidden lineage; separate false merges, missed links, and unknowns |
| Cost | Full-lifecycle totals and per-update/per-task distributions defined above |

Report all wrong actions, unsupported lucky answers, abstentions, errors, and
budget failures separately. Low obsolete-action rate alone is not success.
Retention is a common observable audit, not a comparison of how many rows each
store retains. Archival presence does not imply active use. Resurrection is not
an ordinary world reversal or legitimate independent reconfirmation.

Private scoring checks action preconditions and cited evidence/derivations using
the fixture's valid support sets. Claims with true outcomes but invalid cited
justification are unsupported. For language-extracted equivalence outside a
deterministic normalizer, use a blinded adjudication rule frozen before validation
and report ambiguous cases; do not give the tested interpreter sole grading power.
Do not assess calibration of the current Beta readout as though it were a verified
probability of truth.

## 10. Splits, analysis, and practical decision thresholds

Split the 36 pilot families **24 development / 12 validation**, balanced as four
development and two validation families per motif. Keep every paraphrase,
condition, seed, and derivative of a base support/event topology in the same
split. Validation is not a final test set. After looking at validation outcomes,
revisions require a new protocol version and fresh validation families.

Primary effects are paired SR-minus-RR differences on C1–C3 under the larger
budget in Track E, and separately in Track S. Keep tracks separate. Summarize
95% paired bootstrap intervals with resampling at the family level (10,000
resamples, recorded seed), retaining within-family conditions and repeats.
Report per-motif and per-condition effects descriptively; do not select the
best-looking condition as the primary result. Other baselines and ablations are
secondary comparisons, not extra opportunities to declare primary success.

The following thresholds are **chosen practical targets**, not empirical facts or
claims about statistical power. They apply jointly; all percentages below are
absolute percentage-point differences unless explicitly a cost ratio.

| Decision | Pre-result rule |
| --- | --- |
| Candidate accuracy advantage | SR obsolete-action rate at least 5 points lower than RR; answerable completion and retention each no more than 2 points worse; false retraction no more than 2 points higher; neither total tokens nor uncached-equivalent wall time exceeds RR by more than 25% |
| Candidate efficiency advantage | SR tokens and uncached-equivalent wall time each at least 20% lower than RR; obsolete-action and false-retraction rates each no more than 2 points worse; completion and retention each no more than 2 points worse |
| Favor simpler rereading in this regime | RR meets the same efficiency rule with methods swapped, or SR violates the quality guardrails with no demonstrated compensating advantage |
| Inconclusive/tradeoff | Neither joint rule holds, intervals are too wide, baseline error is too low for the chosen effect, or cost/quality dimensions disagree |

Track S has no token advantage to claim; use its measured runtime and operation
counts diagnostically rather than substituting fabricated token costs. A
structured-only win is a substrate result. A practical language-system claim
requires Track E evidence. Perfect-lineage-only gains are explicitly insufficient.

Pilot point estimates meeting a rule justify continuing, not claiming a finding.
Before final testing, choose sample size from pilot paired variance, a 5-point
obsolete-action effect, 80% target power, and the 2-point quality guardrails;
simulate the joint decision rule at family level. Record the resulting sample
size and maximum resource allowance before generating/opening test outcomes.
Approximately 200 new families is a planning anchor, not an established power
calculation. If the necessary sample is infeasible, narrow the claim or report
uncertainty rather than relaxing margins after seeing results.

For a final positive claim, require the relevant 95% interval bounds to satisfy
the selected joint margins, including cost ratios, not only favorable point
estimates. Efficiency is a prespecified secondary route if primary accuracy
criteria fail in the pilot; label it as such. Select exactly one confirmatory
route before opening a fresh final test set. The other route is descriptive on
that set, avoiding two opportunities to declare a confirmatory win. No optional
stopping on favorable results.

## 11. Stop, invalidate, or revise

- **Invalidate affected comparisons:** hidden truth/future-source leakage,
  unfair source access or human assistance, scorer errors, unmatched model
  settings, or uncharged method work. Repair the harness and rerun all affected
  paired conditions; retain the invalid-run record and reason.
- **Stop mechanism development temporarily:** deterministic repair differs from
  full recomputation on identical supplied inputs, circular support is accepted,
  failed updates leave partial state, or restart changes results without inputs.
  These are engineering defects, not unfavorable research findings.
- **Stop a run safely:** resource cap or transport timeout. Count remaining
  answerable tasks as failures and separately record operational failures. Retry
  infrastructure-corrupted runs only under a method-independent rule frozen in
  the manifest, never selectively to improve a method's score.
- **Prefer a simpler method:** RR dominates under the declared cost/quality
  margins. Report the negative result before adding more architectural machinery.
- **Narrow the conclusion:** gains disappear with missing lineage, extracted
  structure, or legitimate alternative support. Report the boundary explicitly.
- **Revise prospectively:** a floor effect, ambiguous fixture semantics, or too
  few qualifying diagnostic cases makes the study uninformative. Version the
  protocol and use fresh validation/test families; do not quietly remove losses.

Observationally indistinguishable worlds are uncertainty cases, not impossible
reasoning tests. Audit matched visible histories with different hidden truths:
if the exposed evidence cannot justify one action, score justified abstention
and report factual guesses separately.

## 12. Deliverables, freeze checklist, and immediate handoff

Implemented artifacts under this directory are the seeded generator, strict
public/private JSON validators, replay driver/checkpoints, offline deterministic
action/control-audit scorers, command-line tools, generation source/hash manifest,
and the initial Track S method adapters, actor, comparison manifest and cost
instrumentation. Longitudinal metrics, Track E and statistical result-analysis
code remain planned. The
36 candidate configurations and their split designations require semantic/family
review before any pilot is frozen. Record executable commands only once they
have been implemented and verified. Generated databases,
model traces, and run outputs belong in ignored runtime locations; commit
reproducible fixtures/configuration and protocols when authorized.

Before any validation or final run, freeze and retain:

- Protocol version, actual code commit and dirty-diff hash if applicable,
  dependency versions, policy/dynamics versions, and schema versions.
- Family IDs/splits, generator version/seeds, public/archive and private/scorer
  hashes, event schedules, correction targets, and actual corruption counts.
- Method definitions, prompts, model digest/settings, common actor configuration,
  retrieval/chunking limits, fallback triggers, and acceptance policy.
- Budget enforcement, output caps, timeouts, retry rules, caching policy,
  hardware/concurrency, run ordering, repeated-seed schedule, and output location.
- Scoring/normalization/adjudication rules, primary contrast, margins, family
  weighting, bootstrap seed, and final sample size/resource cap when applicable.

Audit source separation, split isolation, budget metering, and scoring against
hand-authored examples. Required scorer cases include all-abstain behavior,
invalid citations, an unaffected alternative justification, correction versus
world change, and an unresolvable visible conflict. Reruns using saved accepted
inputs must reproduce deterministic state and scores; rerunning a model need not
reproduce its proposals byte-for-byte.

**Current handoff (updated 2026-11-06):** steps 1–4 are complete. Initial
structured methods run through the same public-only actor/harness and offline
scorer; their contracts, budgets, actual cost fields, process persistence and
limitations are in [baselines.md](baselines.md). Next is step 5's minimal browser
workspace. Pilot freezing, remaining required comparators and selective repair
are later work. No frozen comparative evaluation has been performed.

Remaining pre-run choices include reviewed family grouping/gold labels, method
configuration freezing, calibrated model caps/timeouts,
and final sample size. The JSON environment schema is now v1. Record the remaining
choices before the relevant evaluation; a runnable simulator does not establish
a completed experimental comparison.

## Change log

| Version | Date | Change | Results available at change |
| --- | --- | --- | --- |
| 0.1 | 2026-11-03 | Initial bounded protocol, paired conditions, comparisons, scoring, budget and decision rules | None; documentation only |
| 0.1 implementation checkpoint | 2026-11-05 | Step 3 environment and schema v1 implemented; handoff advanced to baseline adapters; research margins unchanged | Engineering acceptance only; no comparative outcomes |
| 0.1 implementation checkpoint | 2026-11-06 | Step 4 initial Track S baselines, actor, budgets/costs and subprocess persistence; next step 5; margins unchanged | Development engineering comparisons only |
| Generator v1.1 label amendment | 2026-11-06 | Accept the unchanged room statement in the shared report as alternative audit support; preserve public schedules/IDs | Corrects omitted valid evidence; old v1 bundles retain old labels; regenerate for new runs |
