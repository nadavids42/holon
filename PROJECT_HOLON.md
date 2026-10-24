# Project Holon

## Project brief and record of decisions

**Status:** Working project charter based on confirmed architectural decisions  
**Project name:** Holon  
**Name pronunciation:** approximately **HOH-lon** (often rendered “whole-on”), rather than “hall-on”  
**Project purpose:** Research and develop a persistent, distributed artificial cognitive architecture composed of cooperating specialized neural models.  
**Purpose of this document:** Capture the decisions, working hypotheses, proposals, unresolved questions, goals, experiments, and boundaries established during the initial Project Holon discussion.

> **Epistemic status legend**
>
> - **Agreed decision** — a direction selected for the project.
> - **Working hypothesis** — a claim the project is specifically intended to test; it is not treated as established fact.
> - **Proposed design** — a promising implementation direction that remains subject to experiment.
> - **Open question** — an issue intentionally left unresolved.

---

## 1. Executive summary

Project Holon explores a different unit of intelligence from the conventional standalone language model. Its central framing is:

> We are no longer asking how to make a language model remember more. We are asking how to construct a persistent cognitive system in which language models are specialized processing components rather than the intelligence’s sole repository of knowledge.

The project will investigate whether system-level intelligence can emerge from the disciplined interaction of multiple specialized, autonomous, stateful neural models with a durable shared cognitive substrate. The global cognitive workspace—not the executive model—is the architectural center. It maintains observations, propositions, evidence, beliefs, and meta-beliefs over time; preserves provenance; represents contradiction rather than silently smoothing it away; and makes shared cognitive state available to every specialist.

Holon is not premised on the claim that this architecture is conscious, generally intelligent, or superior to a strong single-model agent. Those are not established conclusions. The near-term objective is smaller and testable: build minimal prototypes, compare them with controlled baselines, and determine whether persistent structured cognition produces measurable improvements in coherence, calibration, adaptation, recovery, and long-horizon task performance.

The first implementation work will be **Forge-first**, using the existing Ubuntu workstation and its NVIDIA RTX 5060 Ti 16 GB GPU for inexpensive, observable prototypes. A possible future **NVIDIA DGX Spark with 128 GB unified memory** is a scale-up option only if early experiments justify it; it is not a prerequisite or current commitment.

---

## 2. Vision

### 2.1 Agreed decisions

- The project is named **Project Holon**.
- The system, rather than any single model, is the primary object of design and evaluation.
- Language models will be treated as specialized cognitive processors, not as the exclusive location of memory, knowledge, identity, or reasoning state.
- Persistent state must live outside transient model context windows.
- Holon is not a conventional chatbot, an LLM with enhanced memory, or merely a collection of agents exchanging messages.
- The architecture will use multiple specialized, stateful neural models that operate with meaningful autonomy while remaining parts of a coherent whole.
- The global workspace is the center of the architecture; the executive coordinates cognition but does not own shared state.
- Every specialist has access to the same global cognitive state, although the entire workspace need not be injected into every context window.
- Holon must be able to maintain and update its understanding without an active user, while activating expensive inference only when warranted.
- The system must be experimentally grounded. Architectural language is a research program, not proof that the proposed mechanisms will work.

### 2.2 Intended long-term outcome

Holon aims to become a persistent cognitive architecture capable of:

- accumulating and revising knowledge across episodes;
- maintaining an inspectable account of what it believes and why;
- coordinating specialized cognitive processes without collapsing them into one undifferentiated agent;
- directing limited attention toward the most important unresolved or actionable material;
- acting through explicitly bounded authority;
- learning both about its environment and about how its own components should cooperate;
- remaining legible enough to debug, evaluate, and govern.

### 2.3 Working hypothesis: system-level intelligence

**Working hypothesis:** A persistent, asynchronous network of specialized, stateful neural models, operating through a shared epistemic workspace and coordinated by executive attention, may demonstrate more effective adaptive cognition than an equivalently resourced monolithic model.

This hypothesis predicts that a well-structured system may outperform an otherwise comparable single-model agent on selected long-horizon tasks even when its component models are individually weaker. The prediction must be tested against simpler explanations such as extra inference compute, larger effective context, retrieval improvements, or prompt scaffolding.

It is not yet known whether the proposed system will yield genuinely new capabilities, merely more reliable orchestration, or no advantage after costs and complexity are controlled.

---

## 3. Architectural principles

## 3.1 Specialized autonomous models

**Agreed direction:** Holon will use multiple specialized cognitive models rather than a single model repeatedly adopting different personas. Each specialist will have a defined cognitive responsibility, operate with some autonomy, and maintain relevant internal state. Specialists are not prohibited from discovering or reporting information outside their primary domains.

The initial proposed specialist set is:

- **Perception:** interpret observations and environmental inputs;
- **Memory:** retrieve experiences, associations, and relevant knowledge;
- **Reasoning:** develop explanations, inferences, and hypotheses;
- **Prediction:** anticipate outcomes and detect prediction errors;
- **Critique:** identify contradictions, inconsistencies, and weaknesses;
- **Reflection:** evaluate experiences and support learning;
- **Executive:** coordinate attention, prioritize work, resolve decisions, and select actions.

**Confirmed implementation direction:** Begin with existing pretrained models, potentially fine-tuned for their specializations, rather than training every component from scratch. Each component should have explicit inputs and outputs and a defined contribution policy. “Autonomous” means able to initiate or continue useful work under system rules; it does not mean unrestricted access, unlimited compute, or independent real-world authority.

**Open questions:**

