"""Track S actor v1: consume claims, never search sources or repair state."""
from datetime import date, timedelta
import re

ACTOR_VERSION = 'structured-actor-v1'


def requirements(task):
    """Fixed finite vocabulary; unknown task forms abstain (no option guessing)."""
    query = task['query']
    match = re.fullmatch(r'Which release date is stated in fragment ([\w-]+)\? This is a report-content lookup\.', query)
    if match:
        return 'lookup', {'release_date'}, match[1]
    if query.startswith('Who is assigned to preparation'):
        return 'owner', {'owner'}, None
    if query in ('On the current schedule, when must preparation occur?',
                 'After the delayed report, when must preparation occur on the current schedule?'):
        return 'prepare', {'release_date'}, None
    if query == 'Is preparation ready to be assigned (owner AND at least one valid approval)?':
        return 'ready', {'owner', 'approval'}, None
    if re.fullmatch(r'What release date actually applied at subject time \d{4}-\d{2}-\d{2}, using everything now known\?', query):
        return 'release', {'release_date'}, None
    return 'unknown', set(), None


def resolve(claims, key, meter):
    candidates = []
    for claim in claims:
        meter.add('actor', 'records_visited')
        if claim['key'] == key and claim['status'] == 'supported':
            candidates.append(claim)
    meter.add('actor', 'rule_evaluations')
    if len({c['value'] for c in candidates}) != 1:
        return None
    # Earliest adapter claim supplies one sufficient proof; never cite everything.
    return candidates[0] if candidates else None


def decide(task, claims, meter):
    kind, _, _ = requirements(task)
    response = dict(task_id=task['id'], decision='abstain', citations=[])
    key = {'lookup': 'reported_release', 'owner': 'owner', 'prepare': 'release_date',
           'release': 'release_date', 'ready': 'owner'}.get(kind)
    if key is None:
        return response
    first = resolve(claims, key, meter)
    if first is None:
        return response
    citations = first['citations'][:]
    if kind == 'prepare':
        decision = 'prepare_on:' + (date.fromisoformat(first['value']) - timedelta(days=1)).isoformat()
    elif kind == 'ready':
        approval = resolve(claims, 'approval', meter)
        if approval is None or approval['value'] != 'yes':
            return response
        citations += approval['citations']
        decision = 'ready:yes'
    else:
        decision = {'lookup': 'reported_release:', 'owner': 'owner:', 'release': 'release_on:'}[kind] + first['value']
    if decision in task['options']:
        response.update(decision=decision, citations=list(dict.fromkeys(citations)))
    return response


def audit(queries, claims, meter):
    answers = []
    for query in queries:
        claim = resolve(claims, query['key'], meter)
        answers.append(dict(**query, stance=('assert' if claim['value'] == query['value'] else 'deny')
                            if claim else 'unresolved', citations=claim['citations'][:] if claim else []))
    return answers
