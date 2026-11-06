#!/usr/bin/env python3
"""Generate worlds, advance public replay, and score saved answers offline."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

from revision_world.generate import GENERATOR_VERSION, catalogue, generate
from revision_world.replay import Replay
from revision_world.schema import VERSION, digest
from revision_world.scoring import score, score_audit


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def source_manifest():
    paths = [HERE / 'run.py', HERE / 'protocol.md', *sorted((HERE / 'revision_world').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
        status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True, timeout=10).strip()
        patch = subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=ROOT, timeout=10)
        dirty_diff_hash = hashlib.sha256(patch).hexdigest()
    except (OSError, subprocess.SubprocessError):
        commit, status, dirty_diff_hash = None, None, None
    return dict(python=platform.python_version(), commit=commit, status=status,
                tracked_diff_sha256=dirty_diff_hash, source_hashes=hashes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('generate', help='Export public schedules and separate private scoring files')
    build.add_argument('--seed', type=int, default=42)
    build.add_argument('--motif', type=int, choices=range(6), default=0)
    build.add_argument('--variant', type=int, choices=range(6), default=0)
    build.add_argument('--condition', choices=('C0', 'C1', 'C2', 'C3'), default='C0')
    build.add_argument('--update-kind', choices=('source_correction', 'world_change'))
    build.add_argument('--catalogue', action='store_true', help='Generate all 36 families × four conditions')
    replay = commands.add_parser('replay', help='Advance to one task/restart boundary without private data')
    replay.add_argument('--public', type=Path, required=True)
    replay.add_argument('--checkpoint', type=Path)
    replay.add_argument('--response', type=Path, help='One response to the pending task in the checkpoint')
    for name in ('score', 'audit'):
        scoring = commands.add_parser(name, help='Offline scoring; never feed output back to a live method')
        scoring.add_argument('--public', type=Path, required=True)
        scoring.add_argument('--private', type=Path, required=True)
        scoring.add_argument('--responses', type=Path, required=True)
    for command in (build, replay, *[commands.choices[n] for n in ('score', 'audit')]):
        command.add_argument('--output', type=Path, required=True, help='New output directory; existing paths refused')
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError(f'Output already exists: {args.output}')
        if args.command == 'generate':
            if args.catalogue and args.update_kind:
                raise ValueError('--update-kind applies only to single scenarios')
            worlds = catalogue(args.seed) if args.catalogue else [generate(
                args.seed, args.motif, args.variant, args.condition, args.update_kind)]
            manifest = dict(schema_version=VERSION, generator_version=GENERATOR_VERSION,
                            seed=args.seed, provenance=source_manifest(), episodes=[])
            args.output.mkdir(parents=True)
            (args.output / 'public').mkdir()
            (args.output / 'private').mkdir()
            for public, private in worlds:
                name = digest(public) + '.json' if args.catalogue else 'episode.json'
                write(args.output / 'public' / name, public)
                write(args.output / 'private' / name, private)
                manifest['episodes'].append(dict(public=f'public/{name}', private=f'private/{name}',
                                                 public_digest=digest(public), private_digest=digest(private),
                                                 metadata=private['metadata']))
            write(args.output / 'manifest.json', manifest)
            print(f'Generated {len(worlds)} episodes; trusted-harness manifest: {args.output / "manifest.json"}')
        elif args.command == 'replay':
            public = read(args.public)
            replay = Replay.restore(public, read(args.checkpoint)) if args.checkpoint else Replay(public)
            if args.response:
                replay.submit(read(args.response))
            view = replay.advance_to_boundary()
            args.output.mkdir(parents=True)
            write(args.output / 'view.json', view)
            write(args.output / 'checkpoint.json', replay.checkpoint())
            write(args.output / 'responses.json', replay.responses())
            print(f'Public view: {args.output / "view.json"}; restart={view["restart_required"]}; complete={view["complete"]}')
        else:
            operation = score if args.command == 'score' else score_audit
            result = operation(read(args.public), read(args.private), read(args.responses))
            args.output.mkdir(parents=True)
            write(args.output / 'scores.json', result)
            print(f'Offline scores: {args.output / "scores.json"}')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
