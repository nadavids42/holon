"""SQLite storage. Reports, links, and revisions commit atomically."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS propositions (
    id TEXT PRIMARY KEY, claim TEXT NOT NULL, scope TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, report TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES observations(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    relation TEXT NOT NULL CHECK (relation IN ('supports', 'contradicts'))
);
CREATE INDEX IF NOT EXISTS evidence_proposition ON evidence(proposition_id);
CREATE TABLE IF NOT EXISTS interpretations (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    model TEXT NOT NULL, reason TEXT NOT NULL, prompt_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS withdrawals (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    actor TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL,
    replacement_evidence_id TEXT REFERENCES evidence(id)
);
CREATE TABLE IF NOT EXISTS revisions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    status TEXT NOT NULL CHECK (status IN ('supported', 'opposed', 'contested', 'insufficient_evidence')),
    evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Database schema is newer than this implementation")
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(statement)
            definition = db.execute("SELECT sql FROM sqlite_master WHERE name = 'revisions'").fetchone()[0]
            if "insufficient_evidence" not in definition:
                db.execute("ALTER TABLE revisions RENAME TO revisions_legacy")
                db.execute(SCHEMA[SCHEMA.index("CREATE TABLE IF NOT EXISTS revisions"):].strip().rstrip(";"))
                db.execute("INSERT INTO revisions SELECT * FROM revisions_legacy")
                db.execute("DROP TABLE revisions_legacy")
            if version < 1:
                from holon.workspace.metadata import METADATA_SCHEMA, policy_payload, digest
                for statement in METADATA_SCHEMA.split(";"):
                    if statement.strip():
                        db.execute(statement)
                payload = policy_payload()
                db.execute("INSERT INTO projection_policies (id, payload, digest) VALUES (?, ?, ?)",
                           ("binary-beta-v1", payload, digest(payload)))
                # Policy/impact records are append-only, including migration assumptions.
                for table in ("projection_policies", "evidence_impact", "impact_migrations"):
                    for operation in ("UPDATE", "DELETE"):
                        db.execute(f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END")
                db.execute("PRAGMA user_version = 1")
        return db
    except Exception:
        db.close()
        raise
