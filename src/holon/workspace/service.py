"""Validated contributions and atomic, provenance-preserving belief updates."""
import json
import re
from dataclasses import asdict
from holon.domain.projection import ProjectionEvidence, ProjectionPolicy, project_binary, DYNAMICS_VERSION
from holon.workspace.metadata import SEMANTICS, canonical, digest, source_cluster
from datetime import datetime, timezone
from uuid import uuid4

from holon.domain.records import Relation, belief_status
from holon.workspace.storage import connect


def required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be blank")
    return value


_OBSERVED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")


def normalize_observed_at(value):
    """Normalize an explicitly supplied instant; None means unknown."""
    if value is None:
        return None
    if not isinstance(value, str) or not _OBSERVED_AT.fullmatch(value):
        raise ValueError("observed_at must be an ISO timestamp with seconds and UTC offset")
    try:
        normalized = value.replace('Z', '+00:00')
        # Python 3.10 accepts fractional seconds only in certain lengths.
        normalized = re.sub(r'\.(\d{1,6})(?=[+-]\d{2}:\d{2}$)',
                            lambda match: '.' + match.group(1).ljust(6, '0'), normalized)
        timestamp = datetime.fromisoformat(normalized)
        # fromisoformat accepts some out-of-range offset components (e.g. +01:60).
        offset = value[-6:] if not value.endswith('Z') else None
        if offset and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
            raise ValueError("Invalid UTC offset")
        return timestamp.astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError, OverflowError) as error:
        raise ValueError("Invalid observed_at timestamp") from error


def request_digest(payload, observed_at):
    # Preserve version-1 digests for unknown times, including existing event keys.
    if observed_at is None:
        return digest(canonical(payload))
    return 'v2:' + digest(canonical({'operation_request': payload, 'observed_at': observed_at}))


