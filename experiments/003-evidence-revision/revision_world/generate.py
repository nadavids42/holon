"""Seeded development worlds. Nothing here is passed to a method as a bundle."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import random
from uuid import UUID

from .schema import VERSION, digest, require, validate_private, validate_public

GENERATOR_VERSION = 'project-world-generator-v1.1'
# Label-only amendment: preserve the original public event identities.
IDENTITY_VERSION = 'project-world-generator-v1'
MOTIFS = ('copied_date', 'alternative_support', 'shared_report', 'joint_premises',
          'lineage_reversal', 'temporal_scope')
CONDITIONS = ('C0', 'C1', 'C2', 'C3')


def generate(seed=42, motif=0, variant=0, condition='C0', update_kind=None):
    require(type(seed) is int, 'Seed must be an integer')
    require(type(motif) is int and 0 <= motif < 6, 'Motif must be 0..5')
    require(type(variant) is int and 0 <= variant < 6, 'Variant must be 0..5')
    require(condition in CONDITIONS, 'Unknown provenance condition')
    mode = update_kind or ('world_change' if motif == 5 and variant % 2 else 'source_correction')
    require(mode in ('source_correction', 'world_change'), 'Unsupported scenario update')
    # Separate random streams: provenance damage cannot change source IDs or tasks.
    rng = random.Random(f'{IDENTITY_VERSION}:{seed}:{motif}:{variant}')
    corruption = random.Random(f'lineage:{seed}:{motif}:{variant}')
    identifier = lambda: str(UUID(int=rng.getrandbits(128), version=4))
    public = dict(schema_version=VERSION, episode_id=identifier(), project_id=identifier(), rules=[
        'Preparation is one calendar day before the release date applicable at the requested subject time.',
        'Ready requires an assigned owner AND at least one valid approval; different valid approval records are alternatives.',
        'A source correction replaces only its identified statement; other statements in the same report remain usable.',
        'A world change preserves earlier applicability and changes the identified statement only from its effective time.',
        'Copies and summaries inherit their premises; a delayed copy is not a new independent observation.',
        'Withdrawals remove the named approval evidence, not every other approval.',
        'Lineage annotations are fallible; distinct source labels alone do not establish independence.',
        'Owner assignments persist after their subject date until explicitly superseded; a conflicting report alone does not resolve the assignment.',
        'Equal-scope conflicting owner reports without a resolving update require abstention.',
        'Answers cite sufficient source fragments; unrelated, stale, unavailable, or invented citations do not justify an action.',
    ], events=[], audit_queries=[])
    events, truth_edges, gold = public['events'], [], []
    old, new = '2026-11-13', '2026-11-16'
    past, current, effective, late = '2026-11-01', '2026-11-06', '2026-11-05', '2026-11-07'
    owner, other_owner = 'Morgan', 'Riley'
    base = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)

    def event(kind, payload):
        index = len(events)
        events.append(dict(index=index, id=identifier(), kind=kind, payload=payload))
        return index

    def source(statements, prose, *, parents=(), source_id=None, version='1', update=None, subject=past):
        sid = identifier()
        dependencies = [dict(parent=p, kind=k) for p, k in parents]
        payload = dict(id=sid, source_id=source_id or identifier(), version=version,
                       recorded_at=(base + timedelta(seconds=len(events))).isoformat(),
                       observed_at=None, subject_time=subject,
                       statements=[dict(key=k, value=v) for k, v in statements],
                       text=prose, dependencies=dependencies, update=update)
        event('source', payload)
        truth_edges.extend(dict(child=sid, **edge) for edge in dependencies)
        return sid

    def task(query, decision, alternatives, supports, stratum='control', subject=current,
             obsolete=(), answerable=True):
        tid = identifier()
        options = list(dict.fromkeys([decision, *alternatives, 'abstain']))
        rng.shuffle(options)
        boundary = event('task', dict(id=tid, query=query, subject_time=subject, options=options))
        gold.append(dict(task_id=tid, boundary=boundary, physical_decision=decision,
                         answerable=answerable, support_sets=supports if answerable else [],
                         obsolete_decisions=list(obsolete), stratum=stratum))
        return tid

    schedule_source = identifier()
    initial_statements = [('release_date', old)]
    if motif == 2:
        initial_statements += [('owner', owner), ('room', 'Cedar')]
    original = source(initial_statements,
                      f'Schedule: release {old}.' + (' Owner Morgan; room Cedar.' if motif == 2 else ''),
                      source_id=schedule_source)
    owner_id = source([('owner', owner)], f'Signed assignment: {owner} owns preparation.')
    approvals = [source([('approval', 'yes')], f'Independent approval record {i + 1}: approved.')
                 for i in range(2 + (variant % 3 if motif in (1, 3, 4) else 0))]
    controls = {}
    for key, value in [('channel', 'email'), ('region', 'east'), ('room', 'Cedar'), ('checklist', 'standard')]:
        controls[key] = (value, source([(key, value)], f'Project {key}: {value}.'))
    copies = []
    for i in range(2 + variant):
        # Distinct topologies by variant; no chain deeper than three.
        parent = original if i % 2 == 0 else copies[-1]
        copies.append(source([('release_date', old)],
                             f'Summary of fragment {parent}: release {old}.', parents=[(parent, 'copy')]))
    derived = source([('prepare_date', '2026-11-12')],
                     f'Using schedule {original}, preparation is November 12.', parents=[(original, 'premise')])
    if motif == 3:
        source([('ready', 'yes')], f'Ready based on owner {owner_id} and approval {approvals[0]}.',
               parents=[(owner_id, 'premise'), (approvals[0], 'premise')])
        source([('task_ready', 'yes')], f'Task readiness also requires preparation record {derived}.',
               parents=[(derived, 'premise'), (owner_id, 'premise')])

    task(f'Which release date is stated in fragment {original}? This is a report-content lookup.',
         f'reported_release:{old}', [f'reported_release:{new}'], [[original]], 'lookup', past)
    owner_support = [[owner_id]] + ([[original]] if motif == 2 else [])
    task('Who is assigned to preparation?', f'owner:{owner}', [f'owner:{other_owner}'], owner_support)

    update = dict(kind=mode, targets=[original], effective_at=effective if mode == 'world_change' else None)
    prose = (f'Correction to release_date in {original}: {old} was erroneous; the release is {new}.'
             if mode == 'source_correction' else
             f'Change to release_date in {original}: effective {effective}, release changes from {old} to {new}; earlier validity is retained.')
    changed = source([('release_date', new)], prose, source_id=schedule_source, version='2',
                     update=update, subject=effective if mode == 'world_change' else past)
    active_approvals = list(approvals)
    if motif in (1, 4):
        source([('approval_withdrawal', approvals[0])], f'Withdraw approval {approvals[0]} only.',
               update=dict(kind='withdrawal', targets=[approvals[0]], effective_at=None), subject=current)
        active_approvals.remove(approvals[0])

    task('On the current schedule, when must preparation occur?', 'prepare_on:2026-11-15',
         ['prepare_on:2026-11-12'], [[changed]], 'affected', obsolete=['prepare_on:2026-11-12'])
    # Every sufficient set needs an owner AND one approval; approvals are OR alternatives.
    ready_support = [o + [approval] for o in owner_support for approval in active_approvals]
    fourth = task('Is preparation ready to be assigned (owner AND at least one valid approval)?',
                  'ready:yes', ['ready:no'], ready_support)
    event('restart', {})
    source([('release_date', old)], f'Delayed copy of {copies[-1]}: release {old}.',
           parents=[(copies[-1], 'copy')])
    source([('meeting_room', 'Birch')], 'Unrelated update: the next meeting uses Birch.', subject=current)
    if motif == 4:
        source([('lineage_review', 'distinct')],
               f'Lineage review: approvals {approvals[0]} and {approvals[1]} have distinct origins.',
               update=dict(kind='lineage_correction', targets=[approvals[1]], effective_at=None), subject=current)
    unresolved = motif == 5 and variant >= 4
    if unresolved:
        source([('owner', other_owner)], f'Conflicting assignment for {late}: {other_owner} owns preparation; no priority or supersession specified.',
               subject=late)
    task('After the delayed report, when must preparation occur on the current schedule?',
         'prepare_on:2026-11-15', ['prepare_on:2026-11-12'], [[changed]], 'affected',
         obsolete=['prepare_on:2026-11-12'])
    if motif == 5 and not unresolved:
        historical = old if mode == 'world_change' else new
        last = task(f'What release date actually applied at subject time {past}, using everything now known?',
                    f'release_on:{historical}', [f'release_on:{new if historical == old else old}'],
                    [[original, changed]] if mode == 'world_change' else [[changed]], 'historical', past)
    else:
        last = task(f'Who is assigned to preparation at {late if unresolved else current}?',
                    f'owner:{owner}', [f'owner:{other_owner}'], owner_support,
                    subject=late if unresolved else current, answerable=not unresolved)

    # Corrupt only the public dependency declarations, not prose or the true graph.
    candidates = [(e['payload'], edge) for e in events if e['kind'] == 'source'
                  for edge in e['payload']['dependencies']]
    require(len(candidates) >= 4, 'Insufficient lineage declarations')
    eligible = len(candidates)
    fraction = {'C0': 0, 'C1': .25, 'C2': .75, 'C3': .25}[condition]
    remove_count = max(1, int(eligible * fraction + .5)) if fraction else 0
    omissions = {'copy': 0, 'premise': 0, 'eligible': eligible, 'removed': remove_count}
    for payload, edge in corruption.sample(candidates, remove_count):
        payload['dependencies'].remove(edge)
        omissions[edge['kind']] += 1
    false_merges = []
    if condition == 'C3':
        target = next(e['payload'] for e in events if e['kind'] == 'source' and e['payload']['id'] == approvals[1])
        target['dependencies'].append(dict(parent=approvals[0], kind='copy'))
        false_merges.append(dict(child=approvals[1], parent=approvals[0]))

    public['audit_queries'] = [dict(after_task_id=tid, claims=[dict(key=k, value=v)
                                                            for k, (v, _) in controls.items()])
                               for tid in (fourth, last)]

    private = dict(schema_version=VERSION, episode_id=public['episode_id'], public_digest=digest(public),
                   metadata=dict(generator_version=GENERATOR_VERSION, seed=seed,
                                 family_id=f'm{motif}-v{variant}', motif=MOTIFS[motif], variant=variant,
                                 split='development' if variant < 4 else 'validation', condition=condition,
                                 omissions=omissions, false_merges=false_merges),
                   truth=dict(release_history=(
                       [dict(start=past, end=effective, value=old), dict(start=effective, end=None, value=new)]
                       if mode == 'world_change' else [dict(start=past, end=None, value=new)]),
                       owner_history=([dict(start=past, end=late, value=owner),
                                       dict(start=late, end=None, value=owner)] if unresolved else
                                      [dict(start=past, end=None, value=owner)]),
                       update_kind=mode), lineage=truth_edges, tasks=gold,
                   audits=[dict(after_task_id=tid, claims=[dict(key=k, value=v, support_sets=[[sid]] +
                                                             ([[original]] if motif == 2 and k == 'room' else []))
                                                         for k, (v, sid) in controls.items()])
                           for tid in (fourth, last)])
    validate_public(public)
    validate_private(private, public)
    return deepcopy(public), deepcopy(private)


def catalogue(seed=42):
    """36 candidate families × 4 paired views; not scored validation results."""
    return [generate(seed, motif, variant, condition)
            for motif in range(6) for variant in range(6) for condition in CONDITIONS]