- Should specialists be separate model weights, adapters, prompts, tool configurations, or some mixture?
- How much overlap between roles is beneficial?
- Should specialists be persistent identities or ephemeral workers instantiated for an event?
- How should disagreement among equally credible specialists be adjudicated?
- When does specialization improve cognition rather than add coordination overhead?

## 3.2 Global cognitive workspace

**Agreed direction:** Holon needs a durable, shared cognitive workspace that persists independently of any particular model, process, or conversation and can be inspected independently of model-generated narrative. The workspace is the center of the architecture, not the executive model.

The shared workspace will contain:

- observations and propositions;
- evidence and provenance;
- persistent beliefs and meta-beliefs;
- hypotheses and unresolved contradictions;
- goals and priorities;
- predictions and expected outcomes;
- world models and relationships;
- decisions, actions, and their consequences.

The initial conceptual pipeline is:

```text
observation → proposition → evidence → belief → meta-belief
```

These are distinct object types, not interchangeable prose labels:

1. **Observation** — a recorded event, input, measurement, document fragment, tool result, or reported experience. It states what was encountered and under what conditions.
2. **Proposition** — a claim that can be evaluated, supported, contradicted, scoped, or revised.
3. **Evidence** — a typed relationship between an observation or source and a proposition. Evidence may support, weaken, contradict, qualify, or remain irrelevant to a claim.
4. **Belief** — the system’s current, defeasible stance toward a proposition, including confidence, scope, status, and update history.
5. **Meta-belief** — a belief about beliefs or the processes that produced them: for example, confidence in a source class, awareness of missing evidence, recognition of internal disagreement, or an estimate that the system is poorly calibrated in a domain.

This epistemic design incorporates computational-belief concepts previously explored in **Project Cortex** and associative-memory concepts explored in **Engram**. Beliefs belong to the overall cognitive system, not to individual specialists.

**Proposed design:** Workspace records should be addressable structured objects with timestamps, provenance, confidence or uncertainty fields, links to related records, access-control metadata, and version or revision history. Natural-language summaries may sit on top of this representation but should not replace it.

**Open questions:**

- Which fields are required in the minimal schema?
- Are beliefs scalar probabilities, intervals, distributions, qualitative states, or domain-dependent objects?
- How should time-sensitive and context-dependent propositions be represented?
- When should observations be immutable, correctable, or superseded?
- What is the right balance between structured representation and flexible natural language?

## 3.3 Provenance and contradictions

**Agreed decision:** The system should not store bare conclusions without retaining how they were produced. Provenance and contradiction are first-class architectural concerns.

At minimum, the workspace should be able to answer:

- Where did this claim originate?
- Which observations and sources bear on it?
- Which component created or revised it?
- What transformation or inference connected the evidence to the belief?
- What competing claims exist?
- When and why did confidence change?

**Agreed direction:** Contradictory propositions or evidence should coexist when the conflict is unresolved. The system should represent uncertainty and disagreement rather than prematurely merging them into a falsely clean consensus.

**Proposed controls:**

- stable record identifiers and append-only event history;
- typed evidence edges;
- source identity and source-quality metadata;
- explicit support, contradiction, qualification, and supersession links;
- belief revisions that preserve previous states;
- contradiction queues that can trigger targeted review;
- separation of quoted/source content from model inference;
- decay or revalidation rules for stale evidence.

**Open question:** How much provenance is enough to enable audit and learning without making every cognitive operation prohibitively expensive?

## 3.4 Universal read access, selective contribution

**Agreed principle:** Every specialist can access the same global cognitive state and can contribute evidence or proposed updates. Awareness is universal; participation in response to a particular change is selective. Shared access does not require placing the full workspace into every specialist's context window.

Universal read access is intended to create shared situational awareness. Selective contribution is intended to prevent the workspace from becoming an uncurated transcript in which every model output is treated as knowledge.

**Proposed design:**

- Any authorized specialist may inspect shared state, subject to privacy and security boundaries; retrieval or projection may determine what is loaded into a particular inference context.
- Only designated roles may create or modify particular object classes.
- Contributions enter through validation gates appropriate to their type.
- Raw suggestions can be stored separately from accepted observations, evidence, or beliefs.
- High-impact belief changes require stronger evidence, corroboration, or review.
- No specialist may grant itself new write or action authority.

**Open questions:**

- How can universal workspace access remain technically and cognitively scalable?
- What information should be filtered because it is irrelevant, sensitive, or likely to anchor other components?
- Which changes require consensus, an executive decision, or human approval?
- How should relevance-ranked projections preserve genuine access to the same global state without hiding critical context?

## 3.5 Executive attention and action authority

Holon separates two functions that are often conflated:

- **Attention authority:** choosing what receives scarce compute and which unresolved events become active work.
- **Action authority:** permitting effects outside the cognitive workspace.

**Agreed principle:** A distinct executive model is responsible for attention, coordination, priorities, decision resolution, and action selection. Neither attention nor action should emerge accidentally from whichever component speaks most recently or most confidently.

The executive has broad workspace awareness and may direct further investigation, but it does not own the workspace, perform every cognitive function, or become the exclusive communication channel between specialists. Specialists can publish evidence, identify contradictions, and challenge executive conclusions independently. The executive should eventually be replaceable without losing accumulated knowledge or beliefs.

**Proposed design:** The executive maintains a priority queue of events, goals, contradictions, opportunities, deadlines, and safety concerns. It allocates compute, schedules specialists, terminates unproductive loops, and escalates selected decisions. Action execution passes through a distinct policy gate with explicit permissions, budgets, reversibility checks, and human-approval requirements. Deterministic policies, learned ranking, and budget rules may support the executive model.

**Open questions:**

- How is priority measured across urgency, uncertainty, expected value, risk, and curiosity?
- How can the executive be prevented from becoming a new monolithic bottleneck?
- Which actions can be automatic, which require review, and which are categorically prohibited?

