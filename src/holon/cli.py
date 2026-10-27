"""Run with PYTHONPATH=src python -m holon.cli (or installed `holon`)."""
import argparse
import json
import sqlite3

from holon.workspace.service import Workspace, required, normalize_observed_at
from holon.inference.ollama import OllamaInterpreter


def main():
    parser = argparse.ArgumentParser(description="Inspect a persistent epistemic workspace")
    parser.add_argument("--db", default="runtime/holon.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
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
    workspace = None
    try:
        workspace = Workspace(args.db)
        if args.command == "propose":
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
            required(args.actor, 'actor')
            required(args.reason, 'reason')
            proposal = None
            relation = args.relation
            if args.model is not None:
                context = workspace.evidence_context(args.evidence_id)
                if context['withdrawn_at'] is not None and args.event_key is None:
                    raise ValueError(f"Evidence already withdrawn: {args.evidence_id}")
                proposition = {'id': context['proposition_id'], 'claim': context['claim'], 'scope': context['scope']}
                proposal = OllamaInterpreter(args.model, args.host, args.timeout).interpret(proposition, context['report'])
                print(json.dumps({'evidence_id': args.evidence_id, 'observation_id': context['observation_id'],
                    'proposition': proposition, 'source': context['source'], 'report': context['report'],
                    'observed_at': context['observed_at'], 'previous_relation': context['relation'],
                    'relation': proposal.relation, 'reason': proposal.reason, 'model': proposal.model,
                    'prompt_version': proposal.prompt_version}, indent=2))
                if proposal.relation in ('unrelated', 'uncertain'):
                    print('No update: report is unrelated or uncertain.')
                    return
                try:
                    answer = input('Accept this replacement evidence link? [y/N] ')
                except (EOFError, KeyboardInterrupt):
                    answer = ''
                if answer.strip().lower() not in ('y', 'yes'):
                    print('Not accepted. Workspace unchanged.')
                    return
                relation = proposal.relation
            result = workspace.reinterpret_evidence(args.evidence_id, relation, args.actor, args.reason,
                                                     mass=args.mass, event_key=args.event_key, interpretation=proposal)
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
            if existing:
                observation = workspace.inspect_observation(args.observation_id)['observation']
                source, report, observed_at = observation['source'], observation['report'], observation['observed_at']
            else:
                required(args.source, "source")
                required(args.text, "report")
                source, report = args.source, args.text
                observed_at = normalize_observed_at(args.observed_at)
            proposition = workspace.inspect(args.proposition_id)["proposition"]
            proposal = OllamaInterpreter(args.model, args.host, args.timeout).interpret(
                proposition, report)
            print(json.dumps({"proposition": proposition, "source": source,
                              "report": report, "relation": proposal.relation,
                              "reason": proposal.reason, "model": proposal.model,
                              "prompt_version": proposal.prompt_version, "observed_at": observed_at}, indent=2))
            if proposal.relation in ("unrelated", "uncertain"):
                print("No update: report is unrelated or uncertain.")
                return
            try:
                answer = input("Accept this evidence link? [y/N] ")
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer.strip().lower() not in ("y", "yes"):
                print("Not accepted. Workspace unchanged.")
                return
            if existing:
                result = workspace.link_observation(args.observation_id, args.proposition_id,
                                                    proposal.relation, interpretation=proposal)
            else:
                result = workspace.add_report(args.proposition_id, source, report,
                                              proposal.relation, interpretation=proposal, observed_at=observed_at)
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
