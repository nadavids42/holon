-- Frozen schema-2 checkpoint before derivation migration.
BEGIN TRANSACTION;
CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES observations(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    relation TEXT NOT NULL CHECK (relation IN ('supports', 'contradicts'))
);
INSERT INTO "evidence" VALUES('0ea1188c-6ba6-43ef-8d2f-fef2e61a4ed4','079c4731-6017-486a-8bfe-1ee6c2dec11c','f12b45fa-4fc4-45fd-9625-b9ebf363eb72','supports');
INSERT INTO "evidence" VALUES('4f736e5a-4f0a-4f06-ba5c-d7af73ad2d2b','f584a09a-8d5b-43dc-a580-179ad1790273','f12b45fa-4fc4-45fd-9625-b9ebf363eb72','contradicts');
CREATE TABLE evidence_impact (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id), source TEXT NOT NULL,
    mass REAL NOT NULL CHECK(mass >= 0), semantics TEXT NOT NULL,
    cluster_id TEXT NOT NULL, cluster_actor TEXT, cluster_reason TEXT,
    event_key TEXT, request_digest TEXT,
    migration_id TEXT REFERENCES impact_migrations(id),
    UNIQUE(proposition_id, source, event_key)
);
INSERT INTO "evidence_impact" VALUES('0ea1188c-6ba6-43ef-8d2f-fef2e61a4ed4','f12b45fa-4fc4-45fd-9625-b9ebf363eb72','A',1.0,'stipulated-impact-v1','source:559aead08264d5795d3909718cdd05abd49572e84fe55590eef31a88a08fdffd',NULL,NULL,NULL,'v2:0f1ceddfe90d416b04f8031c9a9026ec73e6cc195d815bb36f73ed1e49d0a598',NULL);
INSERT INTO "evidence_impact" VALUES('4f736e5a-4f0a-4f06-ba5c-d7af73ad2d2b','f12b45fa-4fc4-45fd-9625-b9ebf363eb72','B',1.0,'stipulated-impact-v1','source:df7e70e5021544f4834bbee64a9e3789febc4be81470df629cad6ddb03320a5c',NULL,NULL,NULL,'62e7cab55bc8128a95d6e438c13c11fe5e77be7e5618efda4bd465ac9bbf804d',NULL);
CREATE TABLE impact_migrations (
    id TEXT PRIMARY KEY, actor TEXT NOT NULL, reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL, assumptions TEXT NOT NULL
);
CREATE TABLE interpretations (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    model TEXT NOT NULL, reason TEXT NOT NULL, prompt_version TEXT NOT NULL
);
CREATE TABLE observations (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, report TEXT NOT NULL,
    recorded_at TEXT NOT NULL
, observed_at TEXT);
INSERT INTO "observations" VALUES('079c4731-6017-486a-8bfe-1ee6c2dec11c','A','closed','2026-11-07T13:49:03.476116+00:00','2026-11-07T10:00:00.000000+00:00');
INSERT INTO "observations" VALUES('f584a09a-8d5b-43dc-a580-179ad1790273','B','open','2026-11-07T13:49:03.476565+00:00',NULL);
CREATE TABLE projection_policies (id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL);
INSERT INTO "projection_policies" VALUES('binary-beta-v1','{"decay_rate":0,"dynamics_version":"binary-beta-v1","mass_semantics":"stipulated-impact-v1","policy":{"alpha0":1.0,"beta0":1.0,"cluster_cap":1.0,"version":"binary-beta-v1"}}','7564f76f066ecf9ba924e02659feea936e40cc488c276f563f36a2de856e83b0');
CREATE TABLE propositions (
    id TEXT PRIMARY KEY, claim TEXT NOT NULL, scope TEXT NOT NULL
);
INSERT INTO "propositions" VALUES('f12b45fa-4fc4-45fd-9625-b9ebf363eb72','Door closed','lab at T0');
CREATE TABLE revisions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    status TEXT NOT NULL CHECK (status IN ('supported', 'opposed', 'contested', 'insufficient_evidence')),
    evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL
);
INSERT INTO "revisions" VALUES(1,'f12b45fa-4fc4-45fd-9625-b9ebf363eb72','supported','["0ea1188c-6ba6-43ef-8d2f-fef2e61a4ed4"]','2026-11-07T13:49:03.476116+00:00','active-presence-v2');
INSERT INTO "revisions" VALUES(2,'f12b45fa-4fc4-45fd-9625-b9ebf363eb72','contested','["0ea1188c-6ba6-43ef-8d2f-fef2e61a4ed4", "4f736e5a-4f0a-4f06-ba5c-d7af73ad2d2b"]','2026-11-07T13:49:03.476565+00:00','active-presence-v2');
INSERT INTO "revisions" VALUES(3,'f12b45fa-4fc4-45fd-9625-b9ebf363eb72','supported','["0ea1188c-6ba6-43ef-8d2f-fef2e61a4ed4"]','2026-11-07T13:49:03.476832+00:00','active-presence-v2');
CREATE TABLE withdrawals (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    actor TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL,
    replacement_evidence_id TEXT REFERENCES evidence(id)
);
INSERT INTO "withdrawals" VALUES('4f736e5a-4f0a-4f06-ba5c-d7af73ad2d2b','reviewer','Bad report','2026-11-07T13:49:03.476832+00:00',NULL);
CREATE INDEX evidence_proposition ON evidence(proposition_id);
CREATE TRIGGER immutable_projection_policies_UPDATE BEFORE UPDATE ON projection_policies BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
CREATE TRIGGER immutable_projection_policies_DELETE BEFORE DELETE ON projection_policies BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
CREATE TRIGGER immutable_evidence_impact_UPDATE BEFORE UPDATE ON evidence_impact BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
CREATE TRIGGER immutable_evidence_impact_DELETE BEFORE DELETE ON evidence_impact BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
CREATE TRIGGER immutable_impact_migrations_UPDATE BEFORE UPDATE ON impact_migrations BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
CREATE TRIGGER immutable_impact_migrations_DELETE BEFORE DELETE ON impact_migrations BEGIN SELECT RAISE(ABORT, 'immutable projection metadata'); END;
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('revisions',3);
COMMIT;
PRAGMA user_version=2;