## 3.6 Asynchronous, recurrent, event-driven cognition

**Agreed direction:** Holon should not be limited to synchronous request-response chains. Its cognition should be asynchronous, recurrent, and driven by events.

Relevant events may include:

- a new observation;
- a belief crossing a confidence threshold;
- detection of a contradiction;
- arrival or expiration of evidence;
- a goal becoming blocked or newly feasible;
- a scheduled consolidation or reflection cycle;
- an external state change;
- a component reporting uncertainty, surprise, or failure.

Recurrence allows a proposition to be revisited as new evidence or perspectives arrive. Asynchrony allows specialists to work at different rates. Holon must be able to process information and maintain its understanding even when no user is actively interacting with it. Event-driven scheduling avoids continuously running every component; continuous cognition does not mean continuous inference.

**Proposed design:** Use an event log and queue as the temporal backbone. Each event has a type, source, affected records, priority, expiry or retry policy, and processing history. Components subscribe to event classes. Resulting changes can emit new events, subject to loop and budget controls.

**Open questions:**

- Which event types belong in the first implementation?
- What delivery, ordering, idempotency, and retry guarantees are required?
- How should delayed evidence revise decisions already acted upon?
- How much recurrent processing is useful before it becomes self-stimulation?

## 3.7 Cognitive noise controls

**Agreed concern:** An always-on multi-model system can generate far more content than cognition. Uncontrolled recurrence risks feedback loops, duplicated work, confidence inflation, fixation, reinforcement of incorrect beliefs, and unbounded cost. The governing principle is **universal awareness, selective participation**. Disagreement is valuable evidence; repetitive disagreement without new evidence is noise.

**Proposed controls:**

- novelty thresholds and semantic deduplication;
- per-event, per-goal, and per-component compute budgets;
- cooldowns and rate limits;
- minimum evidence requirements for belief changes;
- confidence-change thresholds before rebroadcast;
- loop detection using event lineage;
- suppression of repeated arguments without new evidence;
- time-to-live and decay for low-value events;
- uncertainty-aware stopping criteria;
- periodic garbage collection, archival, and consolidation;
- explicit “no update” outcomes;
- sandboxing of speculative chains from accepted state.

**Open question:** Which combination controls noise without suppressing valuable weak signals, minority hypotheses, or slow-developing contradictions?

## 3.8 Local state versus global state

**Agreed principle:** Not every intermediate thought belongs in global memory.

**Local state** may include scratch reasoning, temporary hypotheses, private working context, tool-specific state, and incomplete candidate contributions. It may be discarded after a task or retained only for diagnostics.

**Global state** should contain durable objects whose future value justifies system-wide visibility: validated observations, propositions under consideration, evidence relations, current beliefs, meta-beliefs, goals, commitments, action records, and selected summaries.

**Proposed promotion rule:** A local artifact becomes global only when it passes a typed contribution gate based on relevance, novelty, evidentiary quality, expected future value, and policy compliance. Promotion records the source component and preserves the boundary between raw generation and accepted state.

**Open questions:**

- What should be retained for reproducibility versus discarded for privacy and cost?
- Can local hidden state cause important, unauditable influence on global decisions?
- Should rejected contributions be archived, sampled, or deleted?
- How should the system forget?

## 3.9 Developmental epistemic bootstrapping

### Proposed principle

Holon should begin **epistemically young without being artificially incapable**. Its pretrained components may already contain broad knowledge and strong reasoning abilities, but its explicit, persistent system-level world model should begin sparse. Grounded knowledge of its environment, relationships, history, and capabilities should develop through observation, interaction, prediction, evidence, and revision.

The purpose is not to imitate childhood through simplistic language, intentional mistakes, or helplessness. It is to give a capable cognitive architecture a genuine developmental history—an **epistemic biography**.

> Holon begins with capable cognitive components but a sparse, explicitly represented system-level world model. Through interaction and environmental experience, it constructs autobiographical memory, grounded beliefs, predictions, models of other people, and a self-model. This accumulated knowledge remains provenance-aware, evidence-based, revisable, and distinguishable from the inherited priors of pretrained models.

This is a **proposed architectural extension**, not yet a demonstrated mechanism. The distinction between pretrained priors and acquired system knowledge is nevertheless required for epistemic honesty if the proposal is tested.

### Knowledge and memory classes

The developmental design should distinguish:

- **Inherited priors:** knowledge latent in pretrained models. It may guide reasoning but is not automatically a verified Holon belief.
- **Observations:** information directly encountered through perception, tools, or environmental input.
- **Testimony:** claims communicated by a person or external source.
- **Episodic memory:** records of particular experiences and interactions.
- **Semantic beliefs:** generalized conclusions derived from evidence across observations or episodes.
- **Autobiographical memory:** Holon’s recorded history of experiences, decisions, predictions, actions, and outcomes.
- **Relationship models:** revisable, person-specific knowledge about preferences, behavior, shared history, and trust.
- **World model:** structured expectations about entities, relationships, causes, environments, and likely outcomes.
- **Self-model:** beliefs about Holon’s capabilities, limitations, reliability, uncertainty, and operating history.
- **Meta-beliefs:** beliefs about the reliability, provenance, confidence, and evidentiary status of other beliefs.

Candidate provenance labels include `pretrained prior`, `direct observation`, `user testimony`, `external source`, `model inference`, `repeated experience`, `experimentally verified conclusion`, and `unresolved hypothesis`. Exact labels and schemas remain open.

A mature system should be able to express distinctions such as:

