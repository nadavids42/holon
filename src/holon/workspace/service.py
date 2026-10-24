"""Explicit structured contributions; no natural-language inference yet."""
import json
from datetime import datetime, timezone
from uuid import uuid4

from holon.domain.records import Relation, belief_status
from holon.workspace.storage import connect


def required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be blank")
    return value


class Workspace:
    def __init__(self, path):
        self.db = connect(path)

    def close(self):
        self.db.close()

    def create_proposition(self, claim: str, scope: str) -> str:
        claim, scope = required(claim, "claim"), required(scope, "scope")
        identifier = str(uuid4())
        with self.db:
            self.db.execute("INSERT INTO propositions VALUES (?, ?, ?)",
                            (identifier, claim, scope))
        return identifier

    def add_report(self, proposition_id: str, source: str, report: str,
                   relation: str) -> dict:
        source, report = required(source, "source"), required(report, "report")
        relation = Relation(relation)
        now = datetime.now(timezone.utc).isoformat()
        observation_id, evidence_id = str(uuid4()), str(uuid4())
        with self.db:
            # Serialize read/modify/write across concurrent CLI processes.
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM propositions WHERE id = ?",
                                   (proposition_id,)).fetchone():
                raise ValueError(f"Unknown proposition: {proposition_id}")
            self.db.execute("INSERT INTO observations VALUES (?, ?, ?, ?)",
                            (observation_id, source, report, now))
            self.db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?)",
                            (evidence_id, observation_id, proposition_id, relation.value))
            rows = self.db.execute(
                "SELECT id, relation FROM evidence WHERE proposition_id = ? ORDER BY rowid",
                (proposition_id,)).fetchall()
            status = belief_status({Relation(row["relation"]) for row in rows}).value
            self.db.execute("INSERT INTO revisions (proposition_id, status, evidence_ids, recorded_at, policy) VALUES (?, ?, ?, ?, ?)",
                            (proposition_id, status, json.dumps([r["id"] for r in rows]), now, "presence-v1"))
        return {"observation_id": observation_id, "evidence_id": evidence_id,
                "status": status}

    def inspect(self, proposition_id: str) -> dict:
        # One snapshot for a consistent inspection during concurrent writes.
        with self.db:
            self.db.execute("BEGIN")
            row = self.db.execute("SELECT * FROM propositions WHERE id = ?",
                                  (proposition_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown proposition: {proposition_id}")
            evidence = [dict(r) for r in self.db.execute(
                "SELECT e.id, e.relation, o.id AS observation_id, o.source, o.report, o.recorded_at "
                "FROM evidence e JOIN observations o ON o.id = e.observation_id "
                "WHERE e.proposition_id = ? ORDER BY e.rowid", (proposition_id,))]
            history = [dict(r) for r in self.db.execute(
                "SELECT sequence, status, evidence_ids, recorded_at, policy FROM revisions "
                "WHERE proposition_id = ? ORDER BY sequence", (proposition_id,))]
            for revision in history:
                revision["evidence_ids"] = json.loads(revision["evidence_ids"])
            return {"proposition": dict(row),
                    "status": history[-1]["status"] if history else "insufficient_evidence",
                    "evidence": evidence, "history": history}
