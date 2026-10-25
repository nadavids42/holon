"""Run with PYTHONPATH=src python -m holon.cli (or installed `holon`)."""
import argparse
import json
import sqlite3

from holon.workspace.service import Workspace, required
from holon.inference.ollama import OllamaInterpreter


def main():
    parser = argparse.ArgumentParser(description="Inspect a persistent epistemic workspace")
    parser.add_argument("--db", default="runtime/holon.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("propose", help="Create a claim with explicit shared scope")
    create.add_argument("claim")
    create.add_argument("--scope", required=True)
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
    args = parser.parse_args()
    workspace = None
    try:
        workspace = Workspace(args.db)
        if args.command == "propose":
            result = {"proposition_id": workspace.create_proposition(args.claim, args.scope)}
        elif args.command == "report":
            result = workspace.add_report(args.proposition_id, args.source, args.text, args.relation,
                                          mass=args.mass, event_key=args.event_key, cluster_id=args.cluster_id,
                                          cluster_actor=args.cluster_actor, cluster_reason=args.cluster_reason)
        elif args.command in ("withdraw", "correct"):
            correction = ({"source": args.source, "report": args.text, "relation": args.relation, "mass": args.mass, "event_key": args.event_key}
                          if args.command == "correct" else {})
            result = workspace.withdraw_evidence(args.evidence_id, args.actor, args.reason, **correction)
        elif args.command == 'project':
            result = workspace.project(args.proposition_id, args.policy)
        elif args.command == 'migrate-impacts':
            result = workspace.migrate_impacts(args.proposition_id, args.actor, args.reason)
        elif args.command == "interpret":
            required(args.source, "source")
            required(args.text, "report")
            proposition = workspace.inspect(args.proposition_id)["proposition"]
            proposal = OllamaInterpreter(args.model, args.host, args.timeout).interpret(
                proposition, args.text)
            print(json.dumps({"proposition": proposition, "source": args.source,
                              "report": args.text, "relation": proposal.relation,
                              "reason": proposal.reason, "model": proposal.model,
                              "prompt_version": proposal.prompt_version}, indent=2))
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
            result = workspace.add_report(args.proposition_id, args.source, args.text,
                                          proposal.relation, interpretation=proposal)
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
