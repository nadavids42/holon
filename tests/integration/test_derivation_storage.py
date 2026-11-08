import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from holon.domain.derivation import Justification, SignedClaim
from holon.workspace.derivation_storage import DerivationStore, replay_lineage
from holon.workspace.service import Workspace

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


class DerivationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workspace.sqlite3'
        w = Workspace(self.path)
        self.ids = [w.create_proposition(name, 'T0') for name in ('closed', 'locked', 'secured', 'inspection')]
        self.obs = [w.record_observation(name, 'report from ' + name) for name in ('A', 'B', 'C')]
        self.link = w.link_observation(self.obs[0], self.ids[0], 'supports')
        self.before = w.inspect(self.ids[0], projection_policy='binary-beta-v1')
        w.close()
        self.store = DerivationStore(self.path)
        self.addCleanup(self.store.close)

    def justification(self, id='joint', conclusion=2, premises=(0, 1)):
        return Justification(id, SignedClaim(self.ids[conclusion]), tuple(SignedClaim(self.ids[p]) for p in premises),
                             'Explicit test rule', 'reviewer', 'Test derivation')

    def assign(self, event, index, group):
        return self.store.assign_origin(event, self.obs[index], group, 'reviewer', 'Assert origin',
                                        expected_revision=self.store.lineage()['revision'])

    def reverse(self, event, target):
        return self.store.reverse_lineage(event, target, 'reviewer', 'Undo mistake',
                                          expected_revision=self.store.lineage()['revision'])

    def test_derivations_persist_and_exact_retry_preserves_identity_and_timestamp(self):
        j = self.justification()
        self.store.add_justification(j)
        self.store.add_justification(self.justification('inspection', premises=(3,)))
        before = self.store.inspect_derivations()
        self.assertEqual(self.store.add_justification(j), j.id)
        self.assertEqual(before, self.store.inspect_derivations())
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.store.add_justification(replace(j, rule='changed'))
        with DerivationStore(self.path) as restarted:
            self.assertEqual(restarted.inspect_derivations(), before)
            self.assertEqual(len(restarted.graph().alternatives(SignedClaim(self.ids[2]))), 2)
        self.assertTrue(before['digest'].startswith('derivation-ledger-v1:'))

    def test_lineage_merge_reassignment_and_reverse_restore_prior_assignments(self):
        self.assign('a', 0, 'origin-a'); self.assign('b', 1, 'origin-b')
        before = self.store.lineage()
        self.store.merge_origins('merge', ['origin-b', 'origin-a'], 'origin-a', 'reviewer', 'Shared source', expected_revision=2)
        merged = self.store.lineage()
        self.assertEqual(merged['assignments'][self.obs[1]], 'origin-a')
        self.assertEqual(len(merged['events'][-1]['changes']), 2)
        self.assign('move', 1, 'origin-c')
        with self.assertRaisesRegex(ValueError, 'dependent'):
            self.reverse('too-early', 'merge')
        self.reverse('undo-move', 'move')
        self.reverse('undo-merge', 'merge')
        restored = self.store.lineage()
        self.assertEqual(restored['assignments'], before['assignments'])
        self.assertEqual(restored['heads'], before['heads'])
        self.assertEqual(len(restored['events']), 6)
        self.assertNotEqual(restored['digest'], before['digest'])
        self.reverse('undo-a', 'a')
        self.assertIsNone(self.store.lineage()['assignments'][self.obs[0]])
        with self.assertRaises(ValueError):
            self.reverse('duplicate-undo', 'merge')
        with self.assertRaises(ValueError):
            self.reverse('undo-reversal', 'undo-a')

    def test_overlapping_merges_must_be_reversed_in_dependency_order(self):
        for i in range(3): self.assign('assign-' + str(i), i, 'g' + str(i))
        self.store.merge_origins('m1', ['g0', 'g1'], 'g0', 'reviewer', 'First', expected_revision=3)
        self.store.merge_origins('m2', ['g0', 'g2'], 'g0', 'reviewer', 'Second', expected_revision=4)
        with self.assertRaises(ValueError): self.reverse('blocked', 'm1')
        self.reverse('r2', 'm2'); self.reverse('r1', 'm1')
        self.assertEqual(self.store.lineage()['assignments'], dict(zip(self.obs, ['g0', 'g1', 'g2'])))

    def test_merge_is_explicit_membership_not_an_alias_for_future_members(self):
        self.assign('a', 0, 'a'); self.assign('b', 1, 'b')
        self.store.merge_origins('m', ['a', 'b'], 'a', 'reviewer', 'Merge', expected_revision=2)
        self.assign('new-member', 2, 'a')
        self.reverse('r', 'm')
        self.assertEqual(self.store.lineage()['assignments'], dict(zip(self.obs, ['a', 'b', 'a'])))

    def test_unknown_provenance_and_legacy_readouts_remain_unchanged(self):
        self.assertEqual(set(self.store.lineage()['assignments'].values()), {None})
        self.assertEqual(self.store.lineage()['provenance_completeness'], 'unknown')
        self.store.add_justification(self.justification())
        self.assign('a', 0, 'new-origin')
        self.assign('unknown', 0, None)
        w = Workspace(self.path)
        try:
            self.assertEqual(w.inspect(self.ids[0], projection_policy='binary-beta-v1'), self.before)
            self.assertEqual(w.inspect(self.ids[2])['status'], 'insufficient_evidence')
        finally: w.close()

    def test_restart_in_a_new_process_reconstructs_same_snapshots(self):
        self.store.add_justification(self.justification()); self.assign('a', 0, 'origin')
        script = "from holon.workspace.derivation_storage import DerivationStore; import json,sys; s=DerivationStore(sys.argv[1]); print(json.dumps([s.inspect_derivations(),s.lineage()])); s.close()"
        output = subprocess.check_output([sys.executable, '-c', script, str(self.path)], text=True)
        expected = json.loads(json.dumps([self.store.inspect_derivations(), self.store.lineage()]))
        self.assertEqual(json.loads(output), expected)

    def test_stale_revision_and_conflicting_event_retry_fail_without_changes(self):
        args = ('event', self.obs[0], 'g', 'reviewer', 'Reason')
        self.store.assign_origin(*args, expected_revision=0)
        before = self.store.lineage()
        self.store.assign_origin(*args, expected_revision=0)
        self.assertEqual(self.store.lineage(), before)
        with self.assertRaises(ValueError): self.store.assign_origin(*args, expected_revision=1)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.store.assign_origin('other', self.obs[1], 'g', 'reviewer', 'Reason', expected_revision=0)
        self.assertEqual(self.store.lineage(), before)

    def test_invalid_references_cycles_and_lineage_requests_are_atomic(self):
        self.store.add_justification(self.justification())
        before = self.store.inspect_derivations()
        for j in (self.justification('cycle', conclusion=0, premises=(2,)),
                  replace(self.justification('unknown'), conclusion=SignedClaim('missing'))):
            with self.assertRaises(ValueError): self.store.add_justification(j)
        self.assertEqual(self.store.inspect_derivations(), before)
        for action in (
            lambda: self.store.assign_origin('x','missing','g','actor','reason',expected_revision=0),
            lambda: self.store.merge_origins('x',['a','b'],'a','actor','reason',expected_revision=0),
            lambda: self.store.merge_origins('x',['a','a'],'a','actor','reason',expected_revision=0),
            lambda: self.store.assign_origin('x',self.obs[0],'g','actor','reason',expected_revision=True),
            lambda: self.store.assign_origin('x',self.obs[0],None,'actor','reason',expected_revision=0),
            lambda: self.store.reverse_lineage('x','missing','actor','reason',expected_revision=0)):
            with self.assertRaises(ValueError): action()
        self.assertEqual(self.store.lineage()['events'], [])

    def test_immutable_tables_and_insert_failures_rollback(self):
        self.store.add_justification(self.justification()); self.assign('a',0,'g')
        for table in ('derivation_justifications','lineage_events'):
            for operation in ('DELETE FROM ' + table, 'UPDATE ' + table + " SET reason='changed'"):
                with self.assertRaises(sqlite3.IntegrityError), self.store.db:
                    self.store.db.execute(operation)
        for table, action in [('derivation_justifications',lambda: self.store.add_justification(self.justification('other'))),
                              ('lineage_events',lambda: self.assign('b',1,'g'))]:
            before = (self.store.inspect_derivations(),self.store.lineage())
            self.store.db.execute(f"CREATE TRIGGER fail_insert BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT,'injected'); END")
            with self.assertRaises(sqlite3.IntegrityError): action()
            self.assertEqual((self.store.inspect_derivations(),self.store.lineage()),before)
            self.store.db.execute('DROP TRIGGER fail_insert')

    def test_concurrent_graph_writes_cannot_jointly_create_a_cycle(self):
        choices = [self.justification('ab',conclusion=1,premises=(0,)),self.justification('ba',conclusion=0,premises=(1,))]
        def write(j):
            with DerivationStore(self.path) as store:
                try: store.add_justification(j); return True
                except ValueError: return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(write,choices)),[False,True])
        self.assertEqual(len(self.store.graph().justifications),1)

    def test_concurrent_lineage_edits_reject_stale_snapshot(self):
        def write(index):
            with DerivationStore(self.path) as store:
                try:
                    store.assign_origin('e'+str(index),self.obs[index],'g','actor','reason',expected_revision=0)
                    return True
                except ValueError: return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(write,[0,1])),[False,True])
        self.assertEqual(self.store.lineage()['revision'],1)

    def test_replay_rejects_broken_history(self):
        self.assign('a',0,'g')
        events = self.store.lineage()['events']
        events[0]['changes'][0]['before'] = 'wrong'
        with self.assertRaises(ValueError): replay_lineage(events,self.obs)


