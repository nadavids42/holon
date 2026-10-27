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
from holon.workspace.metadata import canonical, digest, policy_payload, source_cluster
from holon.workspace.service import Workspace, normalize_observed_at


# Literal version-1 schema; independent of the schema being migrated.
V1_SCHEMA = """
CREATE TABLE propositions (id TEXT PRIMARY KEY, claim TEXT NOT NULL, scope TEXT NOT NULL);
CREATE TABLE observations (id TEXT PRIMARY KEY, source TEXT NOT NULL, report TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE evidence (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id), proposition_id TEXT NOT NULL REFERENCES propositions(id), relation TEXT NOT NULL CHECK(relation IN ('supports','contradicts')));
CREATE INDEX evidence_proposition ON evidence(proposition_id);
CREATE TABLE interpretations (evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), model TEXT NOT NULL, reason TEXT NOT NULL, prompt_version TEXT NOT NULL);
CREATE TABLE withdrawals (evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), actor TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL, replacement_evidence_id TEXT REFERENCES evidence(id));
CREATE TABLE revisions (sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposition_id TEXT NOT NULL REFERENCES propositions(id), status TEXT NOT NULL CHECK(status IN ('supported','opposed','contested','insufficient_evidence')), evidence_ids TEXT NOT NULL, recorded_at TEXT NOT NULL, policy TEXT NOT NULL);
CREATE TABLE projection_policies (id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE impact_migrations (id TEXT PRIMARY KEY, actor TEXT NOT NULL, reason TEXT NOT NULL, recorded_at TEXT NOT NULL, assumptions TEXT NOT NULL);
CREATE TABLE evidence_impact (evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), proposition_id TEXT NOT NULL REFERENCES propositions(id), source TEXT NOT NULL, mass REAL NOT NULL CHECK(mass >= 0), semantics TEXT NOT NULL, cluster_id TEXT NOT NULL, cluster_actor TEXT, cluster_reason TEXT, event_key TEXT, request_digest TEXT, migration_id TEXT REFERENCES impact_migrations(id), UNIQUE(proposition_id, source, event_key));
PRAGMA user_version = 1;
"""


