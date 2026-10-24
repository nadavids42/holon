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
CREATE TABLE IF NOT EXISTS revisions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    status TEXT NOT NULL CHECK (status IN ('supported', 'opposed', 'contested')),
    evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db
