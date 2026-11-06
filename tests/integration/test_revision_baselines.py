"""Baseline acceptance: public-only decisions, real Holon, persistence, and failures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / 'experiments/003-evidence-revision'
sys.path.insert(0, str(EXPERIMENT))
from method_worker import execute
from revision_world.actor import decide
from revision_world.generate import generate
from revision_world.methods import Meter, METHODS
from revision_world.replay import Replay
from revision_world.schema import digest
from revision_world.scoring import score, score_audit


def play(public, name, directory, limit=100000):
    replay = Replay(public)
    while True:
        view = replay.advance_to_boundary()
        result = execute(name, view, directory, limit)
        if view['pending_task']:
            replay.submit(result['response'])
        if view['restart_required']:
            replay = Replay.restore(public, json.loads(json.dumps(replay.checkpoint())))
        if replay.view()['complete']:
            return replay.responses(), result


class RevisionBaselineTests(unittest.TestCase):
    def test_expected_stale_copy_failures_and_reconstruction(self):
        public, private = generate()
        with tempfile.TemporaryDirectory() as tmp:
            results = {}
            for name in METHODS:
                responses, _ = play(public, name, Path(tmp)/name)
                results[name] = score(public, private, responses)
            self.assertEqual(results['H0']['metrics']['abstention']['numerator'], 2)
            self.assertEqual(results['LWW']['metrics']['obsolete_action']['numerator'], 1)
            for name in ('RR','RB'):
                self.assertEqual(results[name]['metrics']['justified_task_success']['numerator'], 6)

    def test_correction_is_link_local_in_real_holon_database(self):
        from holon.workspace.service import Workspace
        public, _ = generate(motif=2)
        replay = Replay(public)
        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(3):
                view = replay.advance_to_boundary()
                result = execute('H0', view, tmp)
                replay.submit(result['response'])
            state = json.loads((Path(tmp)/'state.json').read_text())
            original = public['events'][0]['payload']['id']
            links = [l for l in state['links'] if l['source'] == original]
            self.assertEqual({l['key']:l['active'] for l in links},
                             {'release_date':False,'owner':True,'room':True})
            workspace = Workspace(Path(tmp)/'holon.sqlite')
            try:
                evidence_count = workspace.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0]
                self.assertEqual(evidence_count, len(state['links']))
                self.assertTrue(state['diagnostics'])
                self.assertTrue(all('projection' in d for d in state['diagnostics'].values()))
            finally:
                workspace.close()
            execute('H0', view, tmp)  # same prefix must not double-ingest
            again = json.loads((Path(tmp)/'state.json').read_text())
            self.assertEqual(len(state['links']), len(again['links']))
            self.assertEqual(state['event_hashes'], again['event_hashes'])

    def test_world_change_history_and_h0_unsupported_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ('source_correction','world_change'):
                public, private = generate(motif=5, variant=0, update_kind=mode)
                for name in METHODS:
                    responses, _ = play(public, name, Path(tmp)/mode/name)
                    if name in ('RR','RB'):
                        self.assertEqual(score(public,private,responses)['metrics']['justified_task_success']['numerator'],6)
                        final = responses['responses'][-1]
                        self.assertEqual(final['decision'], 'release_on:2026-11-13' if mode=='world_change' else 'release_on:2026-11-16')
                        self.assertEqual(len(final['citations']),2 if mode=='world_change' else 1)
                    elif name == 'H0' and mode == 'world_change':
                        self.assertEqual(responses['responses'][-1]['decision'],'abstain')

    def test_provenance_conditions_and_alternative_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            for motif in (1,3,4):
                for condition in ('C0','C1','C2','C3'):
                    public, private = generate(motif=motif,variant=1,condition=condition)
                    for name in ('RR','RB'):
                        responses,_ = play(public,name,Path(tmp)/str(motif)/condition/name)
                        # Third independent approval survives even the false merge.
                        self.assertEqual(score(public,private,responses)['metrics']['justified_task_success']['numerator'],6)

    def test_unresolved_owner_conflict_and_private_truth_cannot_affect_answers(self):
        public,private=generate(motif=5,variant=4)
        with tempfile.TemporaryDirectory() as tmp:
            for name in METHODS:
                first,_=play(public,name,Path(tmp)/name/'a')
                private['truth']['owner_history'][-1]['value']='Riley'
                second,_=play(deepcopy(public),name,Path(tmp)/name/'b')
                self.assertEqual(first,second)
                self.assertEqual(first['responses'][-1]['decision'],'abstain')

    def test_readonly_audits_do_not_change_persisted_method_state(self):
        public,_=generate()
        with tempfile.TemporaryDirectory() as tmp:
            for name in METHODS:
                directory=Path(tmp)/name
                replay=Replay(public)
                for _ in range(4):
                    view=replay.advance_to_boundary()
                    response=execute(name,view,directory)['response']
                    replay.submit(response)
                before={p.name:p.read_bytes() for p in directory.iterdir()}
                result=execute(name,replay.view(),directory,audit_query=replay.view()['audit_queries'][0])
                after={p.name:p.read_bytes() for p in directory.iterdir()}
                self.assertEqual(before,after)
                self.assertTrue(all(c['stance']=='assert' for c in result['response']))
                self.assertTrue(result['counters'])

    def test_shared_report_room_is_valid_audit_support_after_release_correction(self):
        public, private = generate(motif=2)
        original = public['events'][0]['payload']['id']
        with tempfile.TemporaryDirectory() as tmp:
            for name in METHODS:
                replay = Replay(public)
                directory = Path(tmp)/name
                for _ in range(4):
                    view = replay.advance_to_boundary()
                    replay.submit(execute(name, view, directory)['response'])
                query = replay.view()['audit_queries'][0]
                result = execute(name, replay.view(), directory, audit_query=query)
                envelope = dict(schema_version=public['schema_version'], episode_id=public['episode_id'],
                                public_digest=digest(public), after_task_id=query['after_task_id'], claims=result['response'])
                self.assertEqual(score_audit(public, private, envelope)['valid_knowledge_retention']['rate'], 1)
                room = next(c for c in envelope['claims'] if c['key'] == 'room')
                room['citations'] = [original]
                self.assertEqual(score_audit(public, private, envelope)['valid_knowledge_retention']['rate'], 1)

    def test_private_fields_rejected_at_worker_boundary(self):
        public, private = generate()
        view = Replay(public).advance_to_boundary()
        view['truth'] = private['truth']
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Expected fields'):
                execute('RB', view, tmp)

    def test_budget_exhaustion_is_persistent_and_scored_not_dropped(self):
        public,private=generate()
        with tempfile.TemporaryDirectory() as tmp:
            for name in METHODS:
                responses,result=play(public,name,Path(tmp)/name,limit=1)
                self.assertTrue(result['exhausted'])
                self.assertEqual(len(responses['responses']),6)
                scored=score(public,private,responses)
                self.assertEqual(scored['metrics']['abstention']['numerator'],6)
                self.assertEqual(scored['metrics']['answerable_completion']['numerator'],0)

    def test_changed_prefix_or_method_checkpoint_rejected(self):
        public,_=generate()
        replay=Replay(public)
        view=replay.advance_to_boundary()
        with tempfile.TemporaryDirectory() as tmp:
            execute('LWW',view,tmp)
            altered=deepcopy(view)
            altered['events'][0]['payload']['text']='tampered'
            with self.assertRaisesRegex(ValueError,'prefix'):
                execute('LWW',altered,tmp)
            with self.assertRaisesRegex(ValueError,'checkpoint'):
                execute('RB',view,tmp)

    def test_actor_never_resolves_conflict_from_options_or_partial_ready(self):
        public,_=generate()
        tasks=[e['payload'] for e in public['events'] if e['kind']=='task']
        owner=dict(key='owner',value='Morgan',citations=['a'],status='supported')
        conflict=dict(key='owner',value='Riley',citations=['b'],status='supported')
        self.assertEqual(decide(tasks[1],[owner,conflict],Meter())['decision'],'abstain')
        self.assertEqual(decide(tasks[3],[owner],Meter())['decision'],'abstain')
        self.assertEqual(decide(dict(tasks[1],query='Unknown question'),[owner],Meter())['decision'],'abstain')

    def test_transport_failure_keeps_remaining_tasks_in_denominator(self):
        from compare import run_method
        public, private = generate()
        with tempfile.TemporaryDirectory() as tmp:
            with patch('compare.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 60)) as call:
                responses, audits, costs = run_method(public, 'RB', Path(tmp)/'RB')
            self.assertEqual(call.call_count, 1)
            self.assertTrue(costs['operational_failure'])
            self.assertTrue(costs['incomplete_work_counters'])
            self.assertEqual(len(audits), 2)
            scored = score(public, private, responses)
            self.assertEqual(scored['metrics']['abstention']['numerator'], 6)
            self.assertEqual(scored['metrics']['answerable_completion']['denominator'], 6)
            self.assertEqual(scored['metrics']['answerable_completion']['numerator'], 0)

    def test_cli_real_processes_manifest_costs_and_validation_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            public,private=generate()
            (root/'public.json').write_text(json.dumps(public))
            (root/'private.json').write_text(json.dumps(private))
            command=[sys.executable,str(EXPERIMENT/'compare.py'),'--public',str(root/'public.json'),
                     '--private',str(root/'private.json'),'--output',str(root/'result')]
            proc=subprocess.run(command,capture_output=True,text=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stderr)
            manifest=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual(manifest['status'],'complete')
            self.assertIn('src/holon/workspace/service.py',manifest['provenance']['source_hashes'])
            for name in METHODS:
                directory=root/'result'/name
                costs=json.loads((directory/'costs.json').read_text())
                self.assertFalse(costs['exhausted'])
                self.assertGreater(costs['peak_persisted_state_bytes'],0)
                self.assertEqual(sum(c['kind']=='audit' for c in costs['calls']),2)
                self.assertTrue((directory/'restart.json').exists())
                for path in directory.glob('*-view.json'):
                    view=json.loads(path.read_text())
                    self.assertNotIn('public_digest',view)
                    self.assertNotIn('truth',view)
                    self.assertNotIn('metadata',view)
                self.assertEqual(len(json.loads((directory/'responses.json').read_text())['responses']),6)
            refused=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(refused.returncode,2)
            public,private=generate(variant=4)
            (root/'public.json').write_text(json.dumps(public))
            (root/'private.json').write_text(json.dumps(private))
            command[-1]=str(root/'validation')
            refused=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(refused.returncode,2)
            self.assertFalse((root/'validation').exists())


if __name__ == '__main__':
    unittest.main()
