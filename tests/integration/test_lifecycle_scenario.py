"""End-to-end CLI scenario on a migrated copy of a literal version-1 store."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from holon.workspace.metadata import canonical, digest, policy_payload, source_cluster
from integration.test_observation_time import V1_SCHEMA


class LifecycleScenarioTests(unittest.TestCase):
    def test_migrated_store_observation_links_and_reinterpretation_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'legacy.sqlite3'
            copy = Path(directory) / 'working-copy.sqlite3'
            payload = policy_payload()
            request = {'report': 'closed', 'relation': 'supports', 'mass': 1.0,
                       'cluster': source_cluster('legacy sensor'), 'actor': None, 'reason': None,
                       'interpretation': None}
            with sqlite3.connect(original) as db:
                db.executescript(V1_SCHEMA)
                db.execute("INSERT INTO propositions VALUES ('legacy-p','Door closed','earlier instant')")
                db.execute("INSERT INTO observations VALUES ('legacy-o','legacy sensor','closed','2026-10-25T12:00:00+00:00')")
                db.execute("INSERT INTO evidence VALUES ('legacy-e','legacy-o','legacy-p','supports')")
                db.execute("INSERT INTO revisions VALUES (7,'legacy-p','supported','[\"legacy-e\"]','2026-10-25T12:00:00+00:00','active-presence-v2')")
                db.execute('INSERT INTO projection_policies VALUES (?,?,?)', ('binary-beta-v1', payload, digest(payload)))
                db.execute('INSERT INTO evidence_impact VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           ('legacy-e', 'legacy-p', 'legacy sensor', 1, 'stipulated-impact-v1',
                            source_cluster('legacy sensor'), None, None, 'legacy-key', digest(canonical(request)), None))
            with sqlite3.connect(original) as src, sqlite3.connect(copy) as dst:
                src.backup(dst)

            base = [sys.executable, '-m', 'holon.cli', '--db', str(copy)]
            def invoke(*args):
                return json.loads(subprocess.check_output(base + list(args), text=True))

            legacy = invoke('inspect', 'legacy-p', '--projection')
            self.assertEqual(legacy['evidence'][0]['observation_id'], 'legacy-o')
            self.assertIsNone(legacy['evidence'][0]['observed_at'])
            self.assertEqual(legacy['history'][0]['sequence'], 7)
            self.assertEqual(legacy['projection']['readout']['mean'], 2 / 3)
            self.assertEqual(invoke('report', 'legacy-p', '--source', 'legacy sensor', '--text', 'closed',
                                    '--relation', 'supports', '--event-key', 'legacy-key')['evidence_id'], 'legacy-e')

            closed = invoke('propose', 'The door is closed', '--scope', 'lab door at T0')['proposition_id']
            locked = invoke('propose', 'The door is locked', '--scope', 'lab door at T0')['proposition_id']
            observed = invoke('observe', '--source', 'sensor A', '--text', 'Door is open and locked at T0',
                              '--observed-at', '2026-10-26T12:00:00-04:00')['observation_id']
            wrong = invoke('link', observed, closed, '--relation', 'supports')['evidence_id']
            other = invoke('link', observed, locked, '--relation', 'supports')['evidence_id']
            result = invoke('reinterpret', wrong, '--actor', 'Nick', '--reason', 'Report says open',
                            '--relation', 'contradicts', '--event-key', 'fix')
            self.assertEqual(invoke('reinterpret', wrong, '--actor', 'Nick', '--reason', 'Report says open',
                                    '--relation', 'contradicts', '--event-key', 'fix'), result)

            observation = invoke('inspect-observation', observed)
            self.assertEqual(observation['observation']['observed_at'], '2026-10-26T16:00:00.000000+00:00')
            self.assertEqual(observation['observation']['report'], 'Door is open and locked at T0')
            links = {link['evidence_id']: link for link in observation['links']}
            self.assertFalse(links[wrong]['active'])
            self.assertEqual(links[wrong]['replacement_evidence_id'], result['replacement_evidence_id'])
            self.assertTrue(links[other]['active'])
            self.assertTrue(links[result['replacement_evidence_id']]['active'])
            state = invoke('inspect', closed, '--projection')
            self.assertEqual([entry['status'] for entry in state['history']], ['supported', 'opposed'])
            self.assertEqual(state['history'][0]['evidence_ids'], [wrong])
            self.assertEqual(state['history'][1]['evidence_ids'], [result['replacement_evidence_id']])
            self.assertEqual(state['projection']['readout']['mean'], 1 / 3)
            other_state = invoke('inspect', locked, '--projection')
            self.assertEqual(other_state['status'], 'supported')
            self.assertEqual(other_state['projection']['readout']['mean'], 2 / 3)
            self.assertEqual(other_state['evidence'][0]['observation_id'], observed)
            self.assertEqual(invoke('inspect', 'legacy-p', '--projection'), legacy)
            with sqlite3.connect(copy) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            with sqlite3.connect(original) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 1)
                self.assertNotIn('observed_at', [row[1] for row in db.execute('PRAGMA table_info(observations)')])


if __name__ == '__main__':
    unittest.main()
