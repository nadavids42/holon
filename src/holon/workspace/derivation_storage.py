"""Schema-3 persistence boundary shared by standalone stores and Workspace.

Every write validates under BEGIN IMMEDIATE. Lineage is observation membership
in asserted origin groups, independent of legacy evidence-impact clusters.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json

from holon.domain.derivation import DerivationGraph, Justification, SignedClaim, CONTRACT_VERSION, _identifier, _text
from holon.workspace.metadata import canonical, digest

SCHEMA = '''
CREATE TABLE derivation_justifications (
    id TEXT PRIMARY KEY,
    conclusion_id TEXT NOT NULL REFERENCES propositions(id),
    conclusion_relation TEXT NOT NULL CHECK(conclusion_relation IN ('supports','contradicts')),
    premises_json TEXT NOT NULL,
    rule TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK(contract_version='derivation-v1')
);
CREATE TABLE lineage_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN ('assign','merge','reverse')),
    target_event_id TEXT REFERENCES lineage_events(id),
    request_json TEXT NOT NULL,
    changes_json TEXT NOT NULL,
    actor TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK(contract_version='origin-lineage-v1'),
    CHECK((kind='reverse' AND target_event_id IS NOT NULL) OR
          (kind<>'reverse' AND target_event_id IS NULL))
);
'''


def migrate(db):
    """Called within the storage opener's single migration transaction."""
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)
    for table in ('derivation_justifications', 'lineage_events'):
        for operation in ('UPDATE', 'DELETE'):
            db.execute(f"CREATE TRIGGER immutable_{table}_{operation} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable derivation/lineage history'); END")


def _now():
    return datetime.now(timezone.utc).isoformat()


class LineageConflict(ValueError):
    """A valid lineage request conflicts with the current history."""


def replay_lineage(events, observation_ids):
    """Reconstruct assignments and validate history; no origin is inferred."""
    assignments = {oid: None for oid in sorted(observation_ids)}
    heads = dict(assignments)
    seen, reversed_ids = {}, set()
    last = 0
    for event in events:
        if event['sequence'] <= last or event['id'] in seen:
            raise ValueError('Invalid lineage event ordering or identity')
        last = event['sequence']
        if event['contract_version'] != 'origin-lineage-v1':
            raise ValueError('Unsupported lineage contract')
        changes = event['changes']
        if not changes or len({c['observation_id'] for c in changes}) != len(changes):
            raise ValueError('Empty or duplicate lineage membership changes')
        kind, target = event['kind'], event['target_event_id']
        if kind not in ('assign', 'merge', 'reverse') or (kind == 'reverse') != (target is not None):
            raise ValueError('Invalid lineage event kind/target')
        if kind == 'reverse':
            if target not in seen or seen[target]['kind'] == 'reverse' or target in reversed_ids:
                raise LineageConflict('Invalid or already reversed target')
            original = seen[target]['changes']
            expected = [dict(observation_id=c['observation_id'], before=c['after'], after=c['before'],
                             previous_event_id=target, restored_event_id=c['previous_event_id']) for c in original]
            if changes != expected:
                raise ValueError('Reversal does not restore the target event')
        for change in changes:
            oid = change['observation_id']
            if oid not in assignments:
                raise ValueError('Unknown observation in lineage history')
            for value in (change['before'], change['after']):
                if value is not None:
                    _identifier(value, 'origin group')
            if assignments[oid] != change['before'] or heads[oid] != change['previous_event_id']:
                raise LineageConflict('Lineage history precondition failed; later dependent changes must be reversed first')
            assignments[oid] = change['after']
            heads[oid] = change['restored_event_id'] if kind == 'reverse' else event['id']
        if kind == 'reverse':
            reversed_ids.add(target)
        seen[event['id']] = event
    return {'assignments': assignments, 'heads': heads, 'revision': last,
            'events': events, 'contract_version': 'origin-lineage-v1',
            'digest': 'lineage-ledger-v1:' + digest(canonical(events)),
            'provenance_completeness': 'unknown'}


