# Initial architecture

CLI → workspace service → SQLite.

Domain definitions describe records and deterministic evidence-presence rules.
The caller explicitly identifies a proposition, its shared scope, and the report's
relation. No language interpretation or model inference is performed yet.
Observations, evidence links, and belief revisions commit in one transaction.
Current state is the latest revision; prior revisions retain their evidence IDs.
Recording timestamps are UTC ingestion times. Scope is caller-supplied text.
The database is a research prototype store, not a tamper-proof audit system.