class DerivationMigrationTests(unittest.TestCase):
    def fixture(self, path):
        with sqlite3.connect(path) as db:
            db.executescript((FIXTURES/'derivation-schema2.sql').read_text())

    def test_frozen_schema2_migration_preserves_exact_readout_and_original_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.sqlite3'; self.fixture(path)
            with sqlite3.connect(path) as db:
                tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'sqlite_sequence'")]
                original={t:list(db.execute('SELECT * FROM '+t)) for t in tables}
            expected=json.loads((FIXTURES/'derivation-schema2-expected.json').read_text())
            w=Workspace(path)
            try:
                self.assertEqual(w.db.execute('PRAGMA user_version').fetchone()[0],3)
                self.assertEqual(json.loads(json.dumps(w.inspect(expected['proposition_id'],projection_policy='binary-beta-v1'))),expected['state'])
                for table, rows in original.items():
                    self.assertEqual([tuple(r) for r in w.db.execute('SELECT * FROM '+table)],rows)
            finally: w.close()
            with DerivationStore(path) as store:
                self.assertEqual(store.graph().justifications,())
                self.assertTrue(all(g is None for g in store.lineage()['assignments'].values()))
            with sqlite3.connect(path) as db: self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_failed_migration_rolls_back_schema_version_and_partial_ddl(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.sqlite3'; self.fixture(path)
            def broken(db):
                db.execute('CREATE TABLE partial_migration (id TEXT)')
                raise sqlite3.IntegrityError('injected')
            with patch('holon.workspace.derivation_storage.migrate',side_effect=broken):
                with self.assertRaises(sqlite3.IntegrityError): DerivationStore(path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='partial_migration'").fetchone())
            with DerivationStore(path) as store: self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0],3)
