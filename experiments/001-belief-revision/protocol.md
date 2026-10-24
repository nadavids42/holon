# Experiment 001: Minimal persistent belief revision

Status: engineering acceptance scenario, not a comparative research benchmark.

## Goal
Demonstrate structured observation → evidence → belief revision, with durable
provenance and inspectable history. No model calls are required.

## Scenario
Create the proposition “The lab door is closed” with scope “lab door at instant T0”.
All reports explicitly concern that same instant; recording timestamps describe
when Holon received a report, not when the door was observed.

1. Before reports, inspection returns `insufficient_evidence` and no revisions.
2. Sensor A reports “The lab door is closed”; explicitly link it as `supports`.
   Expected state: `supported`, one observation, one evidence link, one revision.
3. Close the workspace and reopen the same database. The state is unchanged.
4. Sensor B reports “The lab door is open”; link it as `contradicts`.
   Expected state: `contested`, both reports retained, two revisions.
5. Restart again. Inspection retains both sources, reports, evidence links,
   the supported → contested history, and the evidence set used by each revision.
6. An invalid contribution must leave no partial observation, evidence, or revision.

## Policy: presence-v1
Supporting evidence alone means `supported`; contradicting evidence alone means
`opposed`; both mean `contested`. These labels describe evidence presence, not
verified truth or numerical confidence. Repeated reports do not vote away a conflict.
Relations are supplied by the caller; Holon does not interpret report text yet.

## Acceptance
All steps pass automatically using a temporary database. A subprocess CLI check
must verify persistence across actual process exits. Run from the repository root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Deferred
Model interpretation, meta-beliefs, correction/retraction, temporal reasoning,
source reliability, deduplication, numerical confidence, replay tooling,
specialists, scheduling, and baseline comparisons. History inspection is provided;
a general event-replay engine is not implemented at this checkpoint.

Passing establishes an engineering mechanism, not an advantage over a simpler system.

## Optional interpretation acceptance checks

The deterministic scenario above remains runnable without Ollama. Adapter tests
use mocked HTTP responses and CLI tests use mocked model proposals. Verify valid
structured responses, strict malformed-output rejection, failed connections and
timeouts, declined proposals, and unrelated/uncertain abstentions. These paths
must leave epistemic records unchanged. Accepted proposals must preserve verbatim
report text and separate model/reason/prompt-version metadata across restart.
Also verify additive schema setup on an existing prototype database and rollback
when metadata insertion fails. These checks establish integration behavior, not
semantic model accuracy; live matching/conflicting/unrelated/ambiguous reports
remain a manual check using the command in the README.
