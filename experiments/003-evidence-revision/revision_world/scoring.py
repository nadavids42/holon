"""Offline deterministic scoring. Never return gold labels to the acting method."""
from .schema import (VERSION, digest, keys, require, task_boundaries, unique_strings,
                     validate_private, validate_public, validate_response)


def justified(citations, support_sets):
    cited = set(citations)
    allowed = set().union(*(set(s) for s in support_sets)) if support_sets else set()
    return cited <= allowed and any(set(s) <= cited for s in support_sets)


def rate(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator else None)


def score(public, private, responses):
    validate_public(public)
    validate_private(private, public)
    keys(responses, 'schema_version episode_id public_digest responses')
    require(responses['schema_version'] == VERSION and responses['episode_id'] == public['episode_id']
            and responses['public_digest'] == digest(public), 'Responses belong to another public schedule')
    require(isinstance(responses['responses'], list), 'Expected response list')
    boundaries = task_boundaries(public)
    by_id = {}
    for response in responses['responses']:
        require(isinstance(response, dict) and response.get('task_id') in boundaries, 'Unknown task response')
        task_id = response['task_id']
        require(task_id not in by_id, 'Duplicate task response')
        validate_response(response, boundaries[task_id][2])
        by_id[task_id] = response
    results = []
    for gold in private['tasks']:
        task_id = gold['task_id']
        response = by_id.get(task_id)
        available = boundaries[task_id][1]
        if response is None:
            decision, citations, outcome = None, [], 'missing'
        else:
            decision, citations = response['decision'], response['citations']
            outcome = 'abstain' if decision == 'abstain' else 'action'
        physical = decision == gold['physical_decision']
        unavailable = sorted(set(citations) - available)
        proof = not unavailable and justified(citations, gold['support_sets'])
        success = ((gold['answerable'] and physical and proof)
                   or (not gold['answerable'] and outcome == 'abstain'))
        results.append(dict(task_id=task_id, stratum=gold['stratum'], answerable=gold['answerable'],
                            outcome=outcome, physical_correct=physical,
                            valid_justification=gold['answerable'] and physical and proof,
                            justified_success=success, unavailable_citations=unavailable,
                            unsupported_correct=physical and not (gold['answerable'] and proof),
                            obsolete_action=decision in gold['obsolete_decisions']))
    answerable = [r for r in results if r['answerable']]
    unresolved = [r for r in results if not r['answerable']]
    affected = [r for r in answerable if r['stratum'] == 'affected']
    return dict(schema_version=VERSION, episode_id=public['episode_id'],
                public_digest=digest(public), private_digest=digest(private), rows=results,
                metrics=dict(
                    obsolete_action=rate(sum(r['obsolete_action'] for r in affected), len(affected)),
                    justified_task_success=rate(sum(r['justified_success'] for r in results), len(results)),
                    answerable_completion=rate(sum(r['justified_success'] for r in answerable), len(answerable)),
                    unresolved_success=rate(sum(r['justified_success'] for r in unresolved), len(unresolved)),
                    abstention=rate(sum(r['outcome'] == 'abstain' for r in results), len(results)),
                    missing=rate(sum(r['outcome'] == 'missing' for r in results), len(results)),
                    unsupported_correct=rate(sum(r['unsupported_correct'] for r in results), len(results)),
                ),
                deferred_metrics=['false_retraction', 'resurrection', 'repair_delay', 'provenance_quality',
                                  'model_and_method_cost'],
                note='Scoring an answer file is not a comparative experiment or evidence of Holon efficacy.')


def score_audit(public, private, audit_response):
    """Common read-only control audit; caller must run it on a method snapshot."""
    validate_public(public)
    validate_private(private, public)
    keys(audit_response, 'schema_version episode_id public_digest after_task_id claims')
    require(audit_response['schema_version'] == VERSION
            and audit_response['episode_id'] == public['episode_id']
            and audit_response['public_digest'] == digest(public), 'Audit belongs to another schedule')
    candidates = [a for a in private['audits'] if a['after_task_id'] == audit_response['after_task_id']]
    require(len(candidates) == 1, 'Unknown audit checkpoint')
    available = task_boundaries(public)[audit_response['after_task_id']][1]
    require(isinstance(audit_response['claims'], list), 'Invalid audit answers')
    answers = {}
    gold_keys = {c['key'] for c in candidates[0]['claims']}
    for claim in audit_response['claims']:
        keys(claim, 'key value stance citations')
        require(claim['key'] in gold_keys and claim['key'] not in answers, 'Unknown/duplicate audit claim')
        require(claim['stance'] in ('assert', 'deny', 'unresolved'), 'Invalid stance')
        unique_strings(claim['citations'])
        answers[claim['key']] = claim
    rows = []
    for gold in candidates[0]['claims']:
        answer = answers.get(gold['key'])
        retained = bool(answer and answer['stance'] == 'assert' and answer['value'] == gold['value']
                        and set(answer['citations']) <= available
                        and justified(answer['citations'], gold['support_sets']))
        rows.append(dict(key=gold['key'], retained=retained))
    return dict(after_task_id=audit_response['after_task_id'], rows=rows,
                valid_knowledge_retention=rate(sum(r['retained'] for r in rows), len(rows)))