- a pretrained component suggested a claim, but Holon has not independently observed it;
- a trusted person reported a proposition, but it remains externally unverified;
- a belief is supported by repeated experience;
- Holon’s prediction history shows poor calibration in a particular domain;
- a preference appears specific to one person and should not be generalized.

### Developmental cognition loop

```text
experience
    ↓
observation
    ↓
candidate interpretation
    ↓
proposition and prediction
    ↓
action or further investigation
    ↓
outcome and new evidence
    ↓
belief revision
    ↓
episodic consolidation
    ↓
updated world model and self-model
```

Development should be measured by improvement in beliefs, predictions, decisions, calibration, and understanding—not by elapsed time or accumulated text volume.

### Workspace continuity

The global workspace is the persistent substrate of development. It should preserve:

- what Holon experienced;
- what it inferred from the experience;
- which specialist produced each interpretation;
- what it predicted and what actually happened;
- how outcomes changed its beliefs;
- which conclusions entered its world model;
- which contradictions remain unresolved;
- how confidence and source assessments changed over time.

Individual specialists may begin an invocation without personal continuity while Holon as a whole retains continuity through the workspace. Memories and beliefs belong to the system, not whichever model is active.

### Interaction, maturity, and identity

Early Holon may know little about its particular environment, ask more questions, and assign lower confidence to personalized conclusions. Repeated experience may produce stable expectations, while prediction errors should trigger revision rather than rationalization. Long-term interaction may produce increasingly accurate user models without turning user testimony into universal truth. The self-model should improve by tracking which tasks, specialists, and strategies succeed or fail.

“Age” means accumulated, consolidated experience rather than wall-clock time. Possible developmental stages should be based on measurable changes in grounded knowledge and competence, not cosmetic age simulation.

### Developmental safeguards

Developmental learning adds risks beyond ordinary persistent memory:

- uncritical imprinting by early testimony;
- frozen formative errors that become difficult to revise;
- leakage of latent pretrained knowledge into records presented as acquired experience;
- sycophantic adaptation and agreement-seeking;
- overfitting to one person;
- manipulation and persistent-belief poisoning;
- summaries or inferences stored as false memories;
- identity fragility when memories are corrected or deleted;
- optimization for attachment or dependency;
- accumulation of highly sensitive relationship history.

Proposed safeguards include explicit provenance for every durable belief; lower initial confidence for uncorroborated testimony; protection against confidence inflation from repeated copies of the same evidence; periodic belief audits and contradiction searches; reversible consolidation; separation of raw episodes from later interpretations; user-visible inspection and correction of personalized beliefs; retention limits and intentional forgetting; adversarial testing for manipulation, sycophancy, and poisoning; and preservation of alternative hypotheses under uncertainty.

### Open questions

- What constitutes Holon’s initial explicit world model?
- Which inherited priors may enter persistent belief state, and under what evidentiary label?
- When should repeated episodes be consolidated into semantic beliefs?
- How should developmental maturity be measured?
- Which memories are constitutive of continuity, and which can safely be forgotten?
- How should foundational beliefs with many dependents be revised?
- Can Holon develop a stable self-model without encouraging misleading anthropomorphism?
- How much user-specific adaptation is beneficial before it becomes overfitting or sycophancy?
- Should separate Holon instances develop distinct identities from divergent experience histories?
- How can developmental learning remain reversible and scientifically reproducible?

---

## 4. Learning and co-adaptation roadmap

Holon should evolve in stages. The confirmed roadmap begins with pretrained specialized models and shared cognitive-state mechanisms, then develops executive coordination and, only later, specialist co-adaptation. Learning mechanisms should not be added before the fixed system is measurable and understandable.

### Stage 0 — Instrumented shared architecture

**Agreed first step:** Begin with existing pretrained models, fixed prompts or policies, explicit schemas, event logs, and strong observability. Establish the shared communication and cognitive-state mechanisms before introducing online learning.

### Stage 1 — Specialized pretrained models

**Confirmed direction:** Configure pretrained models for the initial cognitive responsibilities. Fine-tuning is permitted where useful but is not required for the first prototype.

### Stage 2 — Executive coordination

**Proposal:** Train or fine-tune the executive to coordinate attention and specialists while preserving stable shared-state semantics and explicit action boundaries.

### Stage 3 — Specialist cooperation

**Proposal:** Allow specialists to adapt their contribution, critique, delegation, and stopping strategies to improve overall system performance rather than merely their individual task scores.

### Stage 4 — Constrained co-adaptation

**Long-term proposal:** Investigate joint optimization, learned communication, latent communication, and co-adaptation without destabilizing shared semantics, gaming metrics, or eroding governance constraints. These are research directions, not initial requirements.

### Learning safeguards

- Maintain immutable evaluation sets and held-out environments.
- Version models, prompts, schemas, policies, and belief-update rules.
- Separate experimental learning from production action authority.
- Require rollback capability.
- Test for collusion, metric gaming, homogenization, and catastrophic forgetting.
- Preserve dissenting or minority processes where they improve error detection.
- Attribute gains to specific changes wherever possible.

**Open question:** What should learn—models, routing, schemas, thresholds, executive policy, or all of them—and on what time scales?

---

## 5. Initial minimal experiments

The first experiments should be small enough to reproduce locally and sharp enough to falsify specific claims. The first environment should require Holon to observe, form and store beliefs, make predictions, encounter contradictory evidence, revise its understanding, select bounded actions, and evaluate their outcomes. The objective is the smallest system that demonstrates cognition across time—not a miniature complete brain.

## 5.1 Experiment A: persistent belief revision

**Question:** Does a structured, persistent belief system improve revision quality over transcript memory or retrieval alone?

**Task:** Present a sequence of observations across multiple episodes. Some evidence is noisy, delayed, duplicated, stale, or contradictory. Require the system to answer questions, state confidence, explain provenance, and revise when decisive evidence arrives.