class Workspace:
    def __init__(self, path):
        self.db = connect(path)

    def close(self):
        self.db.close()

    def create_proposition(self, claim: str, scope: str) -> str:
        claim, scope = required(claim, "claim"), required(scope, "scope")
        identifier = str(uuid4())
        with self.db:
            self.db.execute("INSERT INTO propositions (id, claim, scope) VALUES (?, ?, ?)",
                            (identifier, claim, scope))
        return identifier

    def record_observation(self, source, report, *, observed_at=None):
        source = required(source, 'source')
        required(report, 'report')
        observed_at = normalize_observed_at(observed_at)
        identifier = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute('INSERT INTO observations (id, source, report, recorded_at, observed_at) VALUES (?, ?, ?, ?, ?)',
                            (identifier, source, report, now, observed_at))
        return identifier

    def inspect_observation(self, observation_id):
        with self.db:
            self.db.execute('BEGIN')
            observation = self.db.execute('SELECT * FROM observations WHERE id=?', (observation_id,)).fetchone()
            if observation is None:
                raise ValueError(f'Unknown observation: {observation_id}')
            links = [dict(row) for row in self.db.execute(
                'SELECT e.id AS evidence_id, e.proposition_id, e.relation, w.recorded_at AS withdrawn_at, '
                'w.actor AS withdrawal_actor, w.reason AS withdrawal_reason, w.replacement_evidence_id '
                'FROM evidence e LEFT JOIN withdrawals w ON w.evidence_id=e.id '
                'WHERE e.observation_id=? ORDER BY e.rowid', (observation_id,))]
            for link in links:
                link['active'] = link['withdrawn_at'] is None
            return {'observation': dict(observation), 'links': links}

    def link_observation(self, observation_id, proposition_id, relation, interpretation=None, *,
                         mass=1.0, event_key=None, cluster_id=None, cluster_actor=None, cluster_reason=None):
        relation = Relation(relation)
        self._validate_interpretation(interpretation, relation.value)
        if event_key is not None:
            event_key = required(event_key, 'event key')
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            observation = self.db.execute('SELECT source FROM observations WHERE id=?', (observation_id,)).fetchone()
            if observation is None:
                raise ValueError(f'Unknown observation: {observation_id}')
            if not self.db.execute('SELECT 1 FROM propositions WHERE id=?', (proposition_id,)).fetchone():
                raise ValueError(f'Unknown proposition: {proposition_id}')
            source = observation['source']
            cluster, actor, reason = self._cluster(source, cluster_id, cluster_actor, cluster_reason)
            mass = ProjectionEvidence('validate', proposition_id, cluster, relation, mass).mass
            request = 'link-v1:' + digest(canonical({'operation': 'link', 'observation_id': observation_id,
                'proposition_id': proposition_id, 'relation': relation.value, 'mass': mass, 'cluster': cluster,
                'actor': actor, 'reason': reason, 'interpretation': asdict(interpretation) if interpretation else None}))
            if event_key is not None:
                prior = self.db.execute('SELECT m.request_digest, e.id, e.observation_id FROM evidence_impact m JOIN evidence e ON e.id=m.evidence_id WHERE m.proposition_id=? AND m.source=? AND m.event_key=?',
                                        (proposition_id, source, event_key)).fetchone()
                if prior is not None:
                    if prior['request_digest'] != request:
                        raise ValueError('Event key reused with different content or metadata')
                    status = self.db.execute('SELECT status FROM revisions WHERE proposition_id=? ORDER BY sequence DESC LIMIT 1', (proposition_id,)).fetchone()[0]
                    return {'observation_id': prior['observation_id'], 'evidence_id': prior['id'], 'status': status}
            active = self.db.execute('SELECT 1 FROM evidence e LEFT JOIN withdrawals w ON w.evidence_id=e.id WHERE e.observation_id=? AND e.proposition_id=? AND w.evidence_id IS NULL LIMIT 1',
                                     (observation_id, proposition_id)).fetchone()
            if active:
                raise ValueError('Observation already has active evidence for this proposition')
            evidence_id = str(uuid4())
            self._insert_link(evidence_id, observation_id, proposition_id, relation, interpretation,
                              source, mass, cluster, actor, reason, event_key, request)
            status = self._revise(proposition_id, now)
        return {'observation_id': observation_id, 'evidence_id': evidence_id, 'status': status}

    @staticmethod
    def _validate_interpretation(interpretation, relation):
        if interpretation is not None:
            from holon.inference.inference import Interpretation
            Interpretation.validate({'relation': interpretation.relation,
                                     'reason': interpretation.reason}, interpretation.model)
            if interpretation.relation != relation:
                raise ValueError('Interpretation does not match evidence relation')

    def _insert_link(self, evidence_id, observation_id, proposition_id, relation, interpretation,
                     source, mass, cluster, actor, reason, event_key, request, migration_id=None):
        self.db.execute('INSERT INTO evidence (id, observation_id, proposition_id, relation) VALUES (?, ?, ?, ?)',
                        (evidence_id, observation_id, proposition_id, relation.value))
        if interpretation is not None:
            self.db.execute('INSERT INTO interpretations (evidence_id, model, reason, prompt_version) VALUES (?, ?, ?, ?)',
                            (evidence_id, interpretation.model, interpretation.reason, interpretation.prompt_version))
        self._impact(evidence_id, proposition_id, source, mass, cluster, actor, reason, event_key, request, migration_id)

    def add_report(self, proposition_id: str, source: str, report: str,
                   relation: str, interpretation=None, *, mass=1.0, event_key=None,
                   cluster_id=None, cluster_actor=None, cluster_reason=None,
                   observed_at=None) -> dict:
        source = required(source, "source")
        required(report, "report")  # Validate without altering the original report.
        relation = Relation(relation)
        self._validate_interpretation(interpretation, relation.value)
        cluster_id, cluster_actor, cluster_reason = self._cluster(source, cluster_id, cluster_actor, cluster_reason)
        mass = ProjectionEvidence('validate', proposition_id, cluster_id, relation, mass).mass
        if event_key is not None:
            event_key = required(event_key, 'event key')
        observed_at = normalize_observed_at(observed_at)
        request = request_digest({'report': report, 'relation': relation.value, 'mass': mass,
                                   'cluster': cluster_id, 'actor': cluster_actor, 'reason': cluster_reason,
                                   'interpretation': asdict(interpretation) if interpretation else None}, observed_at)
        now = datetime.now(timezone.utc).isoformat()
        observation_id, evidence_id = str(uuid4()), str(uuid4())
        with self.db:
            # Serialize read/modify/write across concurrent CLI processes.
            self.db.execute("BEGIN IMMEDIATE")
            if not self.db.execute("SELECT 1 FROM propositions WHERE id = ?",
                                   (proposition_id,)).fetchone():
                raise ValueError(f"Unknown proposition: {proposition_id}")
            if event_key is not None:
                prior = self.db.execute("SELECT m.request_digest, e.id, e.observation_id FROM evidence_impact m JOIN evidence e ON e.id=m.evidence_id WHERE m.proposition_id=? AND m.source=? AND m.event_key=?",
                                        (proposition_id, source, event_key)).fetchone()
                if prior is not None:
                    if prior['request_digest'] != request:
                        raise ValueError('Event key reused with different content or metadata')
                    status = self.db.execute("SELECT status FROM revisions WHERE proposition_id=? ORDER BY sequence DESC LIMIT 1", (proposition_id,)).fetchone()[0]
                    return {'observation_id': prior['observation_id'], 'evidence_id': prior['id'], 'status': status}
            self.db.execute("INSERT INTO observations (id, source, report, recorded_at, observed_at) VALUES (?, ?, ?, ?, ?)",
                            (observation_id, source, report, now, observed_at))
            self._insert_link(evidence_id, observation_id, proposition_id, relation, interpretation,
                              source, mass, cluster_id, cluster_actor, cluster_reason, event_key, request)
            status = self._revise(proposition_id, now)
        return {"observation_id": observation_id, "evidence_id": evidence_id,
                "status": status}

    def _revise(self, proposition_id, now):
        rows = self.db.execute(
            "SELECT e.id, e.relation FROM evidence e "
            "LEFT JOIN withdrawals w ON w.evidence_id = e.id "
            "WHERE e.proposition_id = ? AND w.evidence_id IS NULL ORDER BY e.rowid",
            (proposition_id,)).fetchall()
        status = (belief_status({Relation(r["relation"]) for r in rows}).value
                  if rows else "insufficient_evidence")
        self.db.execute(
            "INSERT INTO revisions (proposition_id, status, evidence_ids, recorded_at, policy) VALUES (?, ?, ?, ?, ?)",
            (proposition_id, status, json.dumps([r["id"] for r in rows]), now, "active-presence-v2"))
        return status

    def evidence_context(self, evidence_id):
        """Read the observation and proposition for an evidence link in one snapshot."""
        with self.db:
            self.db.execute('BEGIN')
            row = self.db.execute(
                'SELECT e.id AS evidence_id, e.relation, e.observation_id, e.proposition_id, '
                'o.source, o.report, o.observed_at, p.claim, p.scope, '
                'w.recorded_at AS withdrawn_at FROM evidence e '
                'JOIN observations o ON o.id=e.observation_id '
                'JOIN propositions p ON p.id=e.proposition_id '
                'LEFT JOIN withdrawals w ON w.evidence_id=e.id WHERE e.id=?',
                (evidence_id,)).fetchone()
            if row is None:
                raise ValueError(f'Unknown evidence: {evidence_id}')
            return dict(row)

    def reinterpret_evidence(self, evidence_id, relation, actor, reason, *, mass=None,
                             event_key=None, interpretation=None):
        """Atomically supersede one link while retaining its observation and provenance."""
        actor, reason = required(actor, 'actor'), required(reason, 'reason')
        relation = Relation(relation)
        self._validate_interpretation(interpretation, relation.value)
        if event_key is not None:
            event_key = required(event_key, 'event key')
        if mass is not None:
            mass = ProjectionEvidence('validate', 'validate', 'validate', relation, mass).mass
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.db.execute(
                'SELECT e.observation_id, e.proposition_id, o.source, m.mass, m.semantics, '
                'm.cluster_id, m.cluster_actor, m.cluster_reason, m.migration_id '
                'FROM evidence e JOIN observations o ON o.id=e.observation_id '
                'LEFT JOIN evidence_impact m ON m.evidence_id=e.id WHERE e.id=?',
                (evidence_id,)).fetchone()
            if old is None:
                raise ValueError(f'Unknown evidence: {evidence_id}')
            request = 'reinterpret-v1:' + digest(canonical({
                'operation': 'reinterpret', 'evidence_id': evidence_id, 'relation': relation.value,
                'actor': actor, 'reason': reason, 'mass_override': mass,
                'interpretation': asdict(interpretation) if interpretation else None}))
            if event_key is not None:
                prior = self.db.execute(
                    'SELECT m.request_digest, e.id, e.observation_id FROM evidence_impact m '
                    'JOIN evidence e ON e.id=m.evidence_id WHERE m.proposition_id=? AND m.source=? AND m.event_key=?',
                    (old['proposition_id'], old['source'], event_key)).fetchone()
                if prior is not None:
                    if prior['request_digest'] != request:
                        raise ValueError('Event key reused with different content or metadata')
                    status = self.db.execute('SELECT status FROM revisions WHERE proposition_id=? ORDER BY sequence DESC LIMIT 1', (old['proposition_id'],)).fetchone()[0]
                    return {'proposition_id': old['proposition_id'], 'observation_id': prior['observation_id'],
                            'withdrawn_evidence_id': evidence_id, 'replacement_evidence_id': prior['id'], 'status': status}
            if self.db.execute('SELECT 1 FROM withdrawals WHERE evidence_id=?', (evidence_id,)).fetchone():
                raise ValueError(f'Evidence already withdrawn: {evidence_id}')
            if old['mass'] is None:
                raise ValueError('Evidence impact metadata is missing; annotate legacy impacts before reinterpretation')
            if old['semantics'] != SEMANTICS or not old['cluster_id']:
                raise ValueError('Evidence impact metadata has unsupported or invalid semantics')
            other = self.db.execute('SELECT 1 FROM evidence e LEFT JOIN withdrawals w ON w.evidence_id=e.id WHERE e.observation_id=? AND e.proposition_id=? AND e.id<>? AND w.evidence_id IS NULL LIMIT 1',
                                    (old['observation_id'], old['proposition_id'], evidence_id)).fetchone()
            if other:
                raise ValueError('Another active evidence link exists for this observation and proposition')
            replacement_id = str(uuid4())
            self._insert_link(replacement_id, old['observation_id'], old['proposition_id'], relation,
                              interpretation, old['source'], old['mass'] if mass is None else mass,
                              old['cluster_id'], old['cluster_actor'], old['cluster_reason'], event_key,
                              request, migration_id=old['migration_id'])
            self.db.execute('INSERT INTO withdrawals (evidence_id, actor, reason, recorded_at, replacement_evidence_id) VALUES (?, ?, ?, ?, ?)',
                            (evidence_id, actor, reason, now, replacement_id))
            status = self._revise(old['proposition_id'], now)
        return {'proposition_id': old['proposition_id'], 'observation_id': old['observation_id'],
                'withdrawn_evidence_id': evidence_id, 'replacement_evidence_id': replacement_id, 'status': status}

    def withdraw_evidence(self, evidence_id, actor, reason, *, report=None,
                          source=None, relation=None, mass=1.0, event_key=None, observed_at=None):
        """Withdraw a link; optionally replace it atomically with a corrected report.

        Withdrawal concerns this evidence link, not every use of its observation.
        The actor is caller-supplied attribution, not authenticated identity.
        """
        actor, reason = required(actor, "actor"), required(reason, "reason")
        correcting = report is not None
        observed_at = normalize_observed_at(observed_at)
        if correcting:
            required(report, "report")
            source = required(source, "source")
            relation = Relation(relation).value
            mass = ProjectionEvidence("validate", "validate", "validate", relation, mass).mass
        elif source is not None or relation is not None or observed_at is not None:
            raise ValueError("A correction requires a report")
        if event_key is not None:
            if not correcting:
                raise ValueError('Event key requires a correction')
            event_key = required(event_key, 'event key')
        request = request_digest({'corrects': evidence_id, 'actor': actor, 'reason': reason,
                                   'report': report, 'source': source, 'relation': relation, 'mass': mass}, observed_at) if correcting else None
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT e.proposition_id, o.source FROM evidence e JOIN observations o ON o.id=e.observation_id WHERE e.id = ?",
                                  (evidence_id,)).fetchone()
            if old is None:
                raise ValueError(f"Unknown evidence: {evidence_id}")
            if event_key is not None:
                prior = self.db.execute("SELECT m.request_digest, e.id, e.observation_id FROM evidence_impact m JOIN evidence e ON e.id=m.evidence_id WHERE m.proposition_id=? AND m.source=? AND m.event_key=?",
                                        (old['proposition_id'], source, event_key)).fetchone()
                if prior is not None:
                    if prior['request_digest'] != request:
                        raise ValueError('Event key reused with different content or metadata')
                    status = self.db.execute('SELECT status FROM revisions WHERE proposition_id=? ORDER BY sequence DESC LIMIT 1', (old['proposition_id'],)).fetchone()[0]
                    return {'proposition_id': old['proposition_id'], 'withdrawn_evidence_id': evidence_id,
                            'replacement_evidence_id': prior['id'], 'observation_id': prior['observation_id'], 'status': status}
            if self.db.execute("SELECT 1 FROM withdrawals WHERE evidence_id = ?",
                               (evidence_id,)).fetchone():
                raise ValueError(f"Evidence already withdrawn: {evidence_id}")
            replacement_id = None
            observation_id = None
            if correcting:
                observation_id, replacement_id = str(uuid4()), str(uuid4())
                self.db.execute("INSERT INTO observations (id, source, report, recorded_at, observed_at) VALUES (?, ?, ?, ?, ?)",
                                (observation_id, source, report, now, observed_at))
                self.db.execute("INSERT INTO evidence (id, observation_id, proposition_id, relation) VALUES (?, ?, ?, ?)",
                                (replacement_id, observation_id, old["proposition_id"], relation))
                lineage = self.db.execute('SELECT cluster_id FROM evidence_impact WHERE evidence_id=?', (evidence_id,)).fetchone()
                self._impact(replacement_id, old['proposition_id'], source, mass,
                             lineage['cluster_id'] if lineage else source_cluster(old['source']),
                             actor, 'Correction retains original lineage: ' + reason, event_key, request)
            self.db.execute("INSERT INTO withdrawals (evidence_id, actor, reason, recorded_at, replacement_evidence_id) VALUES (?, ?, ?, ?, ?)",
                            (evidence_id, actor, reason, now, replacement_id))
            status = self._revise(old["proposition_id"], now)
        return {"proposition_id": old["proposition_id"], "withdrawn_evidence_id": evidence_id,
                "replacement_evidence_id": replacement_id,
                "observation_id": observation_id, "status": status}

    def inspect(self, proposition_id: str, *, projection_policy=None) -> dict:
        # One snapshot for a consistent inspection during concurrent writes.
        with self.db:
            self.db.execute("BEGIN")
            row = self.db.execute("SELECT * FROM propositions WHERE id = ?",
                                  (proposition_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown proposition: {proposition_id}")
            evidence = [dict(r) for r in self.db.execute(
                "SELECT e.id, e.relation, o.id AS observation_id, o.source, o.report, o.recorded_at, o.observed_at, i.model, i.reason, i.prompt_version, "
                "w.actor AS withdrawal_actor, w.reason AS withdrawal_reason, "
                "w.recorded_at AS withdrawn_at, w.replacement_evidence_id "
                "FROM evidence e JOIN observations o ON o.id = e.observation_id "
                "LEFT JOIN interpretations i ON i.evidence_id = e.id "
                "LEFT JOIN withdrawals w ON w.evidence_id = e.id "
                "WHERE e.proposition_id = ? ORDER BY e.rowid", (proposition_id,))]
            for item in evidence:
                item["active"] = item["withdrawn_at"] is None
            history = [dict(r) for r in self.db.execute(
                "SELECT sequence, status, evidence_ids, recorded_at, policy FROM revisions "
                "WHERE proposition_id = ? ORDER BY sequence", (proposition_id,))]
            for revision in history:
                revision["evidence_ids"] = json.loads(revision["evidence_ids"])
            result = {"proposition": dict(row),
                    "status": history[-1]["status"] if history else "insufficient_evidence",
                    "evidence": evidence, "history": history}
            if projection_policy is not None:
                result['projection'] = self._project(proposition_id, projection_policy)
            return result

    @staticmethod
    def _cluster(source, cluster_id, actor, reason):
        if cluster_id is None:
            if actor is not None or reason is not None:
                raise ValueError('Cluster attribution requires an explicit cluster ID')
            return source_cluster(source), None, None
        return ('shared:' + required(cluster_id, 'cluster ID'),
                required(actor or '', 'cluster actor'), required(reason or '', 'cluster reason'))

    def _impact(self, eid, pid, source, mass, cluster, actor=None, reason=None,
                event_key=None, request=None, migration_id=None):
        self.db.execute("INSERT INTO evidence_impact (evidence_id, proposition_id, source, mass, semantics, cluster_id, cluster_actor, cluster_reason, event_key, request_digest, migration_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (eid, pid, source, mass, SEMANTICS, cluster, actor, reason, event_key, request, migration_id))

    def project(self, proposition_id, policy='binary-beta-v1'):
        with self.db:
            self.db.execute('BEGIN')
            return self._project(proposition_id, policy)

    def _project(self, proposition_id, policy_id):
        if not self.db.execute('SELECT 1 FROM propositions WHERE id=?', (proposition_id,)).fetchone():
            raise ValueError(f'Unknown proposition: {proposition_id}')
        stored = self.db.execute('SELECT * FROM projection_policies WHERE id=?', (policy_id,)).fetchone()
        if stored is None:
            raise ValueError(f'Unknown projection policy: {policy_id}')
        if digest(stored['payload']) != stored['digest']:
            raise ValueError('Projection policy digest mismatch')
        payload = json.loads(stored['payload'])
        if payload['dynamics_version'] != DYNAMICS_VERSION or payload['mass_semantics'] != SEMANTICS or payload['decay_rate'] != 0:
            raise ValueError('Unsupported projection semantics')
        rows = [dict(row) for row in self.db.execute(
            "SELECT e.id, e.relation, o.source, o.report, o.recorded_at, w.recorded_at AS withdrawn_at, w.actor, w.reason, w.replacement_evidence_id, m.mass, m.semantics, m.cluster_id, m.cluster_actor, m.cluster_reason, m.event_key, m.migration_id FROM evidence e JOIN observations o ON o.id=e.observation_id LEFT JOIN withdrawals w ON w.evidence_id=e.id LEFT JOIN evidence_impact m ON m.evidence_id=e.id WHERE e.proposition_id=? ORDER BY e.id", (proposition_id,))]
        missing = [r['id'] for r in rows if r['mass'] is None or r['semantics'] != SEMANTICS]
        coverage = ('replay_incomplete' if missing else
                    'replay_approximate' if any(r['migration_id'] for r in rows) else 'replay_complete')
        result = {'proposition_id': proposition_id, 'replay_coverage': coverage,
                  'policy_id': policy_id, 'policy_digest': stored['digest'],
                  'dynamics_version': DYNAMICS_VERSION, 'ledger_digest': digest(canonical(rows)),
                  'missing_metadata_ids': missing, 'evidence_metadata': rows, 'readout': None}
        # Never display a partial numeric result as a complete projection.
        if not missing:
            records = [ProjectionEvidence(r['id'], proposition_id, r['cluster_id'], r['relation'],
                                          r['mass'], r['withdrawn_at'] is None) for r in rows]
            result['readout'] = asdict(project_binary(proposition_id, records, ProjectionPolicy(**payload['policy'])))
        return result

    def migrate_impacts(self, proposition_id, actor, reason):
        actor, reason = required(actor, 'actor'), required(reason, 'reason')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if not self.db.execute('SELECT 1 FROM propositions WHERE id=?', (proposition_id,)).fetchone():
                raise ValueError(f'Unknown proposition: {proposition_id}')
            rows = self.db.execute("SELECT e.id, o.source FROM evidence e JOIN observations o ON o.id=e.observation_id LEFT JOIN evidence_impact m ON m.evidence_id=e.id WHERE e.proposition_id=? AND m.evidence_id IS NULL", (proposition_id,)).fetchall()
            migration_id = None
            if rows:
                migration_id = str(uuid4())
                self.db.execute('INSERT INTO impact_migrations (id, actor, reason, recorded_at, assumptions) VALUES (?, ?, ?, ?, ?)',
                                (migration_id, actor, reason, datetime.now(timezone.utc).isoformat(),
                                 'Unit stipulated impact; source-string clusters; no inferred time or reliability'))
                for row in rows:
                    self._impact(row['id'], proposition_id, row['source'], 1.0,
                                 source_cluster(row['source']), actor, reason, migration_id=migration_id)
            return {'migration_id': migration_id, 'annotated_count': len(rows)}
