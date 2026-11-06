"""Strict JSON contracts shared by trusted replay and offline scoring."""
import hashlib
import json
from datetime import date, datetime, timedelta

VERSION = 'revision-world-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()),
            f'Expected fields: {expected}')


def text(value):
    require(isinstance(value, str) and bool(value.strip()), 'Expected nonempty text')


def unique_strings(values):
    require(isinstance(values, list), 'Expected a list')
    for value in values:
        text(value)
    require(len(values) == len(set(values)), 'Duplicate reference or option')


def day(value):
    text(value)
    require(date.fromisoformat(value).isoformat() == value, 'Expected ISO calendar date')


def instant(value):
    text(value)
    parsed = datetime.fromisoformat(value)
    require(parsed.utcoffset() is not None, 'Timestamp needs a UTC offset')


def validate_history(history):
    require(isinstance(history, list) and history, 'Missing truth intervals')
    for i, interval in enumerate(history):
        keys(interval, 'start end value')
        day(interval['start'])
        text(interval['value'])
        if interval['end'] is not None:
            day(interval['end'])
            require(interval['end'] > interval['start'], 'Empty truth interval')
        if i:
            require(history[i - 1]['end'] == interval['start'], 'Truth intervals overlap or have a gap')
    require(history[-1]['end'] is None, 'Last truth interval must remain open')


def value_at(history, subject):
    values = [i['value'] for i in history if i['start'] <= subject
              and (i['end'] is None or subject < i['end'])]
    require(len(values) == 1, 'No unique physical truth at task time')
    return values[0]


def validate_public(public):
    keys(public, 'schema_version episode_id project_id rules events audit_queries')
    require(public['schema_version'] == VERSION, 'Unsupported public schema')
    text(public['episode_id'])
    text(public['project_id'])
    unique_strings(public['rules'])
    require(isinstance(public['events'], list), 'Expected events')
    seen, sources, tasks = set(), {}, []
    restarts = []
    for index, event in enumerate(public['events']):
        keys(event, 'index id kind payload')
        require(type(event['index']) is int and event['index'] == index, 'Non-contiguous event index')
        text(event['id'])
        require(event['id'] not in seen, 'Duplicate event ID')
        seen.add(event['id'])
        payload = event['payload']
        if event['kind'] == 'source':
            keys(payload, 'id source_id version recorded_at observed_at subject_time statements text dependencies update')
            for field in ('id', 'source_id', 'version', 'recorded_at', 'subject_time', 'text'):
                text(payload[field])
            instant(payload['recorded_at'])
            day(payload['subject_time'])
            if payload['observed_at'] is not None:
                instant(payload['observed_at'])
            require(payload['id'] not in sources, 'Duplicate fragment ID')
            require(isinstance(payload['statements'], list) and payload['statements'], 'Missing statements')
            for statement in payload['statements']:
                keys(statement, 'key value')
                text(statement['key'])
                text(statement['value'])
            require(isinstance(payload['dependencies'], list), 'Missing dependency declarations')
            edges = set()
            for edge in payload['dependencies']:
                keys(edge, 'parent kind')
                require(edge['parent'] in sources, 'Dependency is future, missing, or cyclic')
                require(edge['kind'] in ('copy', 'premise'), 'Unknown dependency kind')
                pair = (edge['parent'], edge['kind'])
                require(pair not in edges, 'Duplicate dependency')
                edges.add(pair)
            update = payload['update']
            if update is not None:
                keys(update, 'kind targets effective_at')
                require(update['kind'] in ('source_correction', 'world_change', 'withdrawal', 'lineage_correction'),
                        'Unsupported update kind')
                unique_strings(update['targets'])
                require(update['targets'] and all(t in sources for t in update['targets']), 'Invalid update targets')
                if update['effective_at'] is not None:
                    day(update['effective_at'])
                require(update['kind'] != 'world_change' or update['effective_at'] is not None,
                        'World change needs an effective time')
            sources[payload['id']] = index
        elif event['kind'] == 'task':
            keys(payload, 'id query subject_time options')
            for field in ('id', 'query', 'subject_time'):
                text(payload[field])
            day(payload['subject_time'])
            require(payload['id'] not in {t['id'] for t in tasks}, 'Duplicate task ID')
            unique_strings(payload['options'])
            require('abstain' in payload['options'] and len(payload['options']) > 1, 'Missing task choices')
            tasks.append(payload)
        elif event['kind'] == 'restart':
            keys(payload, '')
            restarts.append(len(tasks))
        else:
            raise ValueError('Unknown event kind')
    require(len(tasks) == 6 and restarts == [4], 'Expected six tasks and restart after task four')
    require(isinstance(public['audit_queries'], list), 'Expected audit queries')
    require(len(public['audit_queries']) == 2, 'Expected two scheduled audits')
    require([a.get('after_task_id') for a in public['audit_queries']] == [tasks[3]['id'], tasks[5]['id']],
            'Audits must follow tasks four and six')
    for audit in public['audit_queries']:
        keys(audit, 'after_task_id claims')
        require(isinstance(audit['claims'], list) and audit['claims'], 'Missing audit questions')
        require(len({c['key'] for c in audit['claims']}) == len(audit['claims']), 'Duplicate audit claim')
        for claim in audit['claims']:
            keys(claim, 'key value')
            text(claim['key'])
            text(claim['value'])
    return public


