"""Experiment-only mechanism classes; H0 calls the unchanged Workspace service."""
from copy import deepcopy
import json
import re
from pathlib import Path

from .actor import requirements
from .schema import canonical, digest, require

METHOD_VERSION = 'structured-baselines-v1'
METHODS = ('H0', 'LWW', 'RR', 'RB')


class BudgetExceeded(Exception):
    pass


class Meter:
    """Logical operations, not estimated tokens or physical database page writes."""
    def __init__(self, counters=None, limit=100000):
        self.counters = deepcopy(counters or {})
        self.limit = limit

    def add(self, phase, name, amount=1):
        bucket = self.counters.setdefault(phase, {})
        bucket[name] = bucket.get(name, 0) + amount
        if name in ('records_visited', 'rule_evaluations', 'source_reads', 'logical_writes'):
            used = sum(sum(v.get(k, 0) for k in ('records_visited', 'rule_evaluations', 'source_reads', 'logical_writes'))
                       for v in self.counters.values())
            if used > self.limit:
                raise BudgetExceeded()

    def read(self, source, phase):
        self.add(phase, 'source_reads')
        self.add(phase, 'source_bytes', len(canonical(source).encode()))


def fact(key, value, citations):
    return dict(key=key, value=value, citations=citations, status='supported')


def refs(source):
    """Declared links plus literal public fragment references, no inferred hidden edges."""
    return set(d['parent'] for d in source['dependencies']) | set(re.findall(
        r'\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b', source['text']))


