"""Simulator/scorer acceptance, not performance results for a research method."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / 'experiments' / '003-evidence-revision'
sys.path.insert(0, str(EXPERIMENT))

from revision_world.generate import catalogue, generate
from revision_world.replay import Replay
from revision_world.schema import VERSION, digest, validate_private, validate_public
from revision_world.scoring import score, score_audit


def envelope(public, rows):
    return dict(schema_version=VERSION, episode_id=public['episode_id'],
                public_digest=digest(public), responses=rows)


def gold_answers(public, private):
    # Privileged scorer test fixture only; never a method or public runner option.
    return envelope(public, [dict(task_id=g['task_id'],
                                  decision=g['physical_decision'] if g['answerable'] else 'abstain',
                                  citations=list(g['support_sets'][0]) if g['answerable'] else [])
                             for g in private['tasks']])


class RevisionWorldTests(unittest.TestCase):
    def test_catalogue_split_pairing_counts_and_reproduction(self):
        worlds = catalogue(42)
        self.assertEqual(len(worlds), 144)
        families = {}
        for public, private in worlds:
            validate_public(public)
            validate_private(private, public)
            metadata = private['metadata']
            families.setdefault(metadata['family_id'], []).append((public, private))
            sources = [e['payload'] for e in public['events'] if e['kind'] == 'source']
            self.assertGreaterEqual(len(sources), 12)
            self.assertLessEqual(len(sources), 24)
            self.assertGreaterEqual(len({s['key'] for source in sources for s in source['statements']}), 8)
            self.assertEqual(len(private['tasks']), 6)
            self.assertEqual(metadata['omissions']['removed'],
                             metadata['omissions']['copy'] + metadata['omissions']['premise'])
        self.assertEqual(len(families), 36)
        self.assertEqual(sum(v[0][1]['metadata']['split'] == 'development' for v in families.values()), 24)
        self.assertEqual(sum(v[0][1]['metadata']['split'] == 'validation' for v in families.values()), 12)
        for family in families.values():
            self.assertEqual({p['metadata']['condition'] for _, p in family}, {'C0', 'C1', 'C2', 'C3'})
            self.assertEqual(len({u['episode_id'] for u, _ in family}), 1)
            self.assertTrue(all(p['lineage'] == family[0][1]['lineage'] for _, p in family))
            self.assertEqual(len({p['metadata']['split'] for _, p in family}), 1)
        self.assertEqual(worlds, catalogue(42))
        self.assertNotEqual(digest(worlds[0][0]), digest(generate(43)[0]))

    def test_public_provenance_corruption_leaves_targets_truth_and_prose_intact(self):
        clean, clean_private = generate(42, 3, 2, 'C0')
        for condition in ('C1', 'C2', 'C3'):
            public, private = generate(42, 3, 2, condition)
            self.assertEqual(private['truth'], clean_private['truth'])
            self.assertEqual(private['tasks'], clean_private['tasks'])
            self.assertEqual(private['lineage'], clean_private['lineage'])
            self.assertGreater(private['metadata']['omissions']['removed'], 0)
            self.assertEqual(len(private['metadata']['false_merges']), int(condition == 'C3'))
            a, b = deepcopy(clean), deepcopy(public)
            for world in (a, b):
                for event in world['events']:
                    if event['kind'] == 'source':
                        event['payload']['dependencies'] = []
            self.assertEqual(a, b)

    def test_copy_depth_and_non_cosmetic_variants(self):
        # For each motif, variants change node/edge structure, not just names or dates.
        for motif in range(6):
            signatures = set()
            for variant in range(6):
                public, private = generate(42, motif, variant)
                depth = {}
                signature = []
                for event in public['events']:
                    if event['kind'] != 'source':
                        continue
                    p = event['payload']
                    depth[p['id']] = 1 + max((depth[e['parent']] for e in p['dependencies']), default=-1)
                    signature.append((tuple(s['key'] for s in p['statements']), len(p['dependencies'])))
                self.assertLessEqual(max(depth.values()), 3)
                signatures.add(tuple(signature))
            self.assertEqual(len(signatures), 6)

    def test_public_views_are_prefixes_and_detached_from_internal_state(self):
        public, private = generate()
        replay = Replay(public)
        initial = replay.view()
        self.assertEqual(initial['events'], [])
        self.assertEqual(initial['audit_queries'], [])
        first = replay.advance_to_boundary()
        self.assertIsNotNone(first['pending_task'])
        self.assertEqual(first['audit_queries'], [])
        boundary = private['tasks'][0]['boundary']
        self.assertEqual(first['events'], public['events'][:boundary + 1])
        future = public['events'][private['tasks'][2]['boundary'] - 1]['id']
        self.assertNotIn(future, json.dumps(first))
        for field in ('truth', 'lineage', 'physical_decision', 'answerable', 'support_sets',
                      'metadata', 'family_id', 'condition', 'public_digest'):
            self.assertNotIn(f'"{field}"', json.dumps(first))
        first['events'][0]['payload']['text'] = 'Tampered'
        first['rules'].clear()
        public['events'].clear()
        self.assertNotEqual(replay.view()['events'][0]['payload']['text'], 'Tampered')
        self.assertTrue(replay.view()['rules'])
        with self.assertRaises(ValueError):
            replay.advance()

    def test_checkpoint_replay_restart_and_no_grading_feedback(self):
        public, private = generate()
        uninterrupted, resumed = Replay(public), Replay(public)
        answers = {r['task_id']: r for r in gold_answers(public, private)['responses']}
        for _ in range(len(public['events']) + 6):
            a, b = uninterrupted.advance_to_boundary(), resumed.advance_to_boundary()
            self.assertEqual(a, b)
            if a['pending_task']:
                answer = answers[a['pending_task']['id']]
                self.assertIsNone(uninterrupted.submit(answer))
                self.assertIsNone(resumed.submit(answer))
            if a['restart_required']:
                with self.assertRaises(ValueError):
                    uninterrupted.advance()
                uninterrupted = Replay.restore(public, uninterrupted.checkpoint())
            resumed = Replay.restore(public, json.loads(json.dumps(resumed.checkpoint())))
            if a['complete']:
                break
        self.assertTrue(resumed.view()['complete'])
        self.assertEqual(uninterrupted.responses(), resumed.responses())
        self.assertEqual(score(public, private, resumed.responses())['metrics']['justified_task_success']['rate'], 1)

    def test_checkpoint_and_response_validation(self):
        public, _ = generate()
        replay = Replay(public)
        task = replay.advance_to_boundary()['pending_task']
        before = replay.checkpoint()
        invalid = [dict(task_id=task['id'], decision='unknown', citations=[]),
                   dict(task_id='wrong', decision='abstain', citations=[]),
                   dict(task_id=task['id'], decision='abstain', citations=['invented']),
                   dict(task_id=task['id'], decision=task['options'][0], citations=[], truth='leak')]
        for value in invalid:
            with self.assertRaises(ValueError):
                replay.submit(value)
            self.assertEqual(replay.checkpoint(), before)
        for change in ({'cursor': -1}, {'cursor': True}, {'cursor': len(public['events'])},
                       {'public_digest': 'wrong'}, {'responses': [{'bad': 'value'}]}):
            broken = {**before, **change}
            with self.assertRaises(ValueError):
                Replay.restore(public, broken)
        other, _ = generate(43)
        with self.assertRaises(ValueError):
            Replay.restore(other, before)

    def test_scorer_acceptance_and_all_abstain_does_not_win(self):
        public, private = generate()
        answers = gold_answers(public, private)
        perfect = score(public, private, answers)
        self.assertEqual(perfect['metrics']['justified_task_success']['rate'], 1)
        abstain = envelope(public, [dict(task_id=g['task_id'], decision='abstain', citations=[])
                                   for g in private['tasks']])
        result = score(public, private, abstain)
        self.assertEqual(result['metrics']['obsolete_action']['rate'], 0)
        self.assertEqual(result['metrics']['answerable_completion']['rate'], 0)
        self.assertEqual(result['metrics']['unresolved_success']['rate'], None)
        self.assertEqual(score(public, private, envelope(public, []))['metrics']['missing']['rate'], 1)

    def test_unsupported_guesses_stale_citations_and_citation_stuffing(self):
        public, private = generate()
        answers = gold_answers(public, private)
        answers['responses'][2]['citations'] = []
        row = score(public, private, answers)['rows'][2]
        self.assertTrue(row['physical_correct'])
        self.assertTrue(row['unsupported_correct'])
        self.assertFalse(row['justified_success'])
        # The previous release report is available, but no longer justifies current preparation.
        answers['responses'][2]['citations'] = private['tasks'][0]['support_sets'][0]
        self.assertFalse(score(public, private, answers)['rows'][2]['justified_success'])
        answers = gold_answers(public, private)
        answers['responses'][2]['citations'] += private['tasks'][0]['support_sets'][0]
        self.assertFalse(score(public, private, answers)['rows'][2]['justified_success'])
        answers['responses'][2]['decision'] = 'prepare_on:2026-11-12'
        self.assertTrue(score(public, private, answers)['rows'][2]['obsolete_action'])

    def test_future_and_unknown_citations_never_justify_actions(self):
        public, private = generate()
        answers = gold_answers(public, private)
        later_source = private['tasks'][2]['support_sets'][0][0]
        for citation in (later_source, 'invented'):
            answers['responses'][0]['citations'] = [citation]
            result = score(public, private, answers)['rows'][0]
            self.assertEqual(result['unavailable_citations'], [citation])
            self.assertFalse(result['justified_success'])

    def test_and_or_support_and_unaffected_shared_report(self):
        public, private = generate(motif=1, variant=2)
        answers = gold_answers(public, private)
        choices = private['tasks'][3]['support_sets']
        self.assertGreater(len(choices), 1)
        for choice in choices:
            answers['responses'][3]['citations'] = choice
            self.assertTrue(score(public, private, answers)['rows'][3]['justified_success'])
        answers['responses'][3]['citations'] = choices[0][:1]
        self.assertFalse(score(public, private, answers)['rows'][3]['justified_success'])
        public, private = generate(motif=2)
        answers = gold_answers(public, private)
        answers['responses'][5]['citations'] = private['tasks'][0]['support_sets'][0]
        self.assertTrue(score(public, private, answers)['rows'][5]['justified_success'])

    def test_correction_and_world_change_have_different_historical_answers(self):
        correction, cp = generate(motif=5, variant=0, update_kind='source_correction')
        change, wp = generate(motif=5, variant=0, update_kind='world_change')
        boundary = cp['tasks'][1]['boundary'] + 1
        self.assertEqual(correction['events'][:boundary], change['events'][:boundary])
        self.assertEqual(cp['tasks'][5]['physical_decision'], 'release_on:2026-11-16')
        self.assertEqual(wp['tasks'][5]['physical_decision'], 'release_on:2026-11-13')
        self.assertEqual(cp['tasks'][2]['physical_decision'], wp['tasks'][2]['physical_decision'])
        self.assertEqual(len(cp['truth']['release_history']), 1)
        self.assertEqual(len(wp['truth']['release_history']), 2)

    def test_unresolved_worlds_identical_public_inputs_and_distinct_hidden_truth(self):
        public, private = generate(motif=5, variant=4)
        other = deepcopy(private)
        other['truth']['owner_history'][-1]['value'] = 'Riley'
        other['tasks'][-1]['physical_decision'] = 'owner:Riley'
        self.assertEqual(other['public_digest'], private['public_digest'])
        answers = gold_answers(public, private)
        self.assertEqual(answers['responses'][-1]['decision'], 'abstain')
        self.assertTrue(score(public, private, answers)['rows'][-1]['justified_success'])
        self.assertTrue(score(public, other, answers)['rows'][-1]['justified_success'])
        answers['responses'][-1] = dict(task_id=private['tasks'][-1]['task_id'], decision='owner:Morgan',
                                       citations=private['tasks'][1]['support_sets'][0])
        a, b = score(public, private, answers)['rows'][-1], score(public, other, answers)['rows'][-1]
        self.assertTrue(a['physical_correct'])
        self.assertFalse(b['physical_correct'])
        self.assertFalse(a['justified_success'])
        self.assertFalse(b['justified_success'])

    def test_private_binding_bad_support_and_unknown_public_fields(self):
        public, private = generate()
        bad = deepcopy(public)
        bad['truth'] = private['truth']
        with self.assertRaises(ValueError):
            validate_public(bad)
        bad = deepcopy(public)
        bad['events'][0]['payload']['dependencies'] = [dict(parent='future', kind='copy')]
        with self.assertRaises(ValueError):
            validate_public(bad)
        bad = deepcopy(private)
        bad['tasks'][0]['support_sets'] = private['tasks'][2]['support_sets']
        with self.assertRaises(ValueError):
            validate_private(bad, public)
        other_public, _ = generate(condition='C1')
        with self.assertRaises(ValueError):
            validate_private(private, other_public)
        bad_answers = gold_answers(public, private)
        bad_answers['responses'].append(bad_answers['responses'][0])
        with self.assertRaises(ValueError):
            score(public, private, bad_answers)

    def test_read_only_control_audit(self):
        public, private = generate()
        audit = private['audits'][0]
        response = dict(schema_version=VERSION, episode_id=public['episode_id'], public_digest=digest(public),
                        after_task_id=audit['after_task_id'],
                        claims=[dict(key=c['key'], value=c['value'], stance='assert', citations=c['support_sets'][0])
                                for c in audit['claims']])
        before = digest([public, private, response])
        self.assertEqual(score_audit(public, private, response)['valid_knowledge_retention']['rate'], 1)
        self.assertEqual(digest([public, private, response]), before)
        response['claims'][0]['stance'] = 'unresolved'
        self.assertEqual(score_audit(public, private, response)['valid_knowledge_retention']['rate'], .75)


class RevisionWorldCLITests(unittest.TestCase):
    def invoke(self, *args, optimized=False):
        return subprocess.run([sys.executable, *(['-O'] if optimized else []), str(EXPERIMENT / 'run.py'),
                               *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=30,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))

    def test_generate_restart_across_processes_and_offline_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bundle'
            result = self.invoke('generate', '--output', bundle)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = json.loads((bundle / 'manifest.json').read_text())['episodes'][0]
            public_path, private_path = bundle / entry['public'], bundle / entry['private']
            public, private = json.loads(public_path.read_text()), json.loads(private_path.read_text())
            # Public replay works with no private file at the referenced bundle location.
            private_path.unlink()
            previous = None
            answer_path = None
            saw_restart = False
            for index in range(9):
                out = root / f'step-{index}'
                args = ['replay', '--public', public_path, '--output', out]
                if previous:
                    args += ['--checkpoint', previous / 'checkpoint.json']
                if answer_path:
                    args += ['--response', answer_path]
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                view = json.loads((out / 'view.json').read_text())
                saw_restart |= view['restart_required']
                previous, answer_path = out, None
                if view['pending_task']:
                    answer_path = root / f'answer-{index}.json'
                    answer_path.write_text(json.dumps(dict(task_id=view['pending_task']['id'],
                                                          decision='abstain', citations=[])))
                if view['complete']:
                    break
            self.assertTrue(view['complete'])
            self.assertTrue(saw_restart)
            private_path.write_text(json.dumps(private))
            out = root / 'score'
            result = self.invoke('score', '--public', public_path, '--private', private_path,
                                 '--responses', previous / 'responses.json', '--output', out)
            self.assertEqual(result.returncode, 0, result.stderr)
            scores = json.loads((out / 'scores.json').read_text())
            self.assertEqual(scores['metrics']['answerable_completion']['rate'], 0)
            self.assertEqual(scores['metrics']['obsolete_action']['rate'], 0)
            refused = self.invoke('generate', '--output', bundle)
            self.assertEqual(refused.returncode, 2)

    def test_malformed_input_rejected_under_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public, private = generate()
            public['truth'] = private['truth']
            path = root / 'bad.json'
            path.write_text(json.dumps(public))
            result = self.invoke('replay', '--public', path, '--output', root / 'out', optimized=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
