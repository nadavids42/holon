import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from holon.workspace.service import Workspace


class PersistentProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.w = Workspace(self.path)
        self.addCleanup(lambda: self.w.close())
        self.pid = self.w.create_proposition('Closed', 'T0')

    def test_retry_clusters_and_read_only_restart(self):
        first = self.w.add_report(self.pid, 'A', 'closed', 'supports', mass=.75, event_key='event1')
        self.assertEqual(self.w.add_report(self.pid, 'A', 'closed', 'supports', mass=.75, event_key='event1'), first)
        with self.assertRaises(ValueError):
            self.w.add_report(self.pid, 'A', 'changed', 'supports', event_key='event1')
        self.w.add_report(self.pid, 'A', 'closed again', 'supports', mass=.75)
        before = self.w.db.total_changes
        result = self.w.project(self.pid)
        self.assertEqual(self.w.db.total_changes, before)
        self.assertEqual(result['replay_coverage'], 'replay_complete')
        self.assertEqual(result['readout']['raw_support'], 1.5)
        self.assertEqual(result['readout']['effective_support'], 1)
        self.assertEqual(len(self.w.inspect(self.pid)['history']), 2)
        self.assertEqual(self.w.inspect(self.pid, projection_policy='binary-beta-v1')['projection'], result)
        self.w.close()
        self.w = Workspace(self.path)
        self.assertEqual(self.w.project(self.pid), result)
        with self.assertRaises(sqlite3.IntegrityError):
            self.w.db.execute("UPDATE projection_policies SET digest='changed'")
        self.w.db.rollback()

    def test_shared_lineage_and_correction(self):
        kwargs = dict(cluster_id='copied-report', cluster_actor='Nick', cluster_reason='Same document')
        first = self.w.add_report(self.pid, 'A', 'closed', 'supports', **kwargs)
        self.w.add_report(self.pid, 'B', 'closed', 'supports', **kwargs)
        self.assertEqual(self.w.project(self.pid)['readout']['effective_support'], 1)
        self.w.withdraw_evidence(first['evidence_id'], 'Nick', 'Misread', report='open', source='C', relation='contradicts', mass=.5)
        result = self.w.project(self.pid)['readout']
        self.assertEqual(len(result['clusters']), 1)
        self.assertEqual(result['effective_contradiction'], .5)
        for item in self.w.inspect(self.pid)['evidence']:
            if item['active']:
                self.w.withdraw_evidence(item['id'], 'Nick', 'Invalid')
        self.assertEqual(self.w.project(self.pid)['readout']['mean'], .5)

    def test_legacy_copy_migration_and_assumption_annotation(self):
        # Rehearse on a copy of a legacy store, never the user's runtime store.
        original = Path(self.temp.name) / 'legacy.sqlite3'
        with sqlite3.connect(original) as db:
            from holon.workspace.storage import SCHEMA
            db.executescript(SCHEMA)
            db.execute("INSERT INTO propositions VALUES ('p','closed','T0')")
            db.execute("INSERT INTO observations VALUES ('o','A','closed','legacy-time')")
            db.execute("INSERT INTO evidence VALUES ('e','o','p','supports')")
        copy = Path(self.temp.name) / 'copy.sqlite3'
        with sqlite3.connect(original) as src, sqlite3.connect(copy) as dst:
            src.backup(dst)
        w = Workspace(copy)
        try:
            state = w.project('p')
            self.assertEqual(state['replay_coverage'], 'replay_incomplete')
            self.assertIsNone(state['readout'])
            self.assertEqual(state['missing_metadata_ids'], ['e'])
            self.assertEqual(w.migrate_impacts('p', 'Nick', 'Experimental replay')['annotated_count'], 1)
            self.assertEqual(w.migrate_impacts('p', 'Nick', 'Retry')['annotated_count'], 0)
            self.assertEqual(w.project('p')['replay_coverage'], 'replay_approximate')
            self.assertEqual(w.project('p')['readout']['effective_support'], 1)
            self.assertEqual(w.db.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(w.db.execute('PRAGMA foreign_key_check').fetchall(), [])
        finally:
            w.close()
        with sqlite3.connect(original) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)

    def test_metadata_failures_rollback_and_validation(self):
        before = self.w.inspect(self.pid)
        for kwargs in ({'mass': float('nan')}, {'mass': -1}, {'cluster_id': 'shared'}, {'event_key': ' '}):
            with self.assertRaises(ValueError):
                self.w.add_report(self.pid, 'A', 'closed', 'supports', **kwargs)
        self.w.db.execute("CREATE TRIGGER reject_impact BEFORE INSERT ON evidence_impact BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.w.add_report(self.pid, 'A', 'closed', 'supports')
        self.assertEqual(self.w.inspect(self.pid), before)
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            self.w.project(self.pid, 'unknown')

    def test_cli_project_and_inspect(self):
        base = [sys.executable, '-m', 'holon.cli', '--db', str(self.path)]
        def invoke(*args):
            return json.loads(subprocess.check_output(base + list(args), text=True))
        args = ('report', self.pid, '--source', 'A', '--text', 'closed', '--relation', 'supports', '--mass', '.5', '--event-key', 'one')
        self.assertEqual(invoke(*args), invoke(*args))
        result = invoke('project', self.pid, '--policy', 'binary-beta-v1')
        self.assertEqual(result['readout']['effective_support'], .5)
        self.assertEqual(invoke('inspect', self.pid, '--projection')['projection'], result)
        self.assertEqual(invoke('migrate-impacts', self.pid, '--actor', 'Nick', '--reason', 'No legacy')['annotated_count'], 0)

    def test_correction_retry_and_metadata_rollback(self):
        old = self.w.add_report(self.pid, 'A', 'open', 'contradicts')['evidence_id']
        kwargs = dict(report='closed', source='A', relation='supports', event_key='correction1')
        first = self.w.withdraw_evidence(old, 'Nick', 'Misread', **kwargs)
        self.assertEqual(self.w.withdraw_evidence(old, 'Nick', 'Misread', **kwargs), first)
        with self.assertRaises(ValueError):
            self.w.withdraw_evidence(old, 'Nick', 'Changed reason', **kwargs)
        before = self.w.project(self.pid)
        self.w.db.execute("CREATE TRIGGER reject_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.w.withdraw_evidence(first['replacement_evidence_id'], 'Nick', 'Again',
                                     report='open', source='A', relation='contradicts')
        self.assertEqual(self.w.project(self.pid), before)
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM evidence_impact').fetchone()[0], 2)

    def test_schema_migration_failure_is_atomic(self):
        path = Path(self.temp.name) / 'broken.sqlite3'
        with sqlite3.connect(path) as db:
            # A conflicting table injects a failure after base tables and the
            # first metadata table have been created inside the migration.
            db.execute('CREATE TABLE impact_migrations (unexpected TEXT)')
        with self.assertRaises(sqlite3.OperationalError):
            Workspace(path)
        with sqlite3.connect(path) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            self.assertEqual(tables, ['impact_migrations'])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
