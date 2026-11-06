-- Frozen pre-impact/pre-observation-time fixture; do not import the live schema.
PRAGMA foreign_keys = ON;
CREATE TABLE propositions (id TEXT PRIMARY KEY, claim TEXT NOT NULL, scope TEXT NOT NULL);
CREATE TABLE observations (id TEXT PRIMARY KEY, source TEXT NOT NULL, report TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE evidence (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id), proposition_id TEXT NOT NULL REFERENCES propositions(id), relation TEXT NOT NULL CHECK (relation IN ('supports','contradicts')));
CREATE TABLE revisions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposition_id TEXT NOT NULL REFERENCES propositions(id), status TEXT NOT NULL CHECK (status IN ('supported','opposed','contested')), evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL);
INSERT INTO propositions VALUES ('legacy-p', 'Door closed', 'lab door at T0');
INSERT INTO observations VALUES ('legacy-o', 'sensor A', 'Closed at T0', '2026-10-24T12:00:00+00:00');
INSERT INTO evidence VALUES ('legacy-e', 'legacy-o', 'legacy-p', 'supports');
INSERT INTO revisions VALUES (7, 'legacy-p', 'supported', '["legacy-e"]', '2026-10-24T12:00:00+00:00', 'presence-v1');
PRAGMA user_version = 0;
