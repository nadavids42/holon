"""Shared interpretation workflow for CLI and browser adapters."""
from dataclasses import asdict, dataclass
import json

from holon.inference.inference import Interpretation
from holon.workspace.metadata import canonical, digest
from holon.workspace.service import normalize_observed_at, required


class StalePreview(ValueError):
    """The reviewed context changed; generate and review a fresh proposal."""


@dataclass(frozen=True)
class Preview:
    kind: str
    arguments_json: str
    context_digest: str
    display_json: str
    interpretation: Interpretation

    def display(self):
        return json.loads(self.display_json)


def _context(workspace, kind, arguments):
    if kind == 'reinterpret':
        evidence = workspace.evidence_context(arguments['evidence_id'])
        pid = evidence['proposition_id']
    else:
        evidence = None
        pid = arguments['proposition_id']
    state = workspace.inspect(pid, projection_policy='binary-beta-v1')
    observation = (workspace.inspect_observation(arguments['observation_id'])['observation']
                   if kind == 'observation' else None)
    return {'state': state, 'observation': observation, 'evidence': evidence}


def preview_interpretation(workspace, interpreter, kind, **arguments):
    if kind not in ('report', 'observation', 'reinterpret'):
        raise ValueError('Unknown interpretation kind')
    if kind == 'report':
        required(arguments['source'], 'source')
        required(arguments['report'], 'report')
        arguments['observed_at'] = normalize_observed_at(arguments.get('observed_at'))
    if kind == 'reinterpret':
        required(arguments['actor'], 'actor')
        required(arguments['reason'], 'reason')
    # Snapshot ends before the potentially slow model request.
    with workspace.transaction():
        workspace._begin()
        context = _context(workspace, kind, arguments)
    proposition = context['state']['proposition']
    if kind == 'report':
        source, report, observed_at = arguments['source'], arguments['report'], arguments['observed_at']
    else:
        record = context['observation'] if kind == 'observation' else context['evidence']
        source, report, observed_at = record['source'], record['report'], record['observed_at']
        if kind == 'reinterpret' and record['withdrawn_at'] and not arguments.get('event_key'):
            raise ValueError('Evidence already withdrawn')
    proposal = interpreter.interpret(proposition, report)
    Interpretation.validate({'relation': proposal.relation, 'reason': proposal.reason}, proposal.model)
    display = dict(proposition=proposition, source=source, report=report,
                   observed_at=observed_at, **asdict(proposal))
    if kind == 'observation':
        display['observation_id'] = arguments['observation_id']
    if kind == 'reinterpret':
        display.update(evidence_id=arguments['evidence_id'],
                       observation_id=context['evidence']['observation_id'],
                       previous_relation=context['evidence']['relation'])
    return Preview(kind, canonical(arguments), digest(canonical(context)), canonical(display), proposal)


def accept_interpretation(workspace, preview):
    proposal = preview.interpretation
    if proposal.relation not in ('supports', 'contradicts'):
        raise ValueError('Uncertain or unrelated proposals cannot be accepted')
    arguments = json.loads(preview.arguments_json)
    # Revalidation and mutation share one write transaction, including CLI calls.
    with workspace.transaction():
        workspace._begin(immediate=True)
        if digest(canonical(_context(workspace, preview.kind, arguments))) != preview.context_digest:
            raise StalePreview('Workspace changed since this preview. Generate and review a fresh preview.')
        if preview.kind == 'report':
            return workspace.add_report(**arguments, relation=proposal.relation, interpretation=proposal)
        if preview.kind == 'observation':
            return workspace.link_observation(**arguments, relation=proposal.relation, interpretation=proposal)
        return workspace.reinterpret_evidence(**arguments, relation=proposal.relation, interpretation=proposal)
