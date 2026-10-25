# RFC-0002A: Belief Dynamics Revision

> **Cortex RFC Series**  
> A decision specification for replacing the prototype confidence dynamics in RFC-0002.

| Property | Value |
|---|---|
| **RFC** | RFC-0002A |
| **Title** | Belief Dynamics Revision |
| **Version** | 0.3.1 |
| **Status** | Review |
| **Author** | Nick Davidson |
| **Depends On** | RFC-0000, RFC-0001, RFC-0002, RFC-0003, RFC-0004 |
| **Amends** | RFC-0002 upon acceptance |
| **Referenced By** | Future RFC-0002 revision; future RFC-0005 |

---

## Abstract

RFC-0002 defines a runnable belief-state prototype, but its smoothing, batching, decay, reliability, and exclusivity rules do not form a coherent mathematical substrate. Reliability changes convergence speed without necessarily changing the limiting belief; batch and sequential ingestion disagree; linear lazy decay is not time-consistent; and normalized exclusive beliefs cannot enter the hard-contradiction state defined by the prototype.

This RFC specifies a narrower replacement program. Cortex **MUST** preserve timestamped evidence and provenance in an append-only logical ledger. Epistemic readout **MUST** be a deterministic projection of that ledger, the reliability-scoring ledger, relation policy, and query time. Evidence accumulation **MUST** obey a commutative evidence algebra so identity, permutation invariance, associativity, and batch equivalence hold by construction. Dependence discounting and decay **MUST** be applied by the canonical projection rather than irreversibly at ingest.

This RFC selects additive Beta/Dirichlet evidence as the replacement family. Bayesian log-odds driven by likelihood ratios remains a calibration reference for binary relations whose boundary contract can emit defensible likelihood ratios; it is not a competing substrate.

Subjective logic is treated as a representation and fusion vocabulary for Beta/Dirichlet evidence, not as a separate candidate. Bounded signed evidence is treated as an approximation to log-odds, not as a separate candidate.

The implementation program is therefore a time-boxed validation of Beta/Dirichlet against hard gates and preregistered acceptance thresholds, not an artificial comparison whose gates predetermine the winner.

---

## Table of Contents

