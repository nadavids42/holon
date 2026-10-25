"""Versioned experimental impact semantics; no learned source reliability."""
from dataclasses import asdict
import hashlib
import json

from holon.domain.projection import ProjectionPolicy, DYNAMICS_VERSION

SEMANTICS = 'stipulated-impact-v1'
METADATA_SCHEMA = """
CREATE TABLE projection_policies (id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE impact_migrations (
    id TEXT PRIMARY KEY, actor TEXT NOT NULL, reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL, assumptions TEXT NOT NULL
);
CREATE TABLE evidence_impact (
    evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id), source TEXT NOT NULL,
    mass REAL NOT NULL CHECK(mass >= 0), semantics TEXT NOT NULL,
    cluster_id TEXT NOT NULL, cluster_actor TEXT, cluster_reason TEXT,
    event_key TEXT, request_digest TEXT,
    migration_id TEXT REFERENCES impact_migrations(id),
    UNIQUE(proposition_id, source, event_key)
);
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def policy_payload():
    return canonical({'policy': asdict(ProjectionPolicy()), 'dynamics_version': DYNAMICS_VERSION,
                      'mass_semantics': SEMANTICS, 'decay_rate': 0})


def source_cluster(source):
    return 'source:' + digest(source)