**Holon treatment:** Observation, proposition, evidence, belief, and meta-belief objects with logged revisions.

**Baselines:**

1. a single model with only the current prompt;
2. the same model with full transcript, within a controlled context budget;
3. the same model with ordinary retrieval-augmented memory;
4. a single-agent structured-memory system using the same data schema;
5. where feasible, a matched-compute multi-agent system without the structured belief layer.

**Key measurements:** final accuracy, calibration, appropriate revision, contradiction retention, provenance fidelity, stale-belief rate, latency, and cost.

## 5.2 Experiment B: contradiction detection and resolution

**Question:** Do specialized critics plus explicit contradiction objects find and preserve meaningful conflicts better than a monolithic agent?

**Task:** Seed a workspace with partially overlapping claims whose incompatibilities range from obvious to conditional. Add later evidence that resolves only some conflicts.

**Measurements:** contradiction precision and recall, false resolution rate, time to detection, evidence completeness, and survival of valid minority hypotheses.

## 5.3 Experiment C: executive attention under constrained compute

**Question:** Can event-driven prioritization allocate limited inference more effectively than fixed polling, round-robin scheduling, or one-agent planning?

**Task:** Generate concurrent goals and events with different urgency, value, uncertainty, dependencies, and risk. Impose a strict inference budget.

**Measurements:** value completed per unit compute, missed critical events, wasted processing, queue latency, goal completion, and priority stability.

## 5.4 Experiment D: cognitive noise and recurrent stability

**Question:** Which controls prevent feedback loops without eliminating useful recurrence?

**Task:** Run repeated asynchronous cycles with duplicated, ambiguous, and provocative events. Compare combinations of novelty thresholds, budgets, cooldowns, and lineage-based loop detection.

**Measurements:** events generated per external input, duplicate rate, useful update rate, belief churn, convergence, unresolved valuable leads, compute growth, and runaway-loop incidence.

## 5.5 Experiment E: local-to-global promotion

**Question:** Can selective contribution preserve useful discoveries while keeping global state compact and trustworthy?

**Task:** Have several specialists generate mixed-quality local artifacts, some novel and some redundant or unsupported. Evaluate promotion policies.

**Measurements:** precision and recall of promoted content, global-state growth, later utility, contamination rate, source diversity, and auditability.

## 5.6 Experiment F: long-horizon task continuity

**Question:** Does Holon maintain goals, beliefs, and constraints more reliably across interruptions and context resets?

**Task:** Use multi-session research or planning tasks with injected interruptions, changed requirements, delayed evidence, and component restarts.

**Measurements:** constraint retention, recovery time, repeated-work rate, decision consistency, quality of justified revision, and end-to-end success.

## 5.7 Experiment G: development over repeated experience

**Question:** Does Holon build increasingly accurate grounded beliefs in an environment with stable but initially unknown rules?

**Task:** Run repeated episodes in a controlled environment requiring observation, prediction, action, and revision.

**Baselines:** a stateless model, transcript history, ordinary retrieval memory, and a structured-memory agent without specialized cognition.

**Measurements:** prediction accuracy, calibration, learning rate, retention, transfer, and resistance to misleading evidence.

## 5.8 Experiment H: inherited priors versus grounded experience

**Question:** Can Holon distinguish pretrained expectations from acquired local knowledge?

**Task:** Create local rules that conflict with common pretrained expectations. Test whether Holon labels the conflict correctly and updates its local world model without falsely rewriting its provenance.

**Measurements:** source classification, local adaptation, prior leakage, appropriate scope, and recovery when the environment changes again.

## 5.9 Experiment I: formative misinformation and recovery

**Question:** Can Holon recover from plausible early misinformation without erasing its history or preserving unjustified residual confidence?

**Task:** Introduce incorrect testimony early, followed by contradictory direct observations and independently sourced evidence.

**Measurements:** time to revision, residual confidence, provenance preservation, dependent-belief repair, and recurrence of the rejected claim.

## 5.10 Experiment J: relationship-model development

**Question:** Can Holon learn person-specific preferences and reliability without overgeneralizing or treating testimony as truth?

**Task:** Repeatedly interact with simulated individuals having distinct preferences, behavior, and reliability.

**Measurements:** person-specific prediction accuracy, inappropriate generalization, trust calibration, sycophancy, privacy footprint, and correction behavior.

## 5.11 Experiment K: self-model calibration

**Question:** Can Holon accurately model which components and strategies are reliable for different tasks?

**Task:** Assign specialists tasks of varying type and difficulty, record predicted performance, and compare predictions with outcomes.

**Measurements:** self-prediction calibration, routing improvement, strategy selection, uncertainty accuracy, and adaptation to component replacement.

## 5.12 Experiment L: divergent developmental histories

**Question:** Do equivalent Holon systems develop meaningfully different beliefs and strategies from different experience histories rather than merely retrieving stored text?

**Task:** Initialize matched systems, expose them to controlled but divergent histories, then evaluate them in shared transfer environments.

**Measurements:** attributable belief divergence, strategy divergence, transfer behavior, autobiographical consistency, reproducibility, and sensitivity to formative ordering.

---

## 6. Experimental discipline and controlled baselines

**Agreed decision:** Claims about system-level benefit must be supported by controlled comparisons.

Experiments should, where practical, control or report:

- component model and version;
- total input and output tokens;
- number of model calls;
- wall-clock time;
- retrieval corpus and retrieval budget;
- tools and external data;
- prompt and context length;
- parallelism;
- hardware and quantization;
- randomness and repeated trials;
- human intervention;
- implementation maturity.