1. [Motivation](#1-motivation)
2. [Scope and Ownership](#2-scope-and-ownership)
3. [Definitions and Notation](#3-definitions-and-notation)
4. [Diagnosis of the Prototype](#4-diagnosis-of-the-prototype)
5. [Normative Architecture](#5-normative-architecture)
6. [Normative Invariants](#6-normative-invariants)
7. [Selected Model and Calibration Reference](#7-selected-model-and-calibration-reference)
8. [Dependence, Decay, and Readout](#8-dependence-decay-and-readout)
9. [Exclusivity, Conflict, and Ambiguity](#9-exclusivity-conflict-and-ambiguity)
10. [Source Reliability](#10-source-reliability)
11. [Status and Decision Policy](#11-status-and-decision-policy)
12. [Validation and Acceptance](#12-validation-and-acceptance)
13. [Migration and Compatibility](#13-migration-and-compatibility)
14. [Security and Complexity](#14-security-and-complexity)
15. [Decisions and Open Mathematics](#15-decisions-and-open-mathematics)
16. [Future Work](#16-future-work)
17. [References](#17-references)

---

# 1. Motivation

Cortex requires a substrate that can distinguish:

- belief direction from evidence strength;
- independent corroboration from repetition;
- uncertainty from conflict;
- elapsed time from contrary observation;
- epistemic state from decision policy;
- current reliance from historical provenance.

The RFC-0002 prototype compresses several of these quantities into one scalar confidence. That made a useful implementation possible, but it also made some desired states unreachable and some results sensitive to batching and access patterns.

The purpose of this RFC is to select a finishable replacement, not to create an indefinite research program.

# 2. Scope and Ownership

## 2.1 This RFC Owns

This RFC owns:

- the canonical evidence ledger and projection model;
- algebraic requirements for evidence accumulation;
- the selected belief-state family and calibration reference;
- temporal discounting and prior recovery;
- dependence representation and discounting;
- the separation of state, readout, diagnostics, and status;
- migration semantics for replay-complete and replay-incomplete beliefs;
- the validation and acceptance rule.

## 2.2 This RFC Does Not Own

RFC-0003 owns extraction of observations and the boundary contract. RFC-0004 owns observation and introspection interfaces. A future RFC owns controller objectives and scalarization. Relation-specific validity models are configured by relation policy and are not inferred by this RFC.

## 2.3 Status of RFC-0002

Until a replacement is accepted and implemented, RFC-0002 remains the executable prototype. Its confidence dynamics **MUST NOT** be described as settled epistemic mathematics, and its zero-hard-contradiction simulation result **MUST NOT** be cited as validation.

# 3. Definitions and Notation

## 3.1 Evidence Record

An evidence record is

$$
e_i=(P_i,x_i,r_i,c_i,t_i,v_i,z_i),
$$

where:

| Symbol | Meaning |
|---|---|
| $P_i$ | proposition or exclusive group addressed |
| $x_i$ | signed support or boundary payload |
| $r_i$ | source-reliability reference and ingest-time estimate snapshot |
| $c_i$ | dependency-cluster identifier |
| $t_i$ | observation time |
| $v_i$ | validity interval or validity metadata |
| $z_i$ | provenance and transformation metadata |

The boundary payload differs by use. Additive evidence consumes support mapped to nonnegative evidence mass. A log-odds calibration reference consumes a likelihood ratio or log-likelihood ratio. The snapshot in $r_i$ is audit metadata; canonical projection uses the replayed reliability estimate specified in Section 10.

## 3.2 Ledger, Policy, and Projection

For proposition or group $P$, let

$$
L_P={e_i:P_i=P}
$$

denote its logical evidence ledger, and let $\Theta_P$ denote relation policy. The canonical operational state at query time $t$ is

$$
S_P(t)=\Phi(L_P,L_R,\Theta_P,t),
$$

where $L_R$ is the scoring-event ledger from which source-reliability state is replayed to the same temporal cut. $\Phi$ is a pure deterministic projection. An implementation **MAY** cache sufficient statistics or projections, but the cache **MUST** be observationally equivalent to recomputation from the same proposition ledger, reliability ledger, policy version, dynamics version, and query time.

## 3.3 State, Readout, Diagnostics, and Status

These are distinct:

$$
S_P(t)=\{(M^+_c(t),M^-_c(t)):c\in\mathcal C_P\},
$$

where $S_P(t)$ is the vector of raw, temporally projected positive and negative masses per dependency cluster. Candidate parameters are derived readout quantities rather than authoritative stored state:

$$
(L_P,L_R) \xrightarrow{\Phi} S_P(t)
\xrightarrow{g} w_P(t),
$$

$$
(L_P,S_P(t))\xrightarrow{h}\mathbf q_P(t),
$$

$$
(S_P(t),\mathbf q_P(t),\Pi_P)\xrightarrow{d}\sigma_P(t).
$$

Here $w_P(t)$ is a scalar readout, $\mathbf q_P(t)$ is a diagnostic vector, $\Pi_P$ is decision policy, and $\sigma_P(t)$ is status. Thresholds **MUST NOT** alter the underlying epistemic state.

## 3.4 Reliability Semantics

Every reliability value **MUST** declare one of these meanings:

1. **impact weight**: contribution to effective evidence mass;
2. **calibration estimate**: expected predictive correctness in a domain and time window;
3. **likelihood quality**: confidence in an emitted likelihood ratio;
4. **source ceiling**: a policy cap on reliance absent independent corroboration.

These meanings are not interchangeable. A composite reliability model **MUST** expose its components.

# 4. Diagnosis of the Prototype

## 4.1 Reliability and the Fixed Point

The prototype update is

$$
w^+=(1-\alpha r)w+\alpha r\widehat w.
$$

For constant $\widehat w$ and any $r>0$,

$$
\lim_{n\to\infty}w_n=\widehat w.
$$

Reliability therefore changes the rate but not the destination. This is defective if $r$ is intended as a source ceiling, but not necessarily if $r$ is evidence mass and repeated observations are genuinely independent. The prototype does not choose or label the semantics.

## 4.2 Batch and Sequential Ingestion

The prototype batch rule uses weighted means, so duplicating a batch does not change its aggregate. Processing those observations over separate turns applies multiple state updates. Therefore

$$
U(S,\{e_1,\ldots,e_n\})
\ne U(\cdots U(U(S,e_1),e_2),\ldots,e_n)
$$

in general.

## 4.3 Normalization Makes Hard Contradiction Unreachable

For an exclusive group with normalized nonnegative confidence,

$$
\sum_{j\in G}w_j=1.
$$

At the prototype commitment threshold $\tau_c=0.65$, two alternatives cannot both satisfy $w_j\ge\tau_c$. The reported absence of hard contradictions is therefore a consequence of the representation, not evidence that contradictions were handled.

## 4.4 Linear Lazy Decay Is Not a Semigroup

Repeated multiplication by $(1-\delta)$ and one delayed multiplication by $(1-k\delta)$ disagree for $k>1$. Read frequency can therefore affect state. A temporal rule must instead satisfy

$$
D_{a+b}=D_b\circ D_a.
$$

## 4.5 Reliability, Silence, and Ambiguity

The prototype updates source reliability from a caller-supplied value rather than an independently scored outcome. Decay is entangled with status transitions. Its ambiguity rule can be triggered by two negligible alternatives. These are semantic defects rather than parameter-tuning problems.

# 5. Normative Architecture

## 5.1 Append-Only Logical Evidence

Cortex **MUST** preserve each accepted evidence record and provenance linkage in an append-only logical ledger. Corrections **MUST** be represented by tombstones, superseding records, or equivalent auditable events; they **MUST NOT** silently rewrite history.

The requirement is logical, not physical. Compaction **MAY** occur if an auditable proof or retained checkpoint makes the canonical projection reproducible within declared tolerances.

## 5.2 Dependency Clusters

Evidence known or inferred to share a causal or derivational origin **MUST** carry the same dependency-cluster identifier or an explicit uncertain-dependence relation. Missing cluster information **MUST NOT** be interpreted as proven independence.

Source identity defines the minimum default cluster boundary, not proof of independence. Unlinked records from the same source identity **MUST** default to one cluster unless stronger lineage evidence supports a split. Records from distinct source identities **MAY** begin in distinct source-owned clusters, but they **MUST** be merged or coupled when shared lineage, coordination, derivation, or provenance uncertainty makes independence unsafe. Records with no stable source identity **MUST** enter a shared anonymous-source cluster. This default prevents both singleton-fragmentation attacks and the collapse of all early-deployment evidence into one global unknown cluster.

## 5.3 Canonical Projection

Reliability replay, temporal decay, validity filtering, and candidate-specific evidence conversion **MUST** be functions inside $\Phi$. Dependence weights and prior parameters **MUST** be applied by $g$ after raw per-cluster summaries have been formed. Ingest **MUST NOT** irreversibly discount an item based on which items happened to arrive first.

## 5.4 Derived Caches

A cache entry **MUST** record:

- proposition-ledger frontier or content digest;
- reliability-ledger frontier or content digest;
- relation-policy version;
- dynamics version;
- projection time or time basis;
- numeric tolerance and implementation version where relevant.

Cache refresh is not a new observation and **MUST NOT** change status except through the same canonical projection that an uncached read would use.

# 6. Normative Invariants

## 6.1 Commutative Evidence Algebra

For a fixed proposition, relation policy, dynamics version, reliability-ledger cut, and query time, the raw per-cluster mass vectors form a commutative monoid under componentwise addition

$$
(\mathcal E,\oplus,\mathbf 0).
$$

The state update is a monoid action $A:\mathcal S\times\mathcal E\to\mathcal S$ satisfying

$$
A(S,\mathbf0)=S,
$$

$$
A(A(S,E_1),E_2)=A(S,E_1\oplus E_2),
$$

$$
E_1\oplus E_2=E_2\oplus E_1.
$$

Consequently, identity evidence, associativity, permutation invariance, and batch/sequential equivalence hold for the same evidence multiset. Post-discount aggregate Beta parameters **MUST NOT** be treated as the monoid state because they cannot recover the component cluster masses required by later updates. This requirement does not assert that dependent observations are independent; dependence is represented in the cluster coordinates and interpreted only after the raw summaries are formed.

## 6.2 Domain Safety and Directionality

All states and readouts **MUST** remain in their declared domains. Holding all other projected evidence fixed, supportive evidence **MUST NOT** decrease support and contradictory evidence **MUST NOT** increase it.

For the concave cluster policy in Section 8.2, contemporaneous new evidence preserves effective-mass monotonicity. Let $M$ be undecayed raw cluster mass, $D\le M$ its temporally projected sum, and $\gamma(M)=f_R(M)/M$. Adding an infinitesimal mass at query time changes effective mass $\gamma(M)D$ at rate

$$
\frac{d}{dM}[\gamma(M)D]
=\gamma'(M)D+\gamma(M)
\ge \gamma'(M)M+\gamma(M)
=f_R'(M)\ge0.
$$

The inequality uses $\gamma'(M)\le0$, which follows from concavity of $f_R$ with $f_R(0)=0$. Backfilled, corrected, or newly linked historical records are replay revisions rather than contemporaneous observations; their effects **MUST** remain auditable but are not covered by this monotonicity lemma.

## 6.3 Time Consistency

Temporal projection **MUST** satisfy the semigroup law. For elapsed durations $a,b\ge0$,

$$
D_{a+b}=D_b\circ D_a.
$$

## 6.4 Access Invariance and Replay Determinism

At fixed proposition ledger, reliability-ledger cut, policy, dynamics version, and query time, readout **MUST** be independent of prior read schedule. Replay of the same inputs **MUST** reproduce the same state within a declared numeric tolerance.

## 6.5 Provenance Conservation

Discounting, decay, compaction, and status changes **MUST NOT** erase the ability to identify retained evidence origins and transformations.

## 6.6 Silence Neutrality

Without new evidence or an explicit validity/expected-observation model, temporal projection:

- **MUST NOT** fabricate negative evidence;
- **MUST NOT** change the sign of $w_P(t)-\mu_P$;
- **MUST NOT** move $w_P(t)$ away from prior readout $\mu_P$.

## 6.7 Conflict Observability

The state and diagnostics together **MUST** distinguish:

1. balanced weak evidence or ignorance;
2. balanced strong incompatible evidence;
3. strong evidence favoring one alternative.

This requirement is representation-neutral. It does not require independently normalized pre-constraint proposition scores.

# 7. Selected Model and Calibration Reference

## 7.1 Selected Family: Additive Beta/Dirichlet Evidence

For a binary proposition, effective positive and negative masses $a(t),b(t)\ge0$ combine with prior parameters $a_0,b_0>0$:

$$
p\mid L,t\sim\operatorname{Beta}(a_0+a(t),b_0+b(t)).
$$

The readout and effective strength are

$$
w(t)=\frac{a_0+a(t)}{a_0+b_0+a(t)+b(t)},
$$

$$
n_{\mathrm{eff}}(t)=a_0+b_0+a(t)+b(t).
$$

Define prior strength $\kappa_0=a_0+b_0$ and prior mean $\mu=a_0/\kappa_0$.

For an exhaustive exclusive group with $K$ alternatives plus an `other/unknown` category where required,

$$
\mathbf p\mid L,t\sim
\operatorname{Dirichlet}(\boldsymbol\alpha_0+\mathbf m(t)),
$$

$$
\pi_j(t)=
\frac{\alpha_{0j}+m_j(t)}
{\sum_k\alpha_{0k}+\sum_km_k(t)}.
$$

Beta is the $K=2$ case of this family. The design question is therefore when propositions are modeled independently and when they belong to an exhaustive categorical group, not which distribution “wins.”

### Subjective-Logic Representation

A binomial subjective-logic opinion

$$
(b,d,u,a)
$$

with evidence $(r,s)$ and prior weight $W$ maps to

$$
b=\frac r{r+s+W},\quad
d=\frac s{r+s+W},\quad
u=\frac W{r+s+W},
$$

$$
P=b+au=\frac{r+aW}{r+s+W}.
$$

This equals the Beta posterior mean under prior $(aW,(1-a)W)$. Subjective logic may provide useful names and fusion operators, but it is not a third state family.

### Strengths and Risks

The family is additive, auditable, uncertainty-aware, and naturally represents unknown mass. Its main risks are calibration of pseudo-count mass, uncertain dependence, and accidental interpretation of convenient conjugacy as proof that the boundary payload is truly binomial evidence.

## 7.2 Calibration Reference: Bayesian Log-Odds

For binary proposition $P$, let

$$
\ell(t)=\log\frac{\Pr(P\mid L,t)}{1-\Pr(P\mid L,t)}.
$$

With prior log-odds $\ell_0$ and projected log-likelihood contributions $q_i(t)$,

$$
\ell(t)=\ell_0+\sum_i q_i(t),
$$

$$
w(t)=\sigma(\ell(t))=\frac1{1+e^{-\ell(t)}}.
$$

This reference requires RFC-0003 to emit defensible likelihood ratios or a separately calibrated transformation from boundary outputs. Bounded signed evidence is permitted only as a documented approximation to $q_i$. A scalar log-odds state cannot distinguish no evidence from balanced strong opposing evidence; it therefore fails Sections 6.7 and 12.1 as a Cortex substrate unless augmented with an independently meaningful strength statistic. This RFC does not standardize such an augmentation.

For exclusive groups, a log-odds reference requires multinomial likelihoods or an explicit composition rule; independent one-vs-rest logits **MUST NOT** be normalized and treated as a categorical posterior without justification.

### Strengths and Risks

Log-odds gives a direct Bayesian calibration reference and additive likelihood evidence. Its limitations as a Cortex substrate are the loss of strength under cancellation, the cost and brittleness of likelihood calibration, extreme evidence domination, and a larger boundary-contract change.

# 8. Dependence, Decay, and Readout

## 8.1 Per-Record Temporal Mass

For evidence item $i$ that remains valid at query time $t\ge t_i$, define a baseline temporal multiplier

$$
\eta_i(t)=e^{-\lambda_R(t-t_i)},
$$

where $\lambda_R\ge0$ is declared by relation policy $R$.

Positive and negative evidence for the same relation policy **MUST** share the same $\lambda_R$. Asymmetric forgetting would move the readout during silence and therefore requires an explicit validity or expected-observation model outside ordinary decay.

The shared rate is also required for the scale-invariant cluster projection in Section 8.2. Relaxing it would invalidate the Silence Neutrality guarantee in Section 6.6.

## 8.2 Cluster-Level Discounting

For sign $s\in\{+,-\}$, define the undecayed raw mass of dependency cluster $c$ as

$$
M^{s,\mathrm{raw}}_c=\sum_{i\in c,\,s_i=s}m_i.
$$

Dependence discounting **MUST** use a mass-independent, versioned cluster multiplier $\gamma^s_c\in[0,1]$ during temporal projection:

$$
\widetilde M^s_c(t)=\gamma^s_c
\sum_{i\in c,\,s_i=s}m_i e^{-\lambda_R(t-t_i)}.
$$

The multiplier **MUST NOT** be recomputed from the decayed mass. One admissible calibration derives it from an undecayed concave repetition-control function $f_R(\cdot;\beta_R)$:

$$
\gamma^s_c=
\begin{cases}
f_R(M^{s,\mathrm{raw}}_c;\beta_R)/M^{s,\mathrm{raw}}_c,
&M^{s,\mathrm{raw}}_c>0,\\
0,&M^{s,\mathrm{raw}}_c=0,
\end{cases}
$$

where $f_R$ is nonnegative, monotone, concave, and satisfies $f_R(0;\beta_R)=0$. For example,

$$
f_R(M;\beta_R)=\beta_R\ln\!\left(1+\frac{M}{\beta_R}\right),
\qquad \beta_R>0,
$$

has unit slope at the origin and makes the repetition-control scale explicit. Other calibrated multipliers are permitted if they satisfy the same scale-invariance and audit requirements.

For a fixed evidence ledger between evidence arrivals, $\gamma^s_c$ is time-independent. Because positive and negative evidence share $\lambda_R$, ordinary decay then scales all effective masses by a common factor $\theta$. For constants $C,D\ge0$, the Beta readout becomes

$$
w(\theta)=\frac{a_0+C\theta}{\kappa_0+(C+D)\theta}.
$$

Its derivative has the constant sign of $Cb_0-a_0D$, so it moves monotonically toward the prior and cannot cross it during silence. This is a piecewise scale-invariance result under the no-new-evidence precondition in Section 6.6; an evidence arrival may change both raw mass and $\gamma^s_c$. Any dependence policy **MUST** demonstrate the same fixed-ledger property. Ingest-time discounts that depend on prior arrival order are prohibited.

Missing dependency metadata **MUST** be resolved conservatively under Section 5.2. A new record **MUST NOT** receive a fresh singleton cluster merely because its lineage is unknown. Distinct source-owned clusters remain subject to later deterministic merging or coupling when dependency evidence appears.

## 8.3 Prior Recovery

For relations with $\lambda_R>0$, $\eta_i(t)\to0$ as $t\to\infty$, so operational state returns toward its prior while the historical ledger remains intact. When $\lambda_R=0$, evidence does not decay and prior recovery is not claimed. Thus Cortex can simultaneously report low current evidential strength and extensive historical provenance where decay policy applies. RFC-0004 **MUST** expose historical observation counts, raw cluster-level masses, dependence multipliers, and effective projected mass so an explanation can show why repetition did or did not increase certainty.

## 8.4 Derivative Semantics

For continuous readout $w(t)$, introspection may report

$$
\dot w(t)=\frac{dw(t)}{dt}.
$$

For discrete revisions it must report

$$
\Delta w_k=w_k-w_{k-1}.
$$

The two **MUST NOT** be mixed.

# 9. Exclusivity, Conflict, and Ambiguity

## 9.1 Exclusive Groups

For a genuinely exhaustive group,

$$
\sum_{j\in G}\pi_j=1,
\qquad \pi_j\ge0.
$$

A group that is not provably exhaustive **MUST** include `other/unknown`. Exclusivity is a hypothesis-space constraint, not contradiction resolution.

## 9.2 Candidate-Neutral Conflict

Conflict diagnostics **MUST** use at least direction and strength. For a categorical group with projected alternative masses $m_j$ and total mass $n=\sum_jm_j$, one admissible diagnostic pair is

$$
B(G)=1-\frac{m_{(1)}-m_{(2)}}{m_{(1)}+m_{(2)}+\varepsilon},
$$

$$
S(G)=m_{(1)}+m_{(2)},
$$

where $m_{(1)}\ge m_{(2)}$ are the largest two masses. High $B$ with high $S$ indicates strong conflict; high $B$ with low $S$ indicates ignorance or weak ambiguity.

Operational conflict **MUST** use effective masses after dependence weighting. The audit view **MUST** additionally expose the corresponding raw masses so a high raw disagreement that is operationally discounted remains visible and explainable. The final conflict diagnostic is not selected by this draft, but it **MUST** satisfy the three-way distinction in Section 6.7 and be reachable in adversarial tests.

## 9.3 Ambiguity

Operational ambiguity requires both closeness and plausibility:

$$
\pi_{(1)}-\pi_{(2)}\le\delta
$$

and either $\pi_{(1)}\ge\tau_{\min}$ or sufficient projected evidence strength. Two negligible alternatives **MUST NOT** trigger ambiguity solely because they are close.

# 10. Source Reliability

Source reliability denotes an externally scored or explicitly proxy estimate for a declared domain and time window. It **MUST NOT** be learned solely from the source's own asserted reliability or agreement with beliefs created by that source.

Canonical projection **MUST** use the source estimate obtained by replaying the scoring-event ledger $L_R$ to query time $t$, not the estimate snapshot stored at evidence ingest. A later independently scored reliability event may therefore reweight earlier evidence. This retroactive reweighting is versioned and auditable; it does not rewrite the evidence ledger.

A scoring event **MUST NOT** be derived from a belief projection that includes the source being scored. When corroboration is used as a labeled proxy, Cortex **MUST** compute a leave-one-source-out projection

$$
S_{P,-c}(t)=\Phi(L_P\setminus L_{P,c},L_R,\Theta_P,t),
$$

where $L_{P,c}$ contains every record attributable to source $c$. The score may compare source $c$ with $S_{P,-c}(t)$, subject to a declared causal-separation policy that also prevents recursive or mutually self-confirming reliability updates. Source-owned clusters make this exclusion cheap; if a dependency cluster mixes sources, its raw mass and multiplier **MUST** be recomputed after exclusion. If source identity is unavailable inside a shared anonymous cluster, corroboration **MUST NOT** score an individual contributor from that cluster.

Where scored binary outcomes exist,

$$
r_c\sim\operatorname{Beta}(A_c,B_c),
$$

$$
A_c\leftarrow A_c+y,
\qquad B_c\leftarrow B_c+(1-y),
$$

for outcome score $y\in[0,1]$. Corroboration, later correction, or trusted adjudication may be used as labeled proxies. Domain-conditioned estimates are preferred; an MVP scalar **MAY** be used if its limitation is explicit.

Calibration **SHOULD** be evaluated with Brier score, log loss, reliability diagrams, and expected calibration error where ground truth exists.

# 11. Status and Decision Policy

## 11.1 Status Vocabulary

The substrate defines the following mutually exclusive operational statuses:

| Status | Meaning |
|---|---|
| `uncertain` | replay-complete, $n_{\mathrm{eff}}\ge n_{\min}$, and no commitment or rejection predicate is met |
| `committed` | commitment predicate is met |
| `rejected` | explicit contrary-evidence or validity predicate is met |
| `dormant` | previously actionable state has decayed because relevance or validity expired under explicit policy |
| `unsupported` | replay-complete, $n_{\mathrm{eff}}<n_{\min}$, without explicit contrary evidence |
| `replay_incomplete` | historical evidence cannot reconstruct required state under the selected dynamics |

`unsupported` is not `rejected`. The policy threshold $n_{\min}$ makes `unsupported` and `uncertain` disjoint. `dormant` requires an explicit temporal applicability policy; mere silence otherwise yields `unsupported` or `uncertain`.

## 11.2 Commitment and Rejection

For posterior models, a candidate commitment rule is

$$
\operatorname{commit}(P)
\iff
\Pr(p_P\ge\theta\mid S)\ge1-\alpha_{\mathrm{sig}}
\land n_{\mathrm{eff}}\ge n_{\min}.
$$

The notation $\alpha_{\mathrm{sig}}$ avoids collision with RFC-0002's learning-rate symbol. Thresholds remain undetermined.

Rejection **MUST** require explicit contrary evidence or an explicit validity/expected-observation model. Read access and ordinary decay **MUST NOT** create rejection.

## 11.3 Supersession

Supersession is a policy transition over an exclusive group. It **SHOULD** require leader plausibility, separation from the runner-up, sufficient strength, and hysteresis. It **MUST NOT** rewrite the superseded belief's evidence history.

## 11.4 Scalarization Boundary

The substrate may expose

$$
\mathbf q=(\text{mean},\text{uncertainty},\text{recency},
\text{diversity},\text{conflict}).
$$

A consumer optimizing over $\mathbf q$ **MUST** define a total or partial ordering, constraints, or scalar objective. There is no meaningful `argmax` over an unordered vector.

# 12. Validation and Acceptance

## 12.1 Hard Gates

The selected Beta/Dirichlet substrate **MUST** demonstrate:

1. the commutative evidence algebra;
2. time consistency and access invariance;
3. deterministic replay;
4. provenance conservation;
5. direction distinct from strength;
6. the conflict distinction in Section 6.7;
7. exclusive groups with `other/unknown` where required;
8. explicit reliability semantics;
9. numerical stability under long and adversarial sequences;
10. migration behavior for incomplete replay.

Failure of any gate blocks acceptance. Scalar log-odds is not evaluated as a substrate because cancellation cannot satisfy gates 5 and 6 without an additional strength state that this RFC does not specify.

## 12.2 Required Scenarios

Evaluation **MUST** include:

| Scenario | Required observation |
|---|---|
| One high-impact assertion | No commitment unless policy explicitly permits it |
| Duplicates within one cluster | Mass-independent cluster weighting limits false certainty |
| Many weak independent clusters | Behavior matches declared reliability semantics |
| Trusted sources disagree | Strong conflict differs from ignorance |
| Long silence | Readout moves monotonically toward prior without crossing it unless explicit validity policy applies |
| Frequent versus rare reads | Same state at the same query time |
| Batch versus randomized order | Same result within declared tolerance |
| New exclusive alternative | Unknown mass and prior behavior remain defined |
| Coordinated sources | Identifier count alone does not imply independence |
| Replay-incomplete migration | Status is explicit and no evidence is invented |
| Uniform temporal attenuation | Direction relative to prior is unchanged |
| Unknown provenance | Records are conservatively merged, not granted singleton independence |
| Reliability correction | Historical evidence is reproducibly reweighted without a causal loop |
| Leave-one-source-out scoring | Scored source contributes no evidence to its reference projection |
| Commitment reachability | Jointly calibrated $\beta_R$, $\kappa_0$, $n_{\min}$, and thresholds permit commitment on preregistered sufficient-evidence cases |
| Reliability cache invalidation | Eager and lazy strategies agree with uncached replay after a scoring event |

## 12.3 Acceptance Thresholds and Preregistration

Substrate acceptance is pass/fail. Each hard gate and empirical criterion **MUST** have a preregistered acceptance threshold. No aggregate score or lexicographic ordering may compensate for a failed hard gate.

The thresholds, datasets, metric definitions, test harness revision, and evaluation policy **MUST** be committed with a timestamp and content digest before results are run. Any later change **MUST** be recorded as a prospective amendment and **MUST NOT** be applied retroactively to existing results. Indifference bands apply only to reported prototype or calibration-reference comparisons under Section 13.3; they do not determine substrate acceptance.

## 12.4 Timebox and Default

Implementation and validation are time-boxed to four weeks from the first committed test harness. Beta/Dirichlet is accepted if it passes every hard gate and every preregistered acceptance threshold. Log-odds **MAY** be reported as a calibration reference on the subset of binary relations for which defensible likelihood ratios exist, but it does not participate in substrate selection.

The timebox may be extended only by a dated amendment naming a specific unresolved gate or invalid experiment. General interest in further mathematical comparison is not sufficient.

## 12.5 Architecture Retrieval Study

The previously proposed retrieval comparison is renamed the **Architecture Retrieval Study** to avoid collision with “Study 1” in the control memoranda. It **MUST** compare direct retrieval, confidence/recency reranking, epistemic-feature reranking, and an oracle or upper bound where feasible. Degradation curves **SHOULD** vary noise, staleness, graph size, and adversarial duplication.

# 13. Migration and Compatibility

## 13.1 Replay Classification

Each migrated belief **MUST** be classified:

- `replay_complete`: the retained ledger and metadata can instantiate the selected model;
- `replay_approximate`: a declared approximation can be computed without inventing unavailable facts;
- `replay_incomplete`: required evidence semantics, dependence, likelihood, or provenance are unavailable.

Replay-incomplete beliefs enter `replay_incomplete`, not `committed` or `rejected`. They may re-earn ordinary status from new sufficient evidence. Existing product policy may display their legacy status separately, but the new substrate **MUST NOT** claim that the new commitment predicate was met.

## 13.2 Schema Requirements

The selected model requires versioned fields for support semantics, reliability semantics, dynamics, relation policy, dependency clusters, observation time, validity, scoring events, and raw boundary outputs. Exact schema changes remain implementation-owned by the RFC-0002 revision.

## 13.3 Dual Run

The prototype and selected substrate **SHOULD** run side by side over the same evidence stream before replacement. The new substrate **MUST NOT** affect production decisions during validation. Divergences in readout, status, conflict, and explanation **MUST** be recorded.

Any comparative claim against the prototype or log-odds calibration reference **MUST** name its metric and a preregistered indifference band $\varepsilon_k$. Differences within $\varepsilon_k$ are reported as practically indistinguishable for that metric. These comparisons are diagnostic and **MUST NOT** override the pass/fail acceptance rule in Section 12.3.

# 14. Security and Complexity

## 14.1 Threat Model

The substrate assumes evidence may be duplicated, delayed, strategically phrased, provenance-laundered, reliability-spoofed, or coordinated across Sybil identities. Source count alone **MUST NOT** establish independence.

Known derived evidence **MUST** retain common lineage. Unknown lineage **MUST** use the source-identity defaults in Section 5.2 rather than singleton clusters; missing source identity uses the shared anonymous-source cluster. Exclusive groups **MUST** preserve unknown mass when incomplete. Rate limits, cluster caps, or evidence-mass caps **MAY** be used if their semantic effect is versioned and auditable.

## 14.2 Complexity Model

Let $N$ be retained evidence records, $N_R$ retained reliability-scoring events, $C_P$ the dependency-cluster count for proposition $P$, and $K$ the size of an exclusive group.

The canonical un-compacted bounds are:

- $O(1)$ append per evidence record, excluding index maintenance;
- $O(N+N_R)$ total proposition and reliability-ledger storage;
- $O(C_P)$ proposition readout from cluster summaries;
- $O(KC)$ group diagnostics in the worst case, where $C$ is the relevant cluster count;
- $O(1)$ lookup of a valid cached projection;
- state storage $O(C_P)$ per proposition before safe compaction, not $O(1)$.

A reliability-scoring event for source $c$ logically invalidates cached projections for every proposition whose retained evidence references $c$, including propositions reached through any declared reliability dependency. If $F_c$ is that fan-out, eager invalidation costs $O(F_c)$ plus index maintenance. An implementation **MAY** instead use source/reliability-ledger version checks for lazy invalidation, preserving $O(1)$ cache lookup only when validity can be established in $O(1)$ from the cache key. Either strategy **MUST** produce the canonical projection and expose invalidation lag or recomputation cost in operational metrics.

An implementation **MAY** cap or merge long-tail clusters, but the policy **MUST** be deterministic, auditable, and evaluated for adversarial sensitivity. It **MUST NOT** claim exact replay after lossy compaction.

# 15. Decisions and Open Mathematics

## 15.1 Decided by This Draft

If accepted, this RFC decides:

- RFC-0002 dynamics are prototype behavior pending replacement.
- The logical evidence ledger is authoritative; operational state is a pure deterministic projection.
- Exact reproducible caches are permitted but cannot define alternate semantics.
- Evidence accumulation obeys a commutative monoid action.
- Dependence and ordinary decay are evaluated by canonical projection, not irreversibly at ingest.
- Ordinary positive and negative evidence share one decay rate per relation policy.
- State, readout, diagnostics, and decision status are separate.
- Conflict observability is defined by distinguishing ignorance, strong conflict, and a strong winner.
- Additive Beta/Dirichlet is the selected replacement family.
- Bayesian log-odds is retained only as a calibration reference where defensible likelihood ratios exist.
- Subjective logic is a Beta/Dirichlet representation/fusion vocabulary, not a separate candidate.
- Bounded signed evidence is an approximation to log-odds, not a separate candidate.
- Replay-incomplete beliefs receive an explicit status and do not silently retain or lose commitment.
- Validation uses pass/fail hard gates, preregistered thresholds, and a four-week timebox; indifference bands apply only to diagnostic comparisons.
- Authoritative state is the raw per-cluster mass vector; Beta/Dirichlet parameters are derived at readout.
- Dependence weighting is mass-independent during temporal projection so ordinary decay is scale-invariant and silence-neutral.
- Canonical projection replays the reliability ledger to the same temporal cut and may retroactively reweight evidence.

## 15.2 Open Mathematical and Empirical Questions

1. What mapping converts RFC-0003 support into evidence mass without false precision?
2. Can RFC-0003 produce calibrated likelihood ratios at acceptable cost for the log-odds reference?
3. What joint calibration of repetition-control scale $\beta_R$, prior strength $\kappa_0$, minimum effective mass $n_{\min}$, and commitment thresholds best resists duplication, permits reachable commitment, and controls false commitment under the intended downstream loss?
4. How should uncertain, overlapping, or nested dependency clusters compose?
5. When does a set of propositions become an exhaustive Dirichlet group rather than independent Beta states?
6. What candidate-neutral conflict diagnostic best separates ignorance, strong disagreement, and multimodal source partitions?
7. Which uncertainty quantities must RFC-0004 expose?
8. What relation-specific decay rates correspond to real environmental volatility?
9. What compaction or cluster-merge policy provides an acceptable exactness/cost tradeoff?
10. What numerical tolerances define deterministic equivalence across implementations?

These questions are calibration and interface work around the selected substrate. They do not reopen the removed candidate comparison.

# 16. Future Work

After acceptance:

1. revise RFC-0002's dynamics, contradiction, status, and source-credibility sections;
2. update RFC-0003's boundary payload and reliability semantics;
3. update RFC-0004 to expose historical counts, operational mass, uncertainty, conflict, and discrete versus continuous change correctly;
4. implement property-based and adversarial tests derived from the hard gates;
5. rerun the toy world with reachable strong conflict and randomized ingestion order;
6. run the Architecture Retrieval Study;
7. define a series-wide notation registry so symbols do not silently change meaning across RFCs;
8. archive prototype simulation claims that rely on unreachable hard contradiction.

# 17. References

- RFC-0000: Cortex Documentation Standard.
- RFC-0001: Computational Epistemology.
- RFC-0002: Belief-State Substrate, version 4.0.
- RFC-0003: Boundary Layer.
- RFC-0004: Observation & Introspection Layer.
- *Toward an Objective Function for Computational Epistemology*.
- *Cortex as a Bounded Epistemic Control System*.
- Current reference files: `schema.sql`, `belief_store.py`, `simulation.py`, and `coherence_engine.py`.

---

## Closing Principle

> Cortex should preserve evidence first, derive belief deterministically, and prefer the simplest model that survives falsification.