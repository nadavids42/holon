"""Run with PYTHONPATH=src python -m holon.cli (or installed `holon`)."""
import argparse
import json
import sqlite3

from holon.workspace.service import Workspace
from holon.workspace.operations import preview_interpretation, accept_interpretation
from holon.inference.ollama import OllamaInterpreter


def review(preview, *, replacement=False):
    print(json.dumps(preview.display(), indent=2))
    if preview.interpretation.relation in ('unrelated', 'uncertain'):
        print('No update: report is unrelated or uncertain.')
        return False
    try:
        answer = input('Accept this replacement evidence link? [y/N] ' if replacement
                       else 'Accept this evidence link? [y/N] ')
    except (EOFError, KeyboardInterrupt):
        answer = ''
    if answer.strip().lower() not in ('y', 'yes'):
        print('Not accepted. Workspace unchanged.')
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Inspect a persistent epistemic workspace")
    parser.add_argument("--db", default="runtime/holon.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser('inspect-derivations', help='Read derivations and their proposition references')
    commands.add_parser('inspect-lineage', help='Read origin assignments, events and revision')
    derive = commands.add_parser('derive', help='Record a supplied justification without changing belief status')
    derive.add_argument('proposition_id')
    derive.add_argument('--id', dest='justification_id', required=True)
    derive.add_argument('--relation', choices=['supports', 'contradicts'], default='supports')
    derive.add_argument('--premise', nargs=2, metavar=('PROPOSITION_ID', 'RELATION'), action='append', required=True)
    derive.add_argument('--rule', required=True)
    derive.add_argument('--actor', required=True)
    derive.add_argument('--reason', required=True)
    for name in ('assign-origin', 'merge-origins', 'reverse-lineage'):
        command = commands.add_parser(name, help='Append an attributed origin-lineage event')
        command.add_argument('--event-id', required=True)
        command.add_argument('--actor', required=True)
        command.add_argument('--reason', required=True)
        command.add_argument('--expected-revision', type=int, required=True)
        if name == 'assign-origin':
            command.add_argument('observation_id')
            group = command.add_mutually_exclusive_group(required=True)
            group.add_argument('--group', dest='group_id')
            group.add_argument('--unknown', action='store_true')
        elif name == 'merge-origins':
            command.add_argument('--group', dest='group_ids', action='append', required=True)
            command.add_argument('--target', dest='target_group_id', required=True)
        else:
            command.add_argument('target_event_id')
    serve = commands.add_parser('serve', help='Open a local browser workspace')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--model', default='qwen3:14b')
    serve.add_argument('--host', default='http://127.0.0.1:11434', help='Ollama URL')
    serve.add_argument('--timeout', type=float, default=120)
    create = commands.add_parser("propose", help="Create a claim with explicit shared scope")
    create.add_argument("claim")
    create.add_argument("--scope", required=True)
    observe = commands.add_parser('observe', help='Record an observation without linking it')
    observe.add_argument('--source', required=True)
    observe.add_argument('--text', required=True)
    observe.add_argument('--observed-at')
    inspect_observation = commands.add_parser('inspect-observation', help='Inspect an observation and its links')
    inspect_observation.add_argument('observation_id')
    link = commands.add_parser('link', help='Link an existing observation to a proposition')
    link.add_argument('observation_id')
    link.add_argument('proposition_id')
    link.add_argument('--relation', choices=['supports', 'contradicts'], required=True)
    link.add_argument('--mass', type=float, default=1.0)
    link.add_argument('--event-key')
    link.add_argument('--cluster-id')
    link.add_argument('--cluster-actor')
    link.add_argument('--cluster-reason')
    reinterpret = commands.add_parser('reinterpret', help='Replace a link while retaining its observation')
    reinterpret.add_argument('evidence_id')
    reinterpret.add_argument('--actor', required=True)
    reinterpret.add_argument('--reason', required=True)
    method = reinterpret.add_mutually_exclusive_group(required=True)
    method.add_argument('--relation', choices=['supports', 'contradicts'])
    method.add_argument('--model', nargs='?', const='qwen3:14b')
    reinterpret.add_argument('--host', default='http://127.0.0.1:11434')
    reinterpret.add_argument('--timeout', type=float, default=120)
    reinterpret.add_argument('--mass', type=float)
    reinterpret.add_argument('--event-key')
    report = commands.add_parser("report", help="Link a structured report to a claim")
    report.add_argument("proposition_id")
    report.add_argument("--source", required=True)
    report.add_argument("--text", required=True)
    report.add_argument("--relation", choices=["supports", "contradicts"], required=True)
    report.add_argument('--mass', type=float, default=1.0)
    report.add_argument('--event-key')
    report.add_argument('--cluster-id')
    report.add_argument('--cluster-actor')
    report.add_argument('--cluster-reason')
    report.add_argument('--observed-at')
    for name in ("withdraw", "correct"):
        command = commands.add_parser(name, help="Withdraw evidence or replace it with a corrected report")
        command.add_argument("evidence_id")
        command.add_argument("--actor", required=True)
        command.add_argument("--reason", required=True)
        if name == "correct":
            command.add_argument("--source", required=True)
            command.add_argument("--text", required=True)
            command.add_argument("--relation", choices=["supports", "contradicts"], required=True)
            command.add_argument('--mass', type=float, default=1.0)
            command.add_argument('--event-key')
            command.add_argument('--observed-at')
    project = commands.add_parser('project', help='Read binary Beta projection without changing beliefs')
    project.add_argument('proposition_id')
    project.add_argument('--policy', default='binary-beta-v1')
    migrate = commands.add_parser('migrate-impacts', help='Explicitly annotate legacy evidence with experimental assumptions')
    migrate.add_argument('proposition_id')
    migrate.add_argument('--actor', required=True)
    migrate.add_argument('--reason', required=True)
    show = commands.add_parser("inspect", help="Show current state, evidence, and revision history")
    show.add_argument("proposition_id")
    show.add_argument("--projection", action="store_true")
    show.add_argument("--policy", default="binary-beta-v1")
    interpret = commands.add_parser("interpret", help="Preview a model interpretation before accepting")
    interpret.add_argument("proposition_id")
    interpret.add_argument("--source", required=True)
    interpret.add_argument("--text", required=True)
    interpret.add_argument("--model", default="qwen3:14b")
    interpret.add_argument("--host", default="http://127.0.0.1:11434")
    interpret.add_argument("--timeout", type=float, default=120)
    interpret.add_argument('--observed-at')
    interpret_existing = commands.add_parser('interpret-observation', help='Preview a model interpretation of an existing observation')
    interpret_existing.add_argument('observation_id')
    interpret_existing.add_argument('proposition_id')
    interpret_existing.add_argument('--model', default='qwen3:14b')
    interpret_existing.add_argument('--host', default='http://127.0.0.1:11434')
    interpret_existing.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if args.command == 'serve':
        from holon.web.server import serve
        try:
            serve(args.db, port=args.port, model=args.model, host=args.host, timeout=args.timeout)
        except (ValueError, sqlite3.Error, OSError) as error:
            parser.exit(2, f"error: {error}\n")
        return
    workspace = None
    try:
        workspace = Workspace(args.db)
        if args.command == 'inspect-derivations':
            result = workspace.inspect_derivations()
        elif args.command == 'inspect-lineage':
            result = workspace.inspect_lineage()
        elif args.command == 'derive':
            result = workspace.add_derivation(args.justification_id,
                {'proposition_id': args.proposition_id, 'relation': args.relation},
                [{'proposition_id': pid, 'relation': relation} for pid, relation in args.premise],
                args.rule, args.actor, args.reason)
        elif args.command in ('assign-origin', 'merge-origins', 'reverse-lineage'):
            common = dict(event_id=args.event_id, actor=args.actor, reason=args.reason,
                          expected_revision=args.expected_revision)
            if args.command == 'assign-origin':
                result = workspace.assign_origin(observation_id=args.observation_id, group_id=args.group_id, **common)
            elif args.command == 'merge-origins':
                result = workspace.merge_origins(group_ids=args.group_ids, target_group_id=args.target_group_id, **common)
            else:
                result = workspace.reverse_lineage(target_event_id=args.target_event_id, **common)
        elif args.command == "propose":
            result = {"proposition_id": workspace.create_proposition(args.claim, args.scope)}
        elif args.command == 'observe':
            result = {'observation_id': workspace.record_observation(args.source, args.text, observed_at=args.observed_at)}
        elif args.command == 'inspect-observation':
            result = workspace.inspect_observation(args.observation_id)
        elif args.command == 'link':
            result = workspace.link_observation(args.observation_id, args.proposition_id, args.relation,
                mass=args.mass, event_key=args.event_key, cluster_id=args.cluster_id,
                cluster_actor=args.cluster_actor, cluster_reason=args.cluster_reason)
        elif args.command == 'reinterpret':
            if args.model is not None:
                preview = preview_interpretation(workspace,
                    OllamaInterpreter(args.model, args.host, args.timeout), 'reinterpret',
                    evidence_id=args.evidence_id, actor=args.actor, reason=args.reason,
                    mass=args.mass, event_key=args.event_key)
                if not review(preview, replacement=True):
                    return
                result = accept_interpretation(workspace, preview)
            else:
                result = workspace.reinterpret_evidence(args.evidence_id, args.relation, args.actor,
                    args.reason, mass=args.mass, event_key=args.event_key)
        elif args.command == "report":
            result = workspace.add_report(args.proposition_id, args.source, args.text, args.relation,
                                          mass=args.mass, event_key=args.event_key, cluster_id=args.cluster_id,
                                          cluster_actor=args.cluster_actor, cluster_reason=args.cluster_reason,
                                          observed_at=args.observed_at)
        elif args.command in ("withdraw", "correct"):
            correction = ({"source": args.source, "report": args.text, "relation": args.relation, "mass": args.mass, "event_key": args.event_key, "observed_at": args.observed_at}
                          if args.command == "correct" else {})
            result = workspace.withdraw_evidence(args.evidence_id, args.actor, args.reason, **correction)
        elif args.command == 'project':
            result = workspace.project(args.proposition_id, args.policy)
        elif args.command == 'migrate-impacts':
            result = workspace.migrate_impacts(args.proposition_id, args.actor, args.reason)
        elif args.command in ("interpret", "interpret-observation"):
            existing = args.command == 'interpret-observation'
            arguments = ({'observation_id': args.observation_id} if existing else
                         {'source': args.source, 'report': args.text, 'observed_at': args.observed_at})
            preview = preview_interpretation(workspace,
                OllamaInterpreter(args.model, args.host, args.timeout),
                'observation' if existing else 'report', proposition_id=args.proposition_id, **arguments)
            if not review(preview):
                return
            result = accept_interpretation(workspace, preview)
        else:
            result = workspace.inspect(args.proposition_id, projection_policy=args.policy if args.projection else None)
        print(json.dumps(result, indent=2))
    except (ValueError, sqlite3.Error, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    finally:
        if workspace is not None:
            workspace.close()


if __name__ == "__main__":
    main()
