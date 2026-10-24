# Initial architecture

CLI → workspace service → SQLite.

Domain definitions describe records and deterministic evidence-presence rules.
The caller explicitly identifies a proposition, its shared scope, and the report's
relation. Optional Ollama interpretation proposes a relation; explicit human acceptance is required before a supporting or contradicting link is stored.
Observations, evidence links, and belief revisions commit in one transaction.
Current state is the latest revision; prior revisions retain their evidence IDs.
Recording timestamps are UTC ingestion times. Scope is caller-supplied text.
The database is a research prototype store, not a tamper-proof audit system.

## Interpretation boundary

`inference/inference.py` defines a provider-independent protocol and validated
proposal. `inference/ollama.py` uses Ollama's non-streaming `/api/chat` endpoint
with a JSON schema, followed by strict local validation. The CLI shows the
proposal before asking for acceptance. Uncertain/unrelated proposals are not
stored. Failed and declined attempts are not retained in this checkpoint.
Accepted interpretation metadata is stored atomically with the original report,
evidence, and belief revision in an additive `interpretations` table. Direct
structured reports continue to work without interpretation metadata.

The adapter follows https://docs.ollama.com/api/chat. Automated adapter/CLI tests
mock the transport/model; they do not establish live model classification quality.