class ObservationTimeTests(unittest.TestCase):
    def test_timestamp_validation_and_normalization(self):
        self.assertIsNone(normalize_observed_at(None))
        self.assertEqual(normalize_observed_at('2026-10-26T12:34:56-04:00'),
                         '2026-10-26T16:34:56.000000+00:00')
        self.assertEqual(normalize_observed_at('2026-10-26T16:34:56.5Z'),
                         '2026-10-26T16:34:56.500000+00:00')
        for value in ('2026-10-26', '2026-10-26T12:34:56', '2026-10-26 12:34:56Z',
                      '2026-10-26T12:34Z', '2026-02-30T12:34:56Z',
                      '2026-10-26T12:34:56+01:60', '2026-10-26T12:34:56.1234567Z',
                      '0001-01-01T00:00:00+01:00', '', 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_observed_at(value)

    def test_report_retry_correction_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            w = Workspace(path)
            pid = w.create_proposition('Door closed', 'Monday')
            first = w.add_report(pid, 'A', 'closed Monday', 'supports', event_key='a',
                                 observed_at='2026-10-26T12:00:00-04:00')
            self.assertEqual(first, w.add_report(pid, 'A', 'closed Monday', 'supports', event_key='a',
                                                observed_at='2026-10-26T16:00:00Z'))
            before = w.inspect(pid)
            for time in (None, '2026-10-26T16:00:01Z', 'invalid'):
                with self.assertRaises(ValueError):
                    w.add_report(pid, 'A', 'closed Monday', 'supports', event_key='a', observed_at=time)
            self.assertEqual(w.inspect(pid), before)
            state = w.inspect(pid)['evidence'][0]
            self.assertEqual(state['observed_at'], '2026-10-26T16:00:00.000000+00:00')
            self.assertNotEqual(state['recorded_at'], state['observed_at'])
            correction = w.withdraw_evidence(first['evidence_id'], 'Nick', 'Bad report', report='open',
                                             source='A', relation='contradicts', event_key='b')
            self.assertEqual(correction, w.withdraw_evidence(first['evidence_id'], 'Nick', 'Bad report',
                             report='open', source='A', relation='contradicts', event_key='b'))
            with self.assertRaises(ValueError):
                w.withdraw_evidence(first['evidence_id'], 'Nick', 'Bad report', report='open', source='A',
                                    relation='contradicts', event_key='b', observed_at='2026-10-26T16:00:00Z')
            self.assertIsNone(w.inspect(pid)['evidence'][1]['observed_at'])
            projection = w.project(pid)
            w.close()
            w = Workspace(path)
            try:
                self.assertEqual(w.project(pid), projection)
                self.assertEqual(w.inspect(pid)['evidence'][0]['observed_at'], state['observed_at'])
            finally:
                w.close()

    def test_v1_migration_preserves_old_retries_and_projection_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'v1.sqlite3'
            payload = policy_payload()
            request = {'report': 'closed', 'relation': 'supports', 'mass': 1.0,
                       'cluster': source_cluster('A'), 'actor': None, 'reason': None, 'interpretation': None}
            with sqlite3.connect(path) as db:
                db.executescript(V1_SCHEMA)
                db.execute("INSERT INTO propositions VALUES ('p','closed','T0')")
                db.execute("INSERT INTO observations VALUES ('o','A','closed','2026-10-27T00:00:00+00:00')")
                db.execute("INSERT INTO evidence VALUES ('e','o','p','supports')")
                db.execute("INSERT INTO revisions VALUES (7,'p','supported','[\"e\"]','2026-10-27T00:00:00+00:00','active-presence-v2')")
                db.execute('INSERT INTO projection_policies VALUES (?,?,?)', ('binary-beta-v1', payload, digest(payload)))
                db.execute('INSERT INTO evidence_impact VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           ('e', 'p', 'A', 1, 'stipulated-impact-v1', source_cluster('A'), None, None,
                            'key', digest(canonical(request)), None))
            # The old digest is defined by the exact old projection query.
            with sqlite3.connect(path) as db:
                db.row_factory = sqlite3.Row
                rows = [dict(row) for row in db.execute("SELECT e.id, e.relation, o.source, o.report, o.recorded_at, w.recorded_at AS withdrawn_at, w.actor, w.reason, w.replacement_evidence_id, m.mass, m.semantics, m.cluster_id, m.cluster_actor, m.cluster_reason, m.event_key, m.migration_id FROM evidence e JOIN observations o ON o.id=e.observation_id LEFT JOIN withdrawals w ON w.evidence_id=e.id LEFT JOIN evidence_impact m ON m.evidence_id=e.id WHERE e.proposition_id=? ORDER BY e.id", ('p',))]
                old_digest = digest(canonical(rows))
            for _ in range(2):
                w = Workspace(path)
                try:
                    self.assertEqual(w.db.execute('PRAGMA user_version').fetchone()[0], 2)
                    self.assertEqual(w.db.execute('PRAGMA foreign_key_check').fetchall(), [])
                    self.assertIsNone(w.inspect('p')['evidence'][0]['observed_at'])
                    self.assertEqual(w.inspect('p')['history'][0]['sequence'], 7)
                    self.assertEqual(w.project('p')['ledger_digest'], old_digest)
                    self.assertEqual(w.project('p')['readout']['mean'], 2 / 3)
                    self.assertEqual(w.add_report('p', 'A', 'closed', 'supports', event_key='key')['evidence_id'], 'e')
                    with self.assertRaises(ValueError):
                        w.add_report('p', 'A', 'closed', 'supports', event_key='key', observed_at='2026-10-26T12:00:00Z')
                finally:
                    w.close()

    def test_migration_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.sqlite3'
            with sqlite3.connect(path) as db:
                db.executescript(V1_SCHEMA)
                db.execute('ALTER TABLE observations ADD COLUMN observed_at TEXT')
            with self.assertRaises(sqlite3.OperationalError):
                Workspace(path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)

    def test_cli_report_correction_and_interpret_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cli.sqlite3'
            base = [sys.executable, '-m', 'holon.cli', '--db', str(path)]
            def invoke(*args):
                return json.loads(subprocess.check_output(base + list(args), text=True))
            pid = invoke('propose', 'closed', '--scope', 'T0')['proposition_id']
            first = invoke('report', pid, '--source', 'A', '--text', 'closed', '--relation', 'supports',
                           '--observed-at', '2026-10-26T12:00:00Z')
            invoke('correct', first['evidence_id'], '--actor', 'Nick', '--reason', 'wrong', '--source', 'A',
                   '--text', 'open', '--relation', 'contradicts', '--observed-at', '2026-10-26T13:00:00Z')
            state = invoke('inspect', pid)
            self.assertEqual(state['evidence'][1]['observed_at'], '2026-10-26T13:00:00.000000+00:00')
            argv = ['holon', '--db', str(path), 'interpret', pid, '--source', 'B', '--text', 'closed',
                    '--observed-at', '2026-10-26T14:00:00Z']
            with patch('sys.argv', argv), patch('builtins.input', return_value='y'), \
                 patch('holon.cli.OllamaInterpreter.interpret', return_value=Interpretation('supports', 'match', 'test')), \
                 patch('sys.stdout', new_callable=io.StringIO) as output:
                main()
            self.assertIn('2026-10-26T14:00:00.000000+00:00', output.getvalue())
            self.assertEqual(invoke('inspect', pid)['evidence'][-1]['observed_at'], '2026-10-26T14:00:00.000000+00:00')


if __name__ == '__main__':
    unittest.main()
