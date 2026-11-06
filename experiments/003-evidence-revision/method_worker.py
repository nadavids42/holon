#!/usr/bin/env python3
"""Public-prefix worker. No scorer, private bundle, or complete schedule input."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'src'))
from revision_world.actor import ACTOR_VERSION, audit, decide
from revision_world.methods import BudgetExceeded, METHOD_VERSION, METHODS, Meter, Method, initial_state
from revision_world.schema import VERSION, canonical, keys, require, validate_response


def execute(name, view, directory, limit=100000, audit_query=None):
    keys(view, 'schema_version episode_id project_id rules events audit_queries pending_task restart_required complete')
    require(view['schema_version'] == VERSION, 'Unsupported view schema')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else initial_state(name, view['episode_id'])
    require(state['version'] == METHOD_VERSION and state['method'] == name, 'Method checkpoint mismatch')
    # Audit runs on detached JSON and a private database copy, never the live ledger.
    if audit_query is not None:
        with tempfile.TemporaryDirectory() as tmp:
            for source in directory.glob('holon.sqlite*'):
                shutil.copy2(source, Path(tmp) / source.name)
            return operate(name, deepcopy(state), view, Path(tmp), limit, audit_query)
    result = operate(name, state, view, directory, limit, None)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(canonical(state) + '\n')
    temporary.replace(path)
    result['checkpoint_write_bytes'] = path.stat().st_size
    result['checkpoint_writes'] = 1
    result['state_bytes'] = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
    return result


def operate(name, state, view, directory, limit, audit_query):
    meter = Meter({} if audit_query is not None else state['counters'], limit)
    wall, cpu = time.perf_counter(), time.process_time()
    method = Method(name, state, directory, meter)
    task = view['pending_task']
    response, claims, exhausted = None, [], state['exhausted']
    timings = {}
    try:
        if exhausted:
            raise BudgetExceeded()
        meter.add('validation', 'records_visited', len(view['events']))
        meter.add('validation', 'input_bytes', len(canonical(view).encode()))
        start = time.perf_counter()
        method.ingest(view)
        timings['ingestion_wall_seconds'] = time.perf_counter() - start
        start = time.perf_counter()
        if audit_query is not None:
            # Last completed task supplies public subject time, not private gold scope.
            completed = next(e['payload'] for e in view['events'] if e['kind'] == 'task'
                             and e['payload']['id'] == audit_query['after_task_id'])
            claims = method.claims(audit_keys=[c['key'] for c in audit_query['claims']],
                                   subject_time=completed['subject_time'])
            response = audit(audit_query['claims'], claims, meter)
        elif task:
            claims = method.claims(task)
            response = decide(task, claims, meter)
            validate_response(response, task)
            meter.add('validation', 'records_visited', 1 + len(response['citations']))
        timings['query_wall_seconds'] = time.perf_counter() - start
    except BudgetExceeded:
        exhausted = True
        response = ([dict(**c, stance='unresolved', citations=[]) for c in audit_query['claims']]
                    if audit_query is not None else
                    dict(task_id=task['id'], decision='abstain', citations=[]) if task else None)
    finally:
        sqlite_changes = method.ws.db.total_changes if method.ws else 0
        method.close()
    if audit_query is None:
        state['counters'], state['exhausted'] = meter.counters, exhausted
    return dict(method=name, method_version=METHOD_VERSION, actor_version=ACTOR_VERSION,
                response=response, claims=claims, counters=meter.counters, exhausted=exhausted,
                timings=dict(**timings, wall_seconds=time.perf_counter()-wall, cpu_seconds=time.process_time()-cpu),
                sqlite_rows_changed=sqlite_changes, model_calls=0, model_tokens=0, retries=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=METHODS, required=True)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=100000)
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    try:
        require(args.limit > 0, 'Budget must be positive')
        require(not args.output.exists(), 'Output already exists')
        view = json.loads(args.view.read_text())
        query = json.loads(args.audit.read_text()) if args.audit else None
        result = execute(args.method, view, args.state, args.limit, query)
        result['input_bytes'] = args.view.stat().st_size
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
