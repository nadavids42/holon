"""Run with PYTHONPATH=src python -m holon.cli (or installed `holon`)."""
import argparse
import json
import sqlite3

from holon.workspace.service import Workspace


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
    args = parser.parse_args()
    workspace = None
    try:
        workspace = Workspace(args.db)
        if args.command == "propose":
            result = {"proposition_id": workspace.create_proposition(args.claim, args.scope)}
        elif args.command == "report":
            result = workspace.add_report(args.proposition_id, args.source, args.text, args.relation)
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
