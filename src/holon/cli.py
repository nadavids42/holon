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
    show = commands.add_parser("inspect", help="Show current state, evidence, and revision history")
    show.add_argument("proposition_id")
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
            result = workspace.add_report(args.proposition_id, args.source, args.text, args.relation)
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
            result = workspace.inspect(args.proposition_id)
        print(json.dumps(result, indent=2))
    except (ValueError, sqlite3.Error, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    finally:
        if workspace is not None:
            workspace.close()


if __name__ == "__main__":
    main()