class DerivationStore:
    """Own a connection or borrow Workspace ownership; never share across threads."""
    def __init__(self, path):
        from holon.workspace.storage import connect
        self.db = connect(path)
        self._workspace = None

    @classmethod
    def for_workspace(cls, workspace):
        """Borrow its connection and transaction owner; never close the owner."""
        store = cls.__new__(cls)
        store.db = workspace.db
        store._workspace = workspace
        return store

    def close(self):
        if self._workspace is None:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @contextmanager
    def _transaction(self, write=False):
        if self._workspace is not None:
            with self._workspace.atomic(write=write):
                yield
            return
        if self.db.in_transaction:
            raise ValueError('DerivationStore requires an operation-scoped transaction')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield

    def _records(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM derivation_justifications ORDER BY id')]

    def _graph(self):
        js = []
        for row in self._records():
            if row['contract_version'] != CONTRACT_VERSION:
                raise ValueError('Unsupported derivation contract')
            js.append(Justification(row['id'], SignedClaim(row['conclusion_id'], row['conclusion_relation']),
                tuple(SignedClaim(**p) for p in json.loads(row['premises_json'])), row['rule'], row['actor'], row['reason']))
        return DerivationGraph(frozenset(r[0] for r in self.db.execute('SELECT id FROM propositions')), tuple(js))

    def graph(self):
        with self._transaction():
            return self._graph()

    def inspect_derivations(self):
        with self._transaction():
            graph = self._graph()
            records = self._records()
            return {'records': records, 'topological_order': graph.topological_order(),
                    'contract_version': CONTRACT_VERSION,
                    'digest': 'derivation-ledger-v1:' + digest(canonical(records))}

    def add_justification(self, justification):
        if not isinstance(justification, Justification):
            raise ValueError('Expected a Justification')
        with self._transaction(write=True):
            graph = self._graph()
            prior = next((j for j in graph.justifications if j.id == justification.id), None)
            if prior is not None:
                if prior != justification:
                    raise ValueError('Justification ID reused with different content')
                return justification.id
            graph.with_justification(justification)
            self.db.execute('INSERT INTO derivation_justifications VALUES (?,?,?,?,?,?,?,?,?)',
                (justification.id, justification.conclusion.proposition_id, justification.conclusion.relation.value,
                 canonical([asdict(p) for p in justification.premises]), justification.rule,
                 justification.actor, justification.reason, _now(), CONTRACT_VERSION))
        return justification.id

    def _lineage(self):
        events = []
        for row in self.db.execute('SELECT * FROM lineage_events ORDER BY sequence'):
            item = dict(row)
            item['changes'] = json.loads(item.pop('changes_json'))
            events.append(item)
        return replay_lineage(events, [r[0] for r in self.db.execute('SELECT id FROM observations')])

    def lineage(self):
        with self._transaction():
            return self._lineage()

    def assign_origin(self, event_id, observation_id, group_id, actor, reason, *, expected_revision):
        """Assign/reassign one observation; None explicitly restores unknown origin."""
        _identifier(observation_id, 'observation id')
        if group_id is not None:
            _identifier(group_id, 'origin group')
        return self._append(event_id, 'assign', {'observation_id': observation_id, 'group_id': group_id},
                            actor, reason, expected_revision)

    def merge_origins(self, event_id, group_ids, target_group_id, actor, reason, *, expected_revision):
        if not isinstance(group_ids, (list, tuple, set, frozenset)):
            raise ValueError('group_ids must be a collection')
        for group in group_ids:
            _identifier(group, 'origin group')
        _identifier(target_group_id, 'target origin group')
        if len(set(group_ids)) != len(group_ids) or len(group_ids) < 2 or target_group_id not in group_ids:
            raise ValueError('Merge requires at least two distinct groups including its target')
        return self._append(event_id, 'merge', {'group_ids': sorted(group_ids), 'target_group_id': target_group_id},
                            actor, reason, expected_revision)

    def reverse_lineage(self, event_id, target_event_id, actor, reason, *, expected_revision):
        _identifier(target_event_id, 'target event id')
        return self._append(event_id, 'reverse', {'target_event_id': target_event_id}, actor, reason, expected_revision)

    def _append(self, event_id, kind, arguments, actor, reason, revision):
        _identifier(event_id, 'event id')
        _text(actor, 'actor'); _text(reason, 'reason')
        if type(revision) is not int or revision < 0:
            raise ValueError('expected_revision must be a nonnegative integer')
        request = canonical(dict(kind=kind, arguments=arguments, actor=actor, reason=reason, expected_revision=revision))
        with self._transaction(write=True):
            prior = self.db.execute('SELECT request_json FROM lineage_events WHERE id=?', (event_id,)).fetchone()
            if prior:
                if prior['request_json'] != request:
                    raise LineageConflict('Lineage event ID reused with different content')
                return event_id
            state = self._lineage()
            if revision != state['revision']:
                raise LineageConflict('Stale lineage revision; reload before editing')
            assignments, heads = state['assignments'], state['heads']
            target = None
            if kind == 'assign':
                oid, group = arguments['observation_id'], arguments['group_id']
                if oid not in assignments:
                    raise ValueError('Unknown observation')
                if assignments[oid] == group:
                    raise ValueError('Origin assignment would not change')
                changes = [dict(observation_id=oid, before=assignments[oid], after=group, previous_event_id=heads[oid])]
            elif kind == 'merge':
                groups, group = arguments['group_ids'], arguments['target_group_id']
                if any(g not in assignments.values() for g in groups):
                    raise ValueError('Cannot merge an empty or unknown group')
                # Record target members too: later changes to any member block reversal.
                changes = [dict(observation_id=o, before=g, after=group, previous_event_id=heads[o])
                           for o, g in sorted(assignments.items()) if g in groups]
            else:
                target = arguments['target_event_id']
                original = next((e for e in state['events'] if e['id'] == target), None)
                if original is None or original['kind'] == 'reverse':
                    raise ValueError('Target must be an existing assignment or merge')
                changes = [dict(observation_id=c['observation_id'], before=c['after'], after=c['before'],
                                previous_event_id=target, restored_event_id=c['previous_event_id']) for c in original['changes']]
            event = dict(sequence=state['revision'] + 1, id=event_id, kind=kind, target_event_id=target,
                         request_json=request, changes=changes, actor=actor, reason=reason,
                         recorded_at=_now(), contract_version='origin-lineage-v1')
            replay_lineage([*state['events'], event], assignments)
            self.db.execute('''INSERT INTO lineage_events
                (id,kind,target_event_id,request_json,changes_json,actor,reason,recorded_at,contract_version)
                VALUES (?,?,?,?,?,?,?,?,?)''', (event_id, kind, target, request, canonical(changes), actor, reason,
                                              event['recorded_at'], 'origin-lineage-v1'))
        return event_id
