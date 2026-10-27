# Epistemic semantic contract

Status: working design contract, 2026-10-27. This document defines the meaning
of the records and operations Holon should preserve as the minimal world model
evolves. It does not claim that the current implementation already supports
every operation described here. The current behavior is summarized separately
below; schemas and exact APIs remain implementation decisions.

## Records and identity

- **Observation:** a record of an input Holon received, such as a report,
  measurement, or document fragment. Its content is what was received, not a
  conclusion that the content is true. An observation has its own identity and
  source provenance. The same observation may be relevant to multiple claims.
- **Proposition:** a specific claim within a specific scope that can be assessed.
  Its ID identifies that claim and scope, not every equivalent way of expressing
  them. A materially refined claim or scope is a new proposition; an explicit,
  reviewable relationship can preserve its connection to the earlier one.
  Similar wording alone does not establish equivalence, and opposite wording
  alone does not establish a contradiction without compatible scope and time.
- **Evidence link:** a judgment that an observation bears on a particular
  proposition in a particular way. It has its own identity and points to both
  records. Support and contradiction are currently supported relations; they
  are judgments about the link, not proof that the source or claim is true.
- **Interpretation:** the process or judgment used to propose or assign a link,
  including its rationale and producer when available. A model proposal and
  its acceptance are distinct from the original report. A manual relation is
  also an interpretation, even if no model-generated rationale exists.
- **Belief readout:** a derived, revisable view of evidence for a proposition
  under a named policy. It is not the observation, the proposition, or a fact
  independently established by the model. Different readouts can coexist.

An ID remains attached to the meaning of its record; it must not be silently
reused for a materially different claim, report, or evidence judgment. Text
similarity is not identity: identical reports can be separate events, and
different reports can share an origin. Source labels and model names are useful
provenance, but do not by themselves prove independence or identify immutable
artifacts.

## Time and scope

**Recording time** is when Holon records an input or event. **Observation time**
is when the reported observation occurred, if known. A report can also refer to
a different **subject time**: the past, present, future, or an interval that the
claim is about. These meanings must not be silently substituted for one another.
Unknown is a valid value and must not be filled in from recording time or
inferred from text without recording that inference and its provenance.

Scope identifies the subject and circumstances under which a proposition is
intended to apply. The current scope is free text, not a machine-verified context
or time interval. Compatible scope and subject time are necessary before opposing
reports can be treated as evidence of the same conflict. A changed state at a
different time is not automatically a contradiction. This contract does not yet
choose an interval representation, timezone precision, or temporal inference
policy.

## Lifecycle and corrections

Accepted observations, propositions, evidence judgments, and revision history
are **logically immutable**: a correction adds a record or event rather than
silently replacing the historical meaning of an existing one. This is a design
invariant, not a claim that every table is currently protected from direct SQL
updates. Future enforcement should preserve a clear distinction between:

1. **Report correction:** the received content or its source attribution was
   recorded incorrectly. Preserve the original and relate a corrected record to
   it, with attribution and reason. Do not present the correction as another
   independent observation without justification.
2. **Evidence reinterpretation:** the observation was recorded correctly, but
   its relationship to a proposition was judged incorrectly. Retain the same
   observation, withdraw or supersede the old link, and create a new link with
   its rationale and provenance.
3. **Proposition refinement:** the claim or scope itself needs a material change.
   Preserve the old proposition and introduce a new one with an explicit
   relationship; do not silently move its evidence or rewrite history.
4. **Withdrawal without replacement:** a link should no longer contribute under
   the active policy. Preserve its identity, attribution, reason, and history.

Corrections must be atomic with the changes they cause to active evidence and
derived qualitative revisions. Links to an unchanged observation are not
independent corroboration merely because multiple propositions use them. A
correction's lineage and a dependency-cluster assignment are related but distinct:
neither should silently imply the other is proven.

## Readouts, conflict, and replay

The existing `active-presence-v2` qualitative status describes the presence of
active supporting and contradicting links. It does not measure their impact:
an active zero-mass link still affects this status. In contrast, the current
binary Beta projection uses stipulated nonnegative mass and per-cluster,
per-sign caps; zero mass contributes no quantitative strength. Therefore the
two readouts can differ without either being a truth verdict. For example, one
zero-mass supporting link produces qualitative `supported`, while the default
Beta readout remains at its prior mean of 0.5 and evidence strength of zero.

The Beta mean and variance are properties of the selected experimental
pseudo-count model, not automatically calibrated probabilities or complete
descriptions of disagreement. Inspect opposing mass and conflict diagnostics
alongside them. Repeated source labels, cluster membership, and weights are
assumptions; they are not proof of independent observations or reliability.

Derived state should be reproducible from the same preserved inputs, policy,
dynamics implementation, and applicable metadata. Replaying an accepted link
is different from rerunning its model interpretation. A current projection is
not automatically a record of what was calculated in the past. Missing or
inferred information must be identified as such rather than invented. Historical
quantitative replay and versioned changes to dependency assignments remain
future work; the exact frontier and retention mechanism are not yet decided.

## Examples and current support

| Scenario | Contract | Current implementation |
| --- | --- | --- |
| A sensor reports on Tuesday that the door was open Monday. | Preserve recording, observation, and subject times separately when known; otherwise mark them unknown. The report alone does not establish when the sensor observed the door. | Recording time and optional caller-supplied observation time are structured; subject time may appear in report or scope text. |
| One report bears on two propositions. | One observation may have two distinct evidence links, each with its own judgment and provenance. | `observe` records one observation; `link` or `interpret-observation` can link it to each proposition. `report` remains a one-step convenience that creates a new observation. |
| A correctly recorded report was classified against a proposition incorrectly. | Preserve the observation; supersede or withdraw the old link and create a new interpretation/link. | `reinterpret` atomically replaces the link while retaining the observation; `correct` instead creates a replacement report and observation. |
| Two reports say a door was open and closed at the same instant. | Preserve both links and the disagreement; do not decide truth by erasing the conflict. | Active opposing links yield `contested`; the Beta projection also exposes conflict diagnostics. |
| A claim is refined from “the door is closed” to “the lab door was closed at T0.” | Preserve the original proposition and explicitly relate a new scoped proposition; do not silently carry over evidence. | New propositions can be created, but proposition refinement and relationship operations are not implemented. |

## Open design questions

- How should exact instants, intervals, precision, uncertainty, and future or
  retrospective subject times be encoded without overstating what is known?
- What minimal provenance identifies a source event and an accepted
  interpretation, including manual attribution, without inventing missing data?
- Which proposition relationships and review rules are needed before semantic
  equivalence or contradiction links can be acted upon?
- How should revised dependency assignments be versioned, and what inputs must
  a historical quantitative readout retain to be reproducible?
- Which logical immutability rules belong in the service versus database
  constraints, and how should legacy records with missing context be labeled?
