# Experiment 002: Adversarial binary Beta validation

Engineering acceptance protocol v1, 2026-11-05. Criteria written before the
first run. This validates the current stipulated-impact contract; it is not a
comparative study, calibration test, or proof of source independence.

Use the unchanged public domain/workspace APIs and actual CLI subprocesses.
All databases are created in temporary directories. Migrate only a copy of the
literal `legacy-v0.sql` fixture. Never open the user's runtime database. No model,
network, extra dependency, learned weights, decay, or commitment policy is needed.

`fixtures.json` contains fixed inputs and hand-specified expected readouts.
Groups expand to distinct deterministic evidence IDs; `independent` means
separately stipulated clusters, not measured independence. The runner also
reconstructs numeric readouts with rational arithmetic from those inputs and
checks the full explanation (IDs, exclusions, counts, clusters, and multipliers).
Floating-point comparisons use relative and absolute tolerance `1e-12`.
Counts, identities, states, retry results, and within-run snapshots compare exactly.

| Check | Acceptance criterion |
| --- | --- |
| Fixed fixtures and explanation | Every saved expectation and rational reconstruction agrees; excluded/withdrawn IDs remain accounted for |
| Ignorance versus balanced conflict | Both means are 0.5; balanced strength 20, opposing mass 10, balance 1; variance differs |
| Repetition versus stipulated independence | 500 copies contribute raw mass 500 but effective mass 1; ten separate origins contribute 10; no commitment decision |
| Per-sign caps | One cluster with masses +10 and -20 contributes +1 and -1 |
| Permutations and raw partitions | 25 seeded shuffles and partitions of sizes 1, 2, 3, 7, 17 yield the same full readout; summing capped partition results demonstrably fails |
| Keyed retries | Repeated identical request adds no record, revision, or mass; changed request under that key is rejected without a partial write |
| Shared lineage and lifecycle | Two source strings with an explicit shared origin contribute one support unit; correction and reinterpretation retain lineage and history; unrelated links survive |
| All withdrawn | Configured default prior parameters, mean, variance, and strength return exactly; records remain inspectable |
| Qualitative/readout divergence | Zero-mass support is qualitatively supported with prior readout; one positive and one fractional negative are contested even with mean above 0.5 |
| Restart and read-only inspection | Service and actual CLI restart reads agree; initialized-store reads make no changes to logical contents or database bytes |
| Legacy coverage | Original fixture is unchanged; copy upgrades atomically; missing metadata blocks readout; explicit annotation is approximate, repeatable, and preserves revision 7 |
| Invalid/numeric-range inputs | Negative, nonfinite, bool/string, huge integer, malformed snapshot/policy inputs fail explicitly; finite large inputs remain finite; aggregate overflow is an explicit read error |
| Transaction failures | Invalid writes and injected failures after intermediate inserts leave the entire logical database unchanged; migration failure leaves the pre-migration schema intact |

Finite per-record masses may be accepted even when their aggregate cannot be
represented. In that case projection must fail without writes, retain the valid
ledger, and recover after an offending link is withdrawn. This is distinct from
an invalid input write, which must be rejected atomically.

Output includes every scenario's verdict/error, input/checkpoint data, frozen
fixture hashes, policy/dynamics versions, source hashes, Git revision/dirty state,
and Python/SQLite versions. Service UUIDs and timestamps vary between fresh runs;
fixture readouts and verdicts are reproducible. Raw snapshot digests are only
expected to match when replaying the same persisted ledger. No timestamp/UUID
patching is used to conceal that distinction.

The runner must exit nonzero for failed scenarios, unreadable fixtures, or output
errors. It must continue through independent scenario failures and preserve their
diagnostics. Runner integration tests must demonstrate detection of a deliberately
wrong expected value and keep assertions active under Python optimization.

Exit: the full existing suite and runner checks pass, all scenarios pass, and a
saved explanation traces each reported value to input records. Failures require
investigation, not weakening expectations to fit the implementation.