class Method:
    def __init__(self, name, state, directory, meter):
        require(name in METHODS, 'Unknown method')
        self.name, self.state, self.directory, self.meter = name, state, Path(directory), meter
        self.ws = None
        if name == 'H0':
            from holon.workspace.service import Workspace
            self.ws = Workspace(self.directory / 'holon.sqlite')

    def close(self):
        if self.ws:
            self.ws.close()

    def ingest(self, view):
        state = self.state
        require(state['episode_id'] == view['episode_id'], 'State belongs to another episode')
        context = digest([view['project_id'], view['rules']])
        require(state['context_digest'] in (None, context), 'Changed public context')
        state['context_digest'] = context
        prefix = view['events']
        old = state['event_hashes']
        require(len(prefix) >= len(old) and [digest(e) for e in prefix[:len(old)]] == old,
                'Changed or truncated public prefix')
        for event in prefix[len(old):]:
            self.meter.add('ingestion', 'records_visited')
            if event['kind'] == 'source':
                source = deepcopy(event['payload'])
                self.meter.read(source, 'ingestion')
                state['sources'].append(source)
                self.meter.add('ingestion', 'logical_writes')
                if self.ws:
                    self._holon_ingest(source, view['project_id'])
                elif self.name == 'LWW':
                    self._lww_ingest(source)
            old.append(digest(event))

    def _holon_ingest(self, source, project):
        state, meter = self.state, self.meter
        update = source['update']
        keys = {s['key'] for s in source['statements']}
        if update and update['kind'] in ('source_correction', 'withdrawal'):
            # Only explicitly targeted links; no dependency walk or source-wide revoke.
            for link in state['links']:
                meter.add('maintenance', 'records_visited')
                if link['source'] in update['targets'] and link['active'] and (
                        update['kind'] == 'withdrawal' or link['key'] in keys):
                    self.ws.withdraw_evidence(link['evidence'], 'experiment-H0', 'Explicit public update')
                    link['active'] = False
                    meter.add('maintenance', 'logical_writes')
        oid = self.ws.record_observation(source['source_id'], source['text'], observed_at=source['observed_at'])
        meter.add('ingestion', 'logical_writes')
        for statement in source['statements']:
            meter.add('ingestion', 'records_visited')
            key = canonical([statement['key'], statement['value'], source['subject_time']])
            if key not in state['propositions']:
                state['propositions'][key] = self.ws.create_proposition(
                    canonical(statement), canonical([project, source['subject_time']]))
                meter.add('ingestion', 'logical_writes')
            linked = self.ws.link_observation(oid, state['propositions'][key], 'supports',
                                              event_key=source['id'] + ':' + statement['key'])
            state['links'].append(dict(source=source['id'], key=statement['key'],
                                       evidence=linked['evidence_id'], active=True))
            meter.add('ingestion', 'logical_writes')

    def claims(self, task=None, audit_keys=None, subject_time=None):
        kind, needed, target = requirements(task) if task else ('audit', set(audit_keys), None)
        when = task['subject_time'] if task else subject_time
        sources = self.state['sources']
        if kind == 'lookup':
            for source in sources:
                self.meter.add('retrieval', 'records_visited')
                if source['id'] == target:
                    self.meter.read(source, 'retrieval')
                    return [fact('reported_release', s['value'], [target]) for s in source['statements']
                            if s['key'] == 'release_date']
            return []
        if self.name == 'H0':
            return self._holon_claims(needed, when)
        if self.name == 'LWW':
            result = []
            for encoded, row in self.state['facts'].items():
                self.meter.add('retrieval', 'records_visited')
                key, scope = json.loads(encoded)
                if key in needed and scope <= when:
                    result.append(deepcopy(row))
            return result
        if self.name == 'RR':
            selected = self._retrieve(needed)
        else:
            selected = sources
        for source in selected:
            self.meter.read(source, 'retrieval')
        return self._rebuild(selected, needed, when)

    def _holon_claims(self, needed, when):
        result = []
        # No temporal adjudication grafted onto H0: world changes are unsupported.
        blocked = set()
        for source in self.state['sources']:
            self.meter.add('retrieval', 'records_visited')
            if source['update'] and source['update']['kind'] == 'world_change':
                blocked.update(s['key'] for s in source['statements'])
        by_evidence = {link['evidence']: link['source'] for link in self.state['links']}
        for encoded, pid in self.state['propositions'].items():
            self.meter.add('retrieval', 'records_visited')
            key, value, scope = json.loads(encoded)
            if key not in needed or key in blocked or scope > when:
                continue
            snapshot = self.ws.inspect(pid, projection_policy='binary-beta-v1')
            self.meter.add('retrieval', 'workspace_inspections')
            self.meter.add('retrieval', 'records_visited', len(snapshot['evidence']) + len(snapshot['history']))
            # Export native status and projection diagnostically; means never pick a value.
            self.state['diagnostics'][encoded] = snapshot
            if snapshot['status'] == 'supported':
                for evidence in snapshot['evidence']:
                    if evidence['active'] and evidence['relation'] == 'supports':
                        result.append(fact(key, value, [by_evidence[evidence['id']]]))
        return result

    def _retrieve(self, needed):
        sources = self.state['sources']
        chosen = set()
        # Deterministic metadata/normalized-key filter; lexical references expand closure.
        for source in sources:
            self.meter.add('retrieval', 'records_visited')
            if any(s['key'] in needed for s in source['statements']):
                chosen.add(source['id'])
        changed = True
        while changed:
            changed = False
            for source in sources:
                self.meter.add('retrieval', 'records_visited')
                self.meter.read(source, 'retrieval')
                links = refs(source) | set((source['update'] or {}).get('targets', []))
                if source['id'] in chosen or links & chosen:
                    expanded = chosen | links | {source['id']}
                    changed |= expanded != chosen
                    chosen = expanded
        return [s for s in sources if s['id'] in chosen]

    def _lww_ingest(self, source):
        scoped = self.state['facts']
        update = source['update']
        if update and update['kind'] in ('withdrawal', 'source_correction'):
            updated = {s['key'] for s in source['statements']}
            for encoded, row in list(scoped.items()):
                self.meter.add('maintenance', 'records_visited')
                if row['citations'][0] in update['targets'] and (
                        update['kind'] == 'withdrawal' or row['key'] in updated):
                    del scoped[encoded]
                    self.meter.add('maintenance', 'logical_writes')
        for statement in source['statements']:
            self.meter.add('maintenance', 'rule_evaluations')
            scoped[canonical([statement['key'], source['subject_time']])] = fact(
                statement['key'], statement['value'], [source['id']])
            self.meter.add('maintenance', 'logical_writes')

    def _rebuild(self, sources, needed, when):
        """Fresh query-local reconstruction, never a persistent derivation graph."""
        rows, invalid, parents, history_proof = [], set(), {}, {}
        by_id = {s['id']: s for s in sources}
        for source in sources:
            self.meter.add('maintenance', 'records_visited')
            sid, update = source['id'], source['update']
            parents[sid] = refs(source) - {sid}
            if update:
                parents[sid] = set()  # References in an intervention identify targets, not premises.
                changed_keys = {s['key'] for s in source['statements']}
                if update['kind'] == 'lineage_correction':
                    for target in update['targets']:
                        parents[target] = set()
                for target in update['targets']:
                    self.meter.add('maintenance', 'rule_evaluations')
                    if update['kind'] == 'withdrawal':
                        invalid.update((target, s['key']) for s in by_id[target]['statements'])
                    elif update['kind'] == 'source_correction' or (update['kind'] == 'world_change' and when >= update['effective_at']):
                        invalid.update((target, key) for key in changed_keys)
                    elif update['kind'] == 'world_change':
                        for key in changed_keys:
                            history_proof[target, key] = sid
            if source['subject_time'] <= when:
                for statement in source['statements']:
                    rows.append((sid, statement['key'], statement['value']))
                    self.meter.add('maintenance', 'logical_writes')
        def usable(sid, key, visiting):
            self.meter.add('maintenance', 'rule_evaluations')
            if (sid, key) in invalid or sid in visiting or sid not in by_id:
                return False
            for parent in parents.get(sid, ()):
                parent_keys = {s['key'] for s in by_id[parent]['statements']} if parent in by_id else set()
                # Copies depend on matching statements; derivations on their declared premises.
                checks = {key} if key in parent_keys else parent_keys
                if not checks or not all(usable(parent, k, visiting | {sid}) for k in checks):
                    return False
            return True
        output = []
        for sid, key, value in rows:
            if key in needed and usable(sid, key, set()):
                cites = [sid]
                if (sid, key) in history_proof:
                    cites.append(history_proof[sid, key])
                output.append(fact(key, value, cites))
        return output


def initial_state(name, episode_id):
    return dict(version=METHOD_VERSION, method=name, episode_id=episode_id, event_hashes=[], sources=[],
                context_digest=None, propositions={}, links=[], facts={}, diagnostics={}, counters={}, exhausted=False)