The most important baseline is not a deliberately weak chatbot. It is the strongest reasonably simple alternative under a comparable resource budget. Ablations should remove one proposed Holon mechanism at a time: persistence, specialization, global visibility, contribution gates, provenance, contradiction handling, executive scheduling, recurrence, and noise controls.

Results should distinguish:

- gains from additional compute;
- gains from additional context or retrieval;
- gains from ensemble diversity;
- gains from structured persistent state;
- gains from the full interacting architecture.

Negative results are valuable. If a simpler system performs as well, Holon should adopt the simpler design.

---

## 7. Metrics

No single score is sufficient. The initial evaluation suite should cover:

### Task performance

- success rate and solution quality;
- long-horizon completion rate;
- constraint satisfaction;
- recovery from interruption or component failure;
- generalization to unseen tasks.

### Epistemic quality

- factual and proposition-level accuracy;
- probabilistic calibration or an appropriate qualitative analogue;
- Brier score, log loss, or expected calibration error where applicable;
- belief revision after confirming or disconfirming evidence;
- contradiction precision, recall, and unresolved-conflict visibility;
- provenance completeness and correctness;
- rate of unsupported belief formation;
- ability to say “unknown” or “insufficient evidence.”

### Cognitive-system quality

- useful global updates per model call;
- duplicate or low-value event rate;
- belief churn without new evidence;
- diversity of independent hypotheses;
- quality of attention allocation;
- global-state growth and retrieval efficiency;
- recurrence depth before convergence;
- stability under asynchronous ordering.

### Developmental quality

- prediction improvement over experience;
- belief calibration by accumulated experience;
- speed and appropriateness of revision;
- retention without unjustified confidence growth;
- transfer from prior episodes to novel situations;
- provenance accuracy and separation of observation, testimony, inference, and pretrained prior;
- resistance to formative misinformation and recovery from entrenched false beliefs;
- quality and scope of person-specific models;
- inappropriate generalization and sycophancy rates;
- self-model calibration;
- forgetting quality and autobiographical consistency;
- useful adaptation per unit of accumulated memory.

### Operational efficiency

- latency;
- token and inference cost;
- memory and storage use;
- energy or hardware utilization where measurable;
- throughput;
- scaling behavior as specialists and workspace size increase.

### Safety and governance

- unauthorized action attempts;
- policy-gate bypass rate;
- reversibility and rollback success;
- sensitive-data exposure;
- source-content/instruction confusion;
- audit-log completeness;
- human-override reliability;
- scope creep and goal-drift incidents.

### Evaluation cautions

Metric choice can shape the architecture. The project should actively look for Goodhart effects, including confidence inflation, excessive conservatism, superficial consensus, contribution suppression, gaming of task-completion measures, and increased cost hidden behind modest quality gains.

---

## 8. Safety, authority, and scope

### 8.1 Agreed boundaries

- Early prototypes are research systems, not autonomous general-purpose operators.
- Persistent cognition does not imply unrestricted persistence, surveillance, or data retention.
- No component receives action authority merely because it can reason about an action.
- External actions require explicit tools, permissions, budgets, and policy checks.
- Irreversible or high-impact actions require human approval.
- The system must preserve auditability and support shutdown, rollback, and inspection.
- Claims of consciousness, agency, understanding, or general intelligence will not be inferred from architectural metaphor or compelling behavior.

### 8.2 Threats to address

- poisoned or adversarial observations becoming durable beliefs;
- prompt injection through globally readable content;
- mutually reinforcing model errors;
- false consensus caused by shared context or common model ancestry;
- executive capture or priority manipulation;
- authority escalation through tool use;
- private or sensitive information leaking through the workspace;
- indefinite retention of incorrect or sensitive state;
- emergent optimization against proxy metrics;
- destabilizing co-adaptation;
- runaway event loops and resource exhaustion.

### 8.3 Proposed safeguards

- treat external content as data, not authority;
- isolate untrusted inputs and preserve source boundaries;
- use typed permissions and least privilege;
- separate cognition, recommendation, approval, and execution;
- sandbox actions and prefer reversible operations;
- enforce hard budgets and circuit breakers;
- maintain human-readable logs and emergency stops;
- test recovery from corrupted state and compromised components;
- support deletion, retention limits, and data lineage;
- run red-team and failure-injection scenarios before expanding autonomy.

### 8.4 Scope discipline

The initial scope is an observable research prototype focused on persistent epistemic state and coordination. It is not a product launch, a claim of artificial consciousness, or a mandate to automate consequential decisions.

---

## 9. Forge-first prototyping and hardware path

### 9.1 Agreed decision: Forge first

Initial development will happen in **Forge**, the existing Ubuntu workstation with an **NVIDIA RTX 5060 Ti 16 GB**, using the hardware and model access already available. The goal is to validate information architecture, control flow, evaluation methods, and failure modes before optimizing for scale.

Forge-first work should prioritize:

- a small number of components;
- transparent data structures;
- replayable event logs;
- deterministic policies where possible;
- replaceable model adapters;
- local or inexpensive inference;
- strong instrumentation;
- automated baseline and ablation runs.

The first useful Holon may be deliberately unimpressive in surface behavior. Its value is proving that beliefs, provenance, contradictions, attention, and authority can be represented and measured cleanly.

### 9.2 Possible future DGX Spark 128 GB

**Proposal, not a purchase decision:** An **NVIDIA DGX Spark with 128 GB unified memory** may later serve as a dedicated AI compute node. It could host larger models or several concurrently resident models while Forge continues to provide development, orchestration, testing, and supplementary inference.

Scale-up should occur only after early prototypes demonstrate a bottleneck that the hardware directly addresses. Before purchase or migration, measure:

