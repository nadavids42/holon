"""Evidence lifecycle: retained provenance, atomic correction, and old stores."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from holon.inference.inference import Interpretation
from holon.workspace.service import Workspace


class WithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.sqlite3'
        self.workspace = Workspace(self.path)
        self.addCleanup(lambda: self.workspace.close())
        self.pid = self.workspace.create_proposition('Door closed', 'T0')

    def restart(self):
        self.workspace.close()
        self.workspace = Workspace(self.path)

    def test_withdrawal_recovery_and_restart(self):
        positive = self.workspace.add_report(self.pid, 'A', 'closed', 'supports')
        negative = self.workspace.add_report(self.pid, 'B', 'open', 'contradicts',
                                           Interpretation('contradicts', 'Opposite state', 'test'))
        originals = self.workspace.inspect(self.pid)['evidence']
        self.workspace.withdraw_evidence(negative['evidence_id'], 'Nick', 'Wrong interpretation')
        self.restart()
        state = self.workspace.inspect(self.pid)
        self.assertEqual(state['status'], 'supported')
        self.assertEqual([r['status'] for r in state['history']],
                         ['supported', 'contested', 'supported'])
        self.assertEqual(state['history'][-1]['evidence_ids'], [positive['evidence_id']])
        self.assertTrue(state['evidence'][0]['active'])
        withdrawn = state['evidence'][1]
        self.assertFalse(withdrawn['active'])
        self.assertEqual(withdrawn['withdrawal_actor'], 'Nick')
        self.assertEqual(withdrawn['withdrawal_reason'], 'Wrong interpretation')
        self.assertIsNotNone(withdrawn['withdrawn_at'])
        for old, current in zip(originals, state['evidence']):
            for key in ('id', 'observation_id', 'source', 'report', 'recorded_at',
                        'relation', 'model', 'reason', 'prompt_version'):
                self.assertEqual(current[key], old[key])
        self.workspace.withdraw_evidence(positive['evidence_id'], 'Nick', 'Unusable sensor')
        self.restart()
        state = self.workspace.inspect(self.pid)
        self.assertEqual(state['status'], 'insufficient_evidence')
        self.assertEqual(state['history'][-1]['evidence_ids'], [])
        self.assertEqual(len(state['evidence']), 2)

    def test_correction_preserves_original_and_links_replacement(self):
        old = self.workspace.add_report(self.pid, 'B', '  open  ', 'contradicts')
        result = self.workspace.withdraw_evidence(old['evidence_id'], 'Nick', 'Misread',
                                                 source='B', report='  closed  ', relation='supports')
        self.restart()
        state = self.workspace.inspect(self.pid)
        self.assertEqual(state['status'], 'supported')
        original, replacement = state['evidence']
        self.assertEqual(original['report'], '  open  ')
        self.assertFalse(original['active'])
        self.assertEqual(original['replacement_evidence_id'], replacement['id'])
        self.assertEqual(replacement['id'], result['replacement_evidence_id'])
        self.assertEqual(replacement['observation_id'], result['observation_id'])
        self.assertEqual(replacement['report'], '  closed  ')
        self.assertTrue(replacement['active'])
        self.assertEqual(len(state['history']), 2)
        self.assertEqual(state['history'][-1]['evidence_ids'], [replacement['id']])

    def test_invalid_and_repeated_withdrawals_leave_state_unchanged(self):
        old = self.workspace.add_report(self.pid, 'A', 'closed', 'supports')['evidence_id']
        cases = [('missing', 'Nick', 'reason', {}), (old, '', 'reason', {}),
                 (old, 'Nick', ' ', {}), (old, 'Nick', 'reason', {'source': 'A'}),
                 (old, 'Nick', 'reason', {'report': ' ', 'source': 'A', 'relation': 'supports'}),
                 (old, 'Nick', 'reason', {'report': 'open', 'source': '', 'relation': 'contradicts'}),
                 (old, 'Nick', 'reason', {'report': 'open', 'source': 'A', 'relation': 'invalid'})]
        before = self.workspace.inspect(self.pid)
        for evidence_id, actor, reason, correction in cases:
            with self.subTest(correction=correction, actor=actor, reason=reason):
                with self.assertRaises(ValueError):
                    self.workspace.withdraw_evidence(evidence_id, actor, reason, **correction)
                self.assertEqual(self.workspace.inspect(self.pid), before)
        self.workspace.withdraw_evidence(old, 'Nick', 'reason')
        before = self.workspace.inspect(self.pid)
        with self.assertRaises(ValueError):
            self.workspace.withdraw_evidence(old, 'Nick', 'again')
        self.assertEqual(self.workspace.inspect(self.pid), before)

    def test_correction_rolls_back_after_replacement_creation(self):
        old = self.workspace.add_report(self.pid, 'A', 'open', 'contradicts')['evidence_id']
        before = self.workspace.inspect(self.pid)
        self.workspace.db.execute("CREATE TRIGGER reject_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.workspace.withdraw_evidence(old, 'Nick', 'Misread', source='A',
                                             report='closed', relation='supports')
        self.restart()
        self.assertEqual(self.workspace.inspect(self.pid), before)
        for table, expected in [('observations', 1), ('evidence', 1), ('withdrawals', 0), ('revisions', 1)]:
            self.assertEqual(self.workspace.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], expected)

    def test_original_schema_migration_retains_history_and_is_repeatable(self):
        # Literal old schema, independent of the schema being tested.
        path = Path(self.directory.name) / 'legacy.sqlite3'
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE propositions (id TEXT PRIMARY KEY, claim TEXT NOT NULL, scope TEXT NOT NULL);
                CREATE TABLE observations (id TEXT PRIMARY KEY, source TEXT NOT NULL, report TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE TABLE evidence (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id), proposition_id TEXT NOT NULL REFERENCES propositions(id), relation TEXT NOT NULL CHECK(relation IN ('supports','contradicts')));
                CREATE TABLE revisions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposition_id TEXT NOT NULL REFERENCES propositions(id), status TEXT NOT NULL CHECK(status IN ('supported','opposed','contested')), evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL);
                INSERT INTO propositions VALUES ('p','closed','T0');
                INSERT INTO observations VALUES ('o','A','closed','2026-10-24T00:00:00+00:00');
                INSERT INTO evidence VALUES ('e','o','p','supports');
                INSERT INTO revisions VALUES (7,'p','supported','["e"]','2026-10-24T00:00:00+00:00','presence-v1');
            """)
        for attempt in range(2):
            workspace = Workspace(path)
            try:
                state = workspace.inspect('p')
                self.assertEqual(state['history'][0]['sequence'], 7)
                self.assertEqual(state['history'][0]['policy'], 'presence-v1')
                self.assertEqual(state['evidence'][0]['report'], 'closed')
                if attempt == 0:
                    workspace.withdraw_evidence('e', 'Nick', 'Unreliable')
                state = workspace.inspect('p')
                self.assertEqual(state['status'], 'insufficient_evidence')
                self.assertEqual(state['history'][-1]['sequence'], 8)
                self.assertEqual(workspace.db.execute('PRAGMA foreign_key_check').fetchall(), [])
            finally:
                workspace.close()

    def test_cli_correction_and_withdrawal_across_processes(self):
        base = [sys.executable, '-m', 'holon.cli', '--db', str(self.path)]
        def invoke(*args):
            return json.loads(subprocess.check_output(base + list(args), text=True))
        old = invoke('report', self.pid, '--source', 'A', '--text', 'open', '--relation', 'contradicts')
        correction = invoke('correct', old['evidence_id'], '--actor', 'Nick', '--reason', 'Misread',
                            '--source', 'A', '--text', 'closed', '--relation', 'supports')
        self.assertEqual(correction['status'], 'supported')
        invoke('withdraw', correction['replacement_evidence_id'], '--actor', 'Nick', '--reason', 'Invalid')
        self.assertEqual(invoke('inspect', self.pid)['status'], 'insufficient_evidence')
        failed = subprocess.run(base + ['withdraw', old['evidence_id'], '--actor', 'Nick', '--reason', 'Again'],
                                capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn('already withdrawn', failed.stderr)