def validate_response(response, task):
    keys(response, 'task_id decision citations')
    require(response['task_id'] == task['id'], 'Response does not match pending task')
    require(response['decision'] in task['options'], 'Decision outside finite vocabulary')
    unique_strings(response['citations'])
    require(response['decision'] != 'abstain' or not response['citations'], 'Abstention has no citations')
    return response


def task_boundaries(public):
    available, boundaries = set(), {}
    for event in public['events']:
        if event['kind'] == 'source':
            available.add(event['payload']['id'])
        elif event['kind'] == 'task':
            boundaries[event['payload']['id']] = (event['index'], set(available), event['payload'])
    return boundaries


def validate_private(private, public):
    keys(private, 'schema_version episode_id public_digest metadata truth lineage tasks audits')
    require(private['schema_version'] == VERSION and private['episode_id'] == public['episode_id'],
            'Private/public episode mismatch')
    require(private['public_digest'] == digest(public), 'Private/public digest mismatch')
    keys(private['metadata'], 'generator_version seed family_id motif variant split condition omissions false_merges')
    require(type(private['metadata']['seed']) is int, 'Invalid seed')
    require(private['metadata']['split'] in ('development', 'validation'), 'Unknown split')
    require(private['metadata']['condition'] in ('C0', 'C1', 'C2', 'C3'), 'Unknown condition')
    keys(private['truth'], 'release_history owner_history update_kind')
    for name in ('release_history', 'owner_history'):
        validate_history(private['truth'][name])
    for interval in private['truth']['release_history']:
        day(interval['value'])
    require(private['truth']['update_kind'] in ('source_correction', 'world_change'), 'Invalid truth update kind')
    require(isinstance(private['lineage'], list), 'Invalid private lineage')
    all_ids = {e['payload']['id']: e['index'] for e in public['events'] if e['kind'] == 'source'}
    edge_ids = set()
    for edge in private['lineage']:
        keys(edge, 'child parent kind')
        require(edge['child'] in all_ids and edge['parent'] in all_ids, 'Unknown true lineage ID')
        require(edge['kind'] in ('copy', 'premise'), 'Unknown true edge kind')
        require(all_ids[edge['parent']] < all_ids[edge['child']], 'True lineage is forward or cyclic')
        identity = (edge['child'], edge['parent'], edge['kind'])
        require(identity not in edge_ids, 'Duplicate true edge')
        edge_ids.add(identity)
    boundaries = task_boundaries(public)
    require(isinstance(private['tasks'], list) and len(private['tasks']) == 6, 'Missing gold tasks')
    require({g['task_id'] for g in private['tasks']} == set(boundaries), 'Gold task IDs mismatch')
    for gold in private['tasks']:
        keys(gold, 'task_id boundary physical_decision answerable support_sets obsolete_decisions stratum')
        index, available, task = boundaries[gold['task_id']]
        require(gold['boundary'] == index, 'Wrong scoring boundary')
        require(type(gold['answerable']) is bool, 'Invalid answerability')
        require(gold['physical_decision'] in task['options'] and gold['physical_decision'] != 'abstain',
                'Physical decision outside task vocabulary')
        action, value = gold['physical_decision'].split(':', 1)
        if action in ('prepare_on', 'release_on'):
            release = value_at(private['truth']['release_history'], task['subject_time'])
            expected = (date.fromisoformat(release) - timedelta(days=1)).isoformat() if action == 'prepare_on' else release
            require(value == expected, 'Physical release action contradicts world history')
        elif action == 'owner':
            require(value == value_at(private['truth']['owner_history'], task['subject_time']),
                    'Physical owner action contradicts world history')
        unique_strings(gold['obsolete_decisions'])
        require(set(gold['obsolete_decisions']) <= set(task['options']) - {'abstain', gold['physical_decision']},
                'Invalid obsolete decision')
        require(gold['stratum'] in ('lookup', 'affected', 'control', 'historical'), 'Unknown stratum')
        require(isinstance(gold['support_sets'], list), 'Missing support sets')
        require(bool(gold['support_sets']) == gold['answerable'], 'Support/answerability mismatch')
        for support in gold['support_sets']:
            unique_strings(support)
            require(support and set(support) <= available, 'Gold support is empty, future, or unknown')
    require(isinstance(private['audits'], list), 'Invalid audits')
    require(len(private['audits']) == len(public['audit_queries']), 'Missing private audit labels')
    stripped = [dict(after_task_id=a['after_task_id'], claims=[dict(key=c['key'], value=c['value'])
                                                            for c in a['claims']]) for a in private['audits']]
    require(stripped == public['audit_queries'], 'Private audit does not match public questions')
    for audit in private['audits']:
        keys(audit, 'after_task_id claims')
        require(audit['after_task_id'] in boundaries, 'Unknown audit boundary')
        available = boundaries[audit['after_task_id']][1]
        require(isinstance(audit['claims'], list), 'Invalid audit claims')
        for claim in audit['claims']:
            keys(claim, 'key value support_sets')
            text(claim['key'])
            text(claim['value'])
            require(claim['support_sets'], 'Missing control support')
            for support in claim['support_sets']:
                unique_strings(support)
                require(support and set(support) <= available, 'Invalid audit support')
    return private