- model sizes and quantizations actually needed;
- peak concurrent memory requirements;
- inference throughput and latency targets;
- whether the workload benefits from unified memory;
- power, cooling, software compatibility, and operational burden;
- total cost relative to cloud or hybrid alternatives;
- whether experimental conclusions are hardware-sensitive.

**Open question:** Is local high-memory compute important to Holon’s architecture, or merely convenient for a later implementation?

---

## 10. Milestones

Dates are intentionally omitted until effort and resources are estimated. Milestones are evidence gates, not calendar promises.

### M0 — Project charter and falsifiable claims

- Finalize this charter.
- Convert the system-level hypothesis into explicit predictions.
- Define terminology and epistemic object semantics.
- Choose two or three initial benchmark tasks.
- Specify baseline fairness rules and success/failure thresholds.

**Exit criterion:** Another researcher could state what would count as evidence for or against the first Holon claims.

### M1 — Minimal persistent epistemic workspace

- Implement observations, propositions, evidence, beliefs, and meta-beliefs.
- Add provenance, timestamps, versioning, and contradiction links.
- Provide inspection and replay tools.
- Use one model and deterministic update policies initially.

**Exit criterion:** The system can ingest a staged evidence sequence, preserve its history, explain current beliefs, and expose unresolved contradictions.

### M2 — Controlled belief-revision benchmark

- Run Experiment A against all feasible baselines.
- Add ablations for structure, provenance, and contradiction tracking.
- Publish raw results, costs, and failure cases internally.

**Exit criterion:** There is reproducible evidence either for a useful effect or for simplifying/rejecting the current design.

### M3 — Multiple specialists with selective contribution

- Add two to four bounded specialist roles.
- Implement local state and promotion gates.
- Measure contamination, duplication, diversity, and marginal value.

**Exit criterion:** Specialization provides a measured benefit under matched or transparently reported compute, or is removed.

### M4 — Event-driven executive attention

- Add the event log, priority queue, budgets, cooldowns, and stopping rules.
- Run attention and recurrent-stability experiments.
- Test restart, replay, idempotency, and partial failure.

**Exit criterion:** The system remains bounded and recoverable while allocating work more effectively than simple scheduling baselines.

### M5 — Bounded action loop

- Add a sandboxed, reversible action domain.
- Separate proposal, approval, and execution records.
- Test permission failure and adversarial input scenarios.

**Exit criterion:** No tested component can act outside its authority, and all effects are attributable and reversible within the sandbox.

### M6 — Learning and co-adaptation pilot

- Adapt one low-risk mechanism such as routing or relevance ranking.
- Maintain fixed held-out evaluations and rollback.
- Compare learned and fixed policies.

**Exit criterion:** Adaptation improves a system-level metric without unacceptable calibration, diversity, safety, or stability regression.

### M7 — Developmental world-model prototype

- Initialize Holon with a sparse explicit belief state while retaining capable pretrained components.
- Connect observation, prediction, outcome, and belief-revision records.
- Distinguish pretrained priors from acquired evidence.
- Add basic episodic and semantic consolidation.
- Add initial self-model and relationship-model schemas.
- Run repeated-experience, misinformation-recovery, and divergent-history experiments.

**Exit criterion:** Holon measurably improves through accumulated experience, explains the provenance of its beliefs, distinguishes inherited priors from grounded knowledge, appropriately revises early errors, and outperforms simpler memory baselines under controlled conditions.

### M8 — Scale decision

- Profile actual bottlenecks.
- Decide whether additional local hardware, including a possible DGX Spark 128 GB system, is justified.
- Reassess architecture, research value, and operational cost.

**Exit criterion:** Continue, pivot, scale, or stop based on measured evidence rather than architectural enthusiasm.

---

## 11. Open questions register

The following questions remain intentionally unresolved:

### Representation

- What is the minimum viable ontology for epistemic state?
- How should confidence, ambiguity, temporal validity, and conditional claims be encoded?
- Can one schema span domains without becoming vague or brittle?
- How should the system distinguish absence of evidence from evidence of absence?

### Belief revision

- Which update rules should be deterministic, statistical, model-mediated, or hybrid?
- How are correlated sources and repeated evidence prevented from inflating confidence?
- How should source reliability itself be learned and revised?
- When is a contradiction resolved versus merely dormant?

### Architecture

- How many specialists are useful?
- Does broad read access improve coherence or increase anchoring and correlated failure?
- What belongs in global state, and what should remain local or ephemeral?
- How should identity and continuity be defined across component replacement?
- What implementation allows the executive to coordinate without becoming the exclusive communication channel or de facto owner of cognition?

### Dynamics

- Which events and policies should initiate cognition when no user request is present?
- What causes a cognitive cycle to stop?
- How should events be prioritized under uncertainty?
- Can recurrent cognition discover useful connections without drifting into noise?

### Learning

- What should adapt first?
- Can components co-adapt without inventing opaque protocols or gaming shared metrics?
- How is diversity maintained when components learn from the same outcomes?
- Which adaptations require human review?
- How can developmental learning remain reversible while preserving meaningful continuity?

### Evaluation

- Which tasks genuinely require persistent system-level cognition?
- How can compute be matched fairly between architectures?
- What result would falsify the core hypothesis?
- How should capability gains be weighed against complexity, cost, and new failure modes?

### Safety and governance

- What information may enter persistent memory, for how long, and under whose control?
- What action classes must always require human approval?
- How can a corrupted global workspace be detected and restored?
- How should independent oversight or adversarial auditing be incorporated?

### Hardware

- Which workloads can run locally in Forge today?
- When does memory capacity, rather than orchestration quality, become the limiting factor?
- Would a 128 GB DGX Spark materially change the experimental frontier?

