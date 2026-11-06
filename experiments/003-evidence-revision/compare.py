#!/usr/bin/env python3
"""Run the four structured methods; evaluate only after each method finishes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
from revision_world.actor import ACTOR_VERSION
from revision_world.methods import METHOD_VERSION, METHODS
from revision_world.replay import Replay
from revision_world.schema import VERSION, digest, require, validate_private, validate_public, validate_response
from revision_world.scoring import score, score_audit
from run import source_manifest


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def run_method(public, method, directory, limit=100000):
    directory.mkdir(parents=True)
    replay = Replay(public)
    calls, audits, audited = [], [], set()
    peak = 0
    failure = None

    def invoke(view, query=None):
        nonlocal peak, failure
        index = len(calls)
        view_path = directory / f'{index:02d}-view.json'
        result_path = directory / f'{index:02d}-result.json'
        write(view_path, view)
        command = [sys.executable, str(HERE / 'method_worker.py'), '--method', method,
                   '--view', str(view_path), '--state', str(directory / 'state'),
                   '--output', str(result_path), '--limit', str(limit)]
        if query:
            query_path = directory / f'{index:02d}-audit.json'
            write(query_path, query)
            command += ['--audit', str(query_path)]
        start = time.perf_counter()
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        try:
            if failure is not None:
                raise ValueError('Method stopped after prior operational failure')
            proc = subprocess.run(command, capture_output=True, text=True, timeout=60,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            require(proc.returncode == 0, f'{method} worker failed: {proc.stderr}')
            result = json.loads(result_path.read_text())
            if view['pending_task'] and query is None:
                validate_response(result['response'], view['pending_task'])
        except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            failure = failure or str(error)
            task = view['pending_task']
            result = dict(response=([dict(**c, stance='unresolved', citations=[]) for c in query['claims']]
                                    if query else dict(task_id=task['id'], decision='abstain', citations=[]) if task else None),
                          counters={}, timings={}, exhausted=False, sqlite_rows_changed=None,
                          input_bytes=view_path.stat().st_size, operational_failure=failure,
                          note='Failure fallback; unfinished work counters unavailable. No retry or success claim.')
            write(result_path, result)
        elapsed = time.perf_counter() - start
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        process_cpu = (cpu_after.ru_utime + cpu_after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime)
        peak = max(peak, result.get('state_bytes', 0))
        calls.append(dict(kind='audit' if query else 'task_or_ingestion', result=result_path.name,
                          process_wall_seconds=elapsed, process_cpu_seconds=process_cpu, worker_timings=result['timings'],
                          sqlite_rows_changed=result['sqlite_rows_changed'],
                          input_bytes=result['input_bytes'],
                          checkpoint_write_bytes=result.get('checkpoint_write_bytes', 0),
                          checkpoint_writes=result.get('checkpoint_writes', 0), exhausted=result['exhausted'],
                          operational_failure=result.get('operational_failure')))
        return result

    while True:
        view = replay.advance_to_boundary()
        result = invoke(view)
        if view['pending_task']:
            replay.submit(result['response'])
            for query in replay.view()['audit_queries']:
                if query['after_task_id'] not in audited:
                    audit_result = invoke(replay.view(), query)
                    audits.append(dict(schema_version=VERSION, episode_id=public['episode_id'],
                                       public_digest=digest(public), after_task_id=query['after_task_id'],
                                       claims=audit_result['response'], costs=audit_result))
                    audited.add(query['after_task_id'])
        if view['restart_required']:
            # Both driver and method state are read from disk across this boundary.
            checkpoint = directory / 'restart.json'
            write(checkpoint, replay.checkpoint())
            replay = Replay.restore(public, json.loads(checkpoint.read_text()))
        if replay.view()['complete']:
            break
    responses = replay.responses()
    write(directory / 'responses.json', responses)
    write(directory / 'audits.json', audits)
    checkpoint = directory / 'state' / 'state.json'
    final = json.loads(checkpoint.read_text()) if checkpoint.exists() else dict(counters={}, exhausted=False)
    costs = dict(logical_counters=final['counters'], calls=calls, peak_persisted_state_bytes=peak,
                 budget_limit=limit, exhausted=final['exhausted'], operational_failure=failure,
                 incomplete_work_counters=failure is not None, model_calls=0, model_tokens=0,
                 note='Logical counters are instrumented operations, not physical I/O. Audit costs are separate.')
    write(directory / 'costs.json', costs)
    return responses, audits, costs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42, help='Fixed randomized method order')
    parser.add_argument('--limit', type=int, default=100000, help='Logical operation budget per method; audits separately')
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Output already exists')
        require(args.limit > 0, 'Budget must be positive')
        public = json.loads(args.public.read_text())
        private = json.loads(args.private.read_text())
        validate_public(public)
        validate_private(private, public)
        require(private['metadata']['split'] == 'development',
                'Step 4 runner is development-only; freeze/review the protocol before validation')
        args.output.mkdir(parents=True)
        order = list(METHODS)
        random.Random(args.seed).shuffle(order)
        provenance = source_manifest()
        # Hash actual core implementation and all harness/worker code, including untracked files.
        paths = [HERE / 'compare.py', HERE / 'method_worker.py', HERE / 'baselines.md', *sorted((HERE.parents[1] / 'src/holon').rglob('*.py'))]
        provenance['source_hashes'].update({str(p.relative_to(HERE.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in paths})
        manifest = dict(schema_version=VERSION, method_version=METHOD_VERSION, actor_version=ACTOR_VERSION,
                        track='S', purpose='development engineering acceptance; not a frozen evaluation',
                        episode_metadata=private['metadata'],
                        public_digest=digest(public), private_digest=digest(private), provenance=provenance,
                        order=order, seed=args.seed, concurrency=1, budget_limit=args.limit,
                        restart_policy='fresh worker process at every boundary; persisted state reused', status='running')
        write(args.output / 'manifest.json', manifest)
        results = {}
        for method in order:
            directory = args.output / method
            responses, audits, costs = run_method(public, method, directory, args.limit)
            # Gold is used here only, never in the worker argument or state.
            score_start = time.perf_counter()
            scored = score(public, private, responses)
            scored['deferred_metrics'].remove('model_and_method_cost')
            audit_scores = [score_audit(public, private, {k:v for k,v in a.items() if k != 'costs'}) for a in audits]
            write(directory / 'scores.json', dict(tasks=scored, audits=audit_scores,
                                                  scoring_wall_seconds=time.perf_counter()-score_start))
            results[method] = dict(metrics=scored['metrics'], audit_scores=audit_scores, exhausted=costs['exhausted'],
                                   operational_failure=costs['operational_failure'])
        write(args.output / 'summary.json', results)
        manifest['status'] = 'failed' if any(r['operational_failure'] for r in results.values()) else 'complete'
        write(args.output / 'manifest.json', manifest)
        print(f'Development comparison ({manifest["status"]}): {args.output / "summary.json"}')
        if manifest['status'] != 'complete':
            return 2
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        if 'manifest' in locals():
            manifest.update(status='failed', error=str(error))
            write(args.output / 'manifest.json', manifest)
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
