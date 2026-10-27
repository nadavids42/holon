import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from holon.cli import main
from holon.inference.inference import Interpretation
from holon.workspace.service import Workspace


class ReinterpretationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite3'
        self.w = Workspace(self.path)
        self.addCleanup(lambda: self.w.close())
        self.pid = self.w.create_proposition('Door closed', 'T0')
        self.other = self.w.create_proposition('Door locked', 'T0')
        self.old = self.w.add_report(self.pid, 'A', 'door open', 'supports',
            Interpretation('supports', 'old model reason', 'old:model'), mass=.4,
            cluster_id='shared', cluster_actor='Nick', cluster_reason='same event')
        self.w.link_observation(self.old['observation_id'], self.other, 'supports')

    def test_reinterpret_retains_observation_history_impact_and_retry(self):
        original = self.w.inspect_observation(self.old['observation_id'])['observation']
        kwargs = dict(relation='contradicts', actor='Nick', reason='Incorrect relation', event_key='retry')
        result = self.w.reinterpret_evidence(self.old['evidence_id'], **kwargs)
        self.assertEqual(result, self.w.reinterpret_evidence(self.old['evidence_id'], **kwargs))
        for change in ({'reason': 'changed'}, {'mass': .4}, {'relation': 'supports'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.w.reinterpret_evidence(self.old['evidence_id'], **(kwargs | change))
        with self.assertRaises(ValueError):
            self.w.reinterpret_evidence(self.old['evidence_id'], 'contradicts', 'Nick', 'again')
        state = self.w.inspect(self.pid)
        self.assertEqual(state['status'], 'opposed')
        old, new = state['evidence']
        self.assertFalse(old['active'])
        self.assertEqual(old['reason'], 'old model reason')
        self.assertEqual(old['withdrawal_reason'], 'Incorrect relation')
        self.assertEqual(old['replacement_evidence_id'], new['id'])
        self.assertEqual(new['observation_id'], old['observation_id'])
        self.assertIsNone(new['model'])
        self.assertEqual(state['history'][0]['evidence_ids'], [old['id']])
        self.assertEqual(state['history'][1]['evidence_ids'], [new['id']])
        projection = self.w.project(self.pid)['readout']
        self.assertEqual((projection['effective_support'], projection['effective_contradiction']), (0, .4))
        meta = self.w.project(self.pid)['evidence_metadata']
        self.assertEqual({(m['cluster_id'], m['cluster_actor'], m['cluster_reason']) for m in meta},
                         {('shared:shared', 'Nick', 'same event')})
        self.assertEqual(self.w.inspect(self.other)['status'], 'supported')
        self.assertEqual(self.w.inspect_observation(self.old['observation_id'])['observation'], original)
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 1)
        self.w.close()
        self.w = Workspace(self.path)
        self.assertEqual(self.w.inspect(self.pid), state)
        revised = self.w.reinterpret_evidence(new['id'], 'supports', 'Nick', 'Second change', mass=.2)
        self.assertEqual(revised['status'], 'supported')
        self.assertEqual(self.w.project(self.pid)['readout']['effective_support'], .2)

    def test_failure_at_each_write_rolls_back(self):
        for table in ('evidence', 'interpretations', 'evidence_impact', 'withdrawals', 'revisions'):
            with self.subTest(table=table):
                before = self.w.inspect(self.pid, projection_policy='binary-beta-v1')
                self.w.db.execute(f"CREATE TRIGGER fail_test BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'injected'); END")
                with self.assertRaises(sqlite3.IntegrityError):
                    self.w.reinterpret_evidence(self.old['evidence_id'], 'contradicts', 'Nick', 'reason',
                                                interpretation=Interpretation('contradicts', 'new reason', 'model'))
                self.assertEqual(self.w.inspect(self.pid, projection_policy='binary-beta-v1'), before)
                self.w.db.execute('DROP TRIGGER fail_test')

    def test_missing_impact_and_migration_assumptions_remain_approximate(self):
        oid = self.w.record_observation('B', 'report')
        with self.w.db:
            self.w.db.execute('INSERT INTO evidence VALUES (?, ?, ?, ?)', ('legacy', oid, self.pid, 'supports'))
        before = self.w.inspect(self.pid)
        with self.assertRaisesRegex(ValueError, 'metadata'):
            self.w.reinterpret_evidence('legacy', 'contradicts', 'Nick', 'reason')
        self.assertEqual(self.w.inspect(self.pid), before)
        self.w.migrate_impacts(self.pid, 'Nick', 'explicit assumptions')
        result = self.w.reinterpret_evidence('legacy', 'contradicts', 'Nick', 'reason')
        metadata = self.w.project(self.pid)
        self.assertEqual(metadata['replay_coverage'], 'replay_approximate')
        replacement = next(row for row in metadata['evidence_metadata'] if row['id'] == result['replacement_evidence_id'])
        self.assertIsNotNone(replacement['migration_id'])

    def test_duplicate_active_link_and_retry_namespace(self):
        other_observation = self.w.record_observation('A', 'another report')
        self.w.link_observation(other_observation, self.pid, 'supports', event_key='used')
        with self.assertRaisesRegex(ValueError, 'Event key'):
            self.w.reinterpret_evidence(self.old['evidence_id'], 'contradicts', 'Nick', 'reason', event_key='used')
        with self.w.db:
            self.w.db.execute('INSERT INTO evidence VALUES (?, ?, ?, ?)', ('duplicate', self.old['observation_id'], self.pid, 'supports'))
        before = self.w.inspect(self.pid)
        with self.assertRaisesRegex(ValueError, 'Another active'):
            self.w.reinterpret_evidence(self.old['evidence_id'], 'contradicts', 'Nick', 'reason')
        self.assertEqual(self.w.inspect(self.pid), before)

    def test_cli_manual_and_model_preview(self):
        base = [sys.executable, '-m', 'holon.cli', '--db', str(self.path)]
        result = json.loads(subprocess.check_output(base + ['reinterpret', self.old['evidence_id'], '--actor', 'Nick',
                            '--reason', 'fix', '--relation', 'contradicts', '--event-key', 'manual'], text=True))
        new = result['replacement_evidence_id']
        argv = ['holon', '--db', str(self.path), 'reinterpret', new, '--actor', 'Nick', '--reason', 'review', '--model']
        proposal = Interpretation('supports', 'model rationale', 'test:model')
        def run(answer='y', result=proposal, side_effect=None):
            with patch('sys.argv', argv), patch('builtins.input', return_value=answer), \
                 patch('holon.cli.OllamaInterpreter.interpret', return_value=result, side_effect=side_effect), \
                 patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
                main()
        before = self.w.inspect(self.pid)
        run('n')
        run('y', Interpretation('uncertain', 'not clear', 'test:model'))
        with self.assertRaises(SystemExit):
            run(side_effect=OSError('offline'))
        self.assertEqual(self.w.inspect(self.pid), before)
        run()
        evidence = self.w.inspect(self.pid)['evidence']
        self.assertEqual(evidence[-1]['model'], 'test:model')
        self.assertEqual(evidence[-1]['reason'], 'model rationale')
        self.assertEqual(evidence[-2]['withdrawal_reason'], 'review')
        self.assertEqual(evidence[-1]['observation_id'], self.old['observation_id'])

    def test_change_during_model_preview_is_revalidated(self):
        argv = ['holon', '--db', str(self.path), 'reinterpret', self.old['evidence_id'],
                '--actor', 'Nick', '--reason', 'review', '--model']
        def competing(*args):
            self.w.withdraw_evidence(self.old['evidence_id'], 'Nick', 'withdrawn while reviewing')
            return Interpretation('contradicts', 'model reason', 'test:model')
        with patch('sys.argv', argv), patch('builtins.input', return_value='y'), \
             patch('holon.cli.OllamaInterpreter.interpret', side_effect=competing), \
             patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main()
        state = self.w.inspect(self.pid)
        self.assertEqual(len(state['evidence']), 1)
        self.assertEqual(state['status'], 'insufficient_evidence')


if __name__ == '__main__':
    unittest.main()
