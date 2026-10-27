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


class ObservationReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.w = Workspace(self.path)
        self.addCleanup(lambda: self.w.close())
        self.p = self.w.create_proposition('Door closed', 'T0')
        self.q = self.w.create_proposition('Door locked', 'T0')

    def test_shared_observation_retry_and_restart(self):
        oid = self.w.record_observation('A', '  closed and locked  ', observed_at='2026-10-26T12:00:00Z')
        self.assertEqual(self.w.inspect_observation(oid)['links'], [])
        first = self.w.link_observation(oid, self.p, 'supports', event_key='event')
        self.assertEqual(first, self.w.link_observation(oid, self.p, 'supports', event_key='event'))
        second = self.w.link_observation(oid, self.q, 'supports', mass=.5)
        self.assertNotEqual(first['evidence_id'], second['evidence_id'])
        self.assertEqual(self.w.project(self.p)['readout']['effective_support'], 1)
        self.assertEqual(self.w.project(self.q)['readout']['effective_support'], .5)
        self.w.close()
        self.w = Workspace(self.path)
        state = self.w.inspect_observation(oid)
        self.assertEqual(state['observation']['report'], '  closed and locked  ')
        self.assertEqual(state['observation']['observed_at'], '2026-10-26T12:00:00.000000+00:00')
        self.assertEqual({link['proposition_id'] for link in state['links']}, {self.p, self.q})
        self.assertTrue(all(link['active'] for link in state['links']))
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 1)
        self.assertEqual(self.w.inspect(self.q)['evidence'][0]['observation_id'], oid)
        duplicate = self.w.record_observation('A', '  closed and locked  ')
        self.assertNotEqual(oid, duplicate)

    def test_invalid_duplicate_key_and_legacy_duplicates(self):
        oid = self.w.record_observation('A', 'closed')
        self.w.link_observation(oid, self.p, 'supports', event_key='one')
        before = self.w.inspect(self.p)
        for args in [(oid, self.p, 'supports'), (oid, self.p, 'contradicts'),
                     ('missing', self.p, 'supports'), (oid, 'missing', 'supports'),
                     (oid, self.q, 'invalid')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.w.link_observation(*args)
        with self.assertRaises(ValueError):
            self.w.link_observation(oid, self.p, 'contradicts', event_key='one')
        with self.assertRaises(ValueError):
            self.w.add_report(self.p, 'A', 'closed', 'supports', event_key='one')
        self.assertEqual(self.w.inspect(self.p), before)
        # Legacy duplicate links remain inspectable and can be withdrawn individually.
        with self.w.db:
            self.w.db.execute('INSERT INTO evidence VALUES (?, ?, ?, ?)', ('legacy', oid, self.p, 'contradicts'))
        self.assertEqual(len(self.w.inspect_observation(oid)['links']), 2)
        self.w.withdraw_evidence('legacy', 'Nick', 'Old duplicate')
        self.assertFalse(self.w.inspect_observation(oid)['links'][1]['active'])
        self.assertTrue(self.w.inspect_observation(oid)['links'][0]['active'])

    def test_failure_rolls_back_link_and_keeps_observation(self):
        oid = self.w.record_observation('A', 'closed')
        before = self.w.inspect(self.p)
        self.w.db.execute("CREATE TRIGGER fail_link_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'fail'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.w.link_observation(oid, self.p, 'supports', interpretation=Interpretation('supports', 'match', 'model'))
        self.assertEqual(self.w.inspect(self.p), before)
        self.assertEqual(self.w.inspect_observation(oid)['links'], [])
        for table in ('evidence', 'evidence_impact', 'interpretations', 'revisions'):
            self.assertEqual(self.w.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_existing_observation_interpretation_accept_decline_and_revalidation(self):
        oid = self.w.record_observation('A', 'closed')
        argv = ['holon', '--db', str(self.path), 'interpret-observation', oid, self.p]
        proposal = Interpretation('supports', 'matches', 'test:model')
        def run(answer, result=proposal, side_effect=None):
            with patch('sys.argv', argv), patch('builtins.input', return_value=answer), \
                 patch('holon.cli.OllamaInterpreter.interpret', return_value=result, side_effect=side_effect), \
                 patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
                main()
        run('n')
        run('y', Interpretation('uncertain', 'unknown', 'test:model'))
        self.assertEqual(self.w.inspect_observation(oid)['links'], [])
        run('y')
        evidence = self.w.inspect(self.p)['evidence'][0]
        self.assertEqual((evidence['observation_id'], evidence['model'], evidence['reason']), (oid, 'test:model', 'matches'))
        with self.assertRaises(SystemExit) as error:
            run('y')
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(len(self.w.inspect_observation(oid)['links']), 1)

    def test_model_failure_and_link_created_during_preview(self):
        oid = self.w.record_observation('A', 'closed')
        argv = ['holon', '--db', str(self.path), 'interpret-observation', oid, self.p]
        with patch('sys.argv', argv), patch('holon.cli.OllamaInterpreter.interpret', side_effect=OSError('offline')), \
             patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main()
        self.assertEqual(self.w.inspect_observation(oid)['links'], [])
        def concurrent_link(*args):
            self.w.link_observation(oid, self.p, 'contradicts')
            return Interpretation('supports', 'match', 'test')
        with patch('sys.argv', argv), patch('holon.cli.OllamaInterpreter.interpret', side_effect=concurrent_link), \
             patch('builtins.input', return_value='y'), patch('sys.stdout', new_callable=io.StringIO), \
             patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                main()
        links = self.w.inspect_observation(oid)['links']
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['relation'], 'contradicts')

    def test_cli_across_processes(self):
        base = [sys.executable, '-m', 'holon.cli', '--db', str(self.path)]
        def invoke(*args):
            return json.loads(subprocess.check_output(base + list(args), text=True))
        oid = invoke('observe', '--source', 'A', '--text', 'closed', '--observed-at', '2026-10-26T12:00:00Z')['observation_id']
        self.assertEqual(invoke('link', oid, self.p, '--relation', 'supports')['observation_id'], oid)
        self.assertEqual(invoke('link', oid, self.q, '--relation', 'contradicts')['status'], 'opposed')
        self.assertEqual(len(invoke('inspect-observation', oid)['links']), 2)


if __name__ == '__main__':
    unittest.main()
