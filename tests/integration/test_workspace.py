import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from holon.workspace.service import Workspace


class WorkspaceTests(unittest.TestCase):
    def test_persistence_provenance_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            workspace = Workspace(path)
            pid = workspace.create_proposition('The door is closed', 'door at T0')
            self.assertEqual(workspace.inspect(pid)['status'], 'insufficient_evidence')
            first = workspace.add_report(pid, 'sensor A', 'closed at T0', 'supports')
            workspace.close()
            workspace = Workspace(path)
            self.assertEqual(workspace.inspect(pid)['status'], 'supported')
            second = workspace.add_report(pid, 'sensor B', 'open at T0', 'contradicts')
            workspace.close()
            workspace = Workspace(path)
            try:
                state = workspace.inspect(pid)
                self.assertEqual(state['status'], 'contested')
                self.assertEqual([r['status'] for r in state['history']], ['supported', 'contested'])
                self.assertEqual(state['history'][0]['evidence_ids'], [first['evidence_id']])
                self.assertEqual(state['history'][1]['evidence_ids'], [first['evidence_id'], second['evidence_id']])
                self.assertEqual([r['source'] for r in state['evidence']], ['sensor A', 'sensor B'])
                workspace.add_report(pid, 'sensor A', 'closed again', 'supports')
                self.assertEqual(workspace.inspect(pid)['status'], 'contested')
                before = workspace.inspect(pid)
                for args in [('missing', 'A', 'closed', 'supports'),
                             (pid, '', 'closed', 'supports'),
                             (pid, 'A', 'closed', 'invalid')]:
                    with self.assertRaises(ValueError):
                        workspace.add_report(*args)
                self.assertEqual(workspace.inspect(pid), before)
                for table in ['observations', 'evidence', 'revisions']:
                    self.assertEqual(workspace.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 3)
            finally:
                workspace.close()

    def test_transaction_rolls_back_if_revision_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Workspace(Path(directory) / 'state.sqlite3')
            try:
                pid = workspace.create_proposition('closed', 'T0')
                workspace.db.execute("CREATE TRIGGER reject_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
                import sqlite3
                with self.assertRaises(sqlite3.IntegrityError):
                    workspace.add_report(pid, 'A', 'closed', 'supports')
                self.assertEqual(workspace.inspect(pid)['history'], [])
                self.assertEqual(workspace.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 0)
                self.assertEqual(workspace.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0], 0)
            finally:
                workspace.close()

    def test_cli_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = [sys.executable, '-m', 'holon.cli', '--db', str(Path(directory) / 'cli.sqlite3')]
            def invoke(*args):
                return json.loads(subprocess.check_output(base + list(args), text=True))
            pid = invoke('propose', 'The door is closed', '--scope', 'door at T0')['proposition_id']
            invoke('report', pid, '--source', 'A', '--text', 'closed', '--relation', 'supports')
            self.assertEqual(invoke('inspect', pid)['status'], 'supported')
            invoke('report', pid, '--source', 'B', '--text', 'open', '--relation', 'contradicts')
            state = invoke('inspect', pid)
            self.assertEqual(state['status'], 'contested')
            self.assertEqual(len(state['history']), 2)
            result = subprocess.run(base + ['inspect', 'missing'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Unknown proposition', result.stderr)