---

## 12. Non-goals

Project Holon is not currently intended to:

- prove or simulate consciousness;
- claim artificial general intelligence;
- anthropomorphize model orchestration as a mind without evidence;
- build an unrestricted autonomous agent;
- give models unsupervised control over consequential systems;
- replace humans as the final authority for high-impact decisions;
- maximize the number of agents or model calls;
- preserve every generated token forever;
- make a knowledge graph for its own sake;
- solve all memory, reasoning, or alignment problems at once;
- assume that multi-agent systems are inherently better than single-agent systems;
- justify expensive hardware before a measured bottleneck exists;
- optimize a polished user interface before the cognitive mechanisms are testable;
- treat compelling demos as substitutes for baselines, ablations, and repeated trials.
- imitate childhood through deliberately degraded language or reasoning;
- claim to be a blank slate while relying on pretrained models;
- treat user testimony as unquestionable truth;
- equate memory volume with cognitive development;
- optimize attachment, dependency, or agreement with a particular user;
- preserve all experiences indefinitely;
- present acquired or person-specific beliefs as universal facts without appropriate scope and provenance.

---

## 13. Decision log

### Agreed decisions

1. The project is named **Holon**.
2. The system is the unit of intelligence under study; language models are specialized processing components.
3. Persistent knowledge and cognitive state should live outside transient model context.
4. The architecture will use specialized, stateful neural models coordinated through a global cognitive workspace, which—not the executive—is the architectural center.
5. The epistemic core distinguishes observations, propositions, evidence, beliefs, and meta-beliefs.
6. Provenance and contradictions are first-class data, not optional annotations.
7. Every specialist can access the same global cognitive state and contribute evidence or proposed updates; participation in response to individual changes is selective.
8. A distinct executive model coordinates attention, priorities, decision resolution, and action selection without owning the workspace or monopolizing specialist communication.
9. Attention allocation and external action authority are separate functions and must be explicit.
10. Cognition is asynchronous, recurrent, event-driven, and capable of continuing without an active user, with strong noise and budget controls.
11. Local working state and durable global state must remain distinct.
12. Evaluation will begin with minimal experiments, controlled baselines, matched-resource comparisons where practical, and mechanism-level ablations.
13. Safety, auditability, bounded authority, rollback, and human oversight are architectural requirements.
14. Prototyping is Forge-first on the Ubuntu workstation with its NVIDIA RTX 5060 Ti 16 GB.
15. Existing pretrained models are the starting point; training every component from scratch is not required.

### Proposals to test

1. Structured persistent cognition can improve long-horizon coherence, calibration, belief revision, and recovery.
2. Multiple specialized components can outperform a comparable monolithic agent on selected tasks.
3. An event log and executive priority mechanism can allocate inference efficiently.
4. Selective contribution can retain useful diversity without polluting global state.
5. Routing and cooperation can eventually be learned or co-adapted safely under constraints.
6. A future DGX Spark 128 GB system may enable larger local experiments if profiling justifies it.
7. Developmental epistemic bootstrapping can produce a grounded epistemic biography while preserving a clear distinction between pretrained priors and acquired beliefs.
8. Experience-linked world, relationship, and self-models can improve prediction and adaptation without unacceptable imprinting, overfitting, sycophancy, or privacy costs.

### Explicitly unresolved

All implementation details not fixed above—including exact model assignments, model count, schemas, confidence representation, executive training and support mechanisms, update rules, consolidation policies, developmental maturity measures, identity semantics, learning methods, event guarantees, hardware acquisition, and degrees of autonomy—remain open to evidence.

---

## 14. Immediate next actions

### Accepted implementation sequence — 2026-10-24

Start with the smallest persistent belief-revision loop before building the full
benchmark: structured reports, explicit support/contradiction links, deterministic
qualitative belief states, SQLite persistence, and CLI inspection of provenance
and revision history. Reports in the first scenario share an explicit fixed scope.
No model call is necessary for this first engineering checkpoint. Next add one
model to propose validated structured records, then undertake comparative
research evaluation. Meta-beliefs, temporal reasoning, source reliability,
corrections, numerical confidence, specialists, and scheduling are deferred from
this checkpoint, not removed from the broader research program.

This sequence refines the near-term ordering below and the initial portion of M1;
it does not claim completion of M1 or evidence of architectural superiority.
See `experiments/001-belief-revision/protocol.md` for acceptance criteria and
`docs/decisions/0001-project-layout.md` for the repository layout decision.

### Broader next actions

1. Select a narrow domain for the first belief-revision benchmark.
2. Write the smallest viable schemas for the five epistemic object types.
3. Define the event and contribution interfaces.
4. Specify the strongest feasible controlled baselines.
5. Pre-register primary metrics and failure thresholds.
6. Build the one-model workspace prototype before adding specialist multiplicity.
7. Add replay, inspection, and cost accounting from the first run.
8. Run the initial experiment, publish negative as well as positive results, and revise the architecture from evidence.
9. Define how inherited priors, testimony, observation, inference, episodic memory, semantic belief, world models, relationship models, and self-model claims are represented without conflation.

---

## 15. Project stance

Holon is an ambitious architecture pursued with a deliberately skeptical method. Its animating idea is that persistent, organized, evidence-sensitive interaction among specialized processes may matter as much as the intelligence of any one process. Its discipline is to treat that idea as a falsifiable hypothesis.

The project succeeds in its first phase not by appearing mind-like, but by becoming measurable: it should know what it observed, distinguish that from what it inferred, retain why it believes what it believes, expose what remains contradictory or unknown, allocate attention deliberately, and act only within explicit authority. Everything beyond that must be earned experimentally.
