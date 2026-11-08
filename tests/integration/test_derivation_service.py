"""Shared service/CLI/API contracts and cross-operation transaction ownership."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from holon.workspace.service import Workspace
from holon.workspace.derivation_storage import DerivationStore, LineageConflict
from holon.web.application import Application
from tests.integration import test_browser_workspace as browser_tests


class DerivationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workspace.sqlite3'
        self.w = Workspace(self.path)
        self.addCleanup(self.w.close)
        self.pids = [self.w.create_proposition(p, 'T0') for p in ('closed', 'locked', 'secured')]
        self.oids = [self.w.record_observation(p, 'Report') for p in ('A','B')]
        self.app = Application(self.path)

    def derive_args(self, identifier='joint'):
        return dict(justification_id=identifier, conclusion=dict(proposition_id=self.pids[2], relation='supports'),
                    premises=[dict(proposition_id=p, relation='supports') for p in self.pids[:2]],
                    rule='Closed and locked suffice here', actor='reviewer', reason='Declared rule')

    def origin_args(self, event='assign', index=0, group='g', revision=0):
        return dict(event_id=event, observation_id=self.oids[index], group_id=group,
                    actor='reviewer', reason='Declared origin', expected_revision=revision)

    def command(self, operation, arguments, request_id=None):
        return self.app.command(dict(operation=operation, arguments=arguments, request_id=request_id or str(uuid4())))

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable,'-m','holon.cli','--db',str(self.path),*args],
                                capture_output=True,text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def http(self,*args,**kwargs):
        return browser_tests.BrowserWorkspaceTests.http(self,*args,**kwargs)

    def test_shared_operations_and_decoded_inspection_preserve_old_status(self):
        old = self.w.inspect(self.pids[2],projection_policy='binary-beta-v1')
        self.assertEqual(self.w.add_derivation(**self.derive_args()), {'justification_id':'joint'})
        self.w.assign_origin(**self.origin_args())
        graph = self.w.inspect_derivations(); lineage = self.w.inspect_lineage()
        record = graph['justifications'][0]
        self.assertEqual(record['conclusion'], self.derive_args()['conclusion'])
        self.assertEqual({p['proposition_id'] for p in record['premises']},set(self.pids[:2]))
        self.assertNotIn('premises_json',record)
        self.assertEqual(len(graph['propositions']),3)
        self.assertNotIn('request_json',lineage['events'][0])
        self.assertEqual(lineage['events'][0]['request']['kind'],'assign')
        self.assertEqual(lineage['observations'][0].keys(),{'id','source','report','recorded_at','observed_at'})
        self.assertEqual(self.w.inspect(self.pids[2],projection_policy='binary-beta-v1'),old)

    def test_composed_success_commits_once_and_borrowed_close_preserves_owner(self):
        with self.w.atomic():
            p = self.w.create_proposition('new', 'T0')
            oid = self.w.record_observation('C','Report')
            args=self.derive_args(); args['conclusion']['proposition_id']=p
            self.w.add_derivation(**args)
            self.w.assign_origin('new-origin',oid,'new','actor','reason',expected_revision=0)
            self.w.add_report(p,'C','Report','supports')
            DerivationStore.for_workspace(self.w).close()
            self.assertTrue(self.w.db.in_transaction)
        self.assertFalse(self.w.db.in_transaction)
        self.assertEqual(self.w.inspect(p)['status'],'supported')
        with DerivationStore(self.path) as store:
            self.assertEqual(store.lineage()['assignments'][oid],'new')
            self.assertEqual(len(store.graph().justifications),1)

    def test_late_failure_rolls_back_existing_and_new_operations_together(self):
        before = (self.w.list_propositions(),self.w.list_observations(),self.w.inspect_derivations(),self.w.inspect_lineage())
        with self.assertRaises(LineageConflict):
            with self.w.atomic():
                self.w.create_proposition('temporary','T0')
                self.w.record_observation('temporary','Report')
                self.w.add_derivation(**self.derive_args())
                self.w.add_report(self.pids[0],'temporary','Report','supports')
                self.w.assign_origin(**self.origin_args())
                self.w.assign_origin(**self.origin_args('stale',1,revision=0))
        self.assertEqual((self.w.list_propositions(),self.w.list_observations(),self.w.inspect_derivations(),self.w.inspect_lineage()),before)
        self.assertEqual(self.w.inspect(self.pids[0])['history'],[])

    def test_api_receipt_failure_rolls_back_derivation_and_lineage(self):
        self.command('propose',{'claim':'receipt setup','scope':'T0'})
        self.w.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON browser_receipts BEGIN SELECT RAISE(ABORT,'injected'); END")
        for operation, args in [('derive',self.derive_args()),('assign-origin',self.origin_args())]:
            before = (self.w.inspect_derivations(),self.w.inspect_lineage())
            with self.assertRaises(sqlite3.IntegrityError): self.command(operation,args)
            self.assertEqual((self.w.inspect_derivations(),self.w.inspect_lineage()),before)
        self.w.db.execute('DROP TRIGGER reject_receipt')
        self.command('derive',self.derive_args())
        self.command('assign-origin',self.origin_args())

    def test_cli_api_and_service_return_identical_inspection_after_process_restart(self):
        result=self.cli('derive',self.pids[2],'--id','joint','--premise',self.pids[0],'supports',
            '--premise',self.pids[1],'supports','--rule','Closed and locked suffice here',
            '--actor','reviewer','--reason','Declared rule')
        self.assertEqual(result, self.command('derive',self.derive_args()))
        self.assertEqual(self.cli('inspect-derivations'), self.w.inspect_derivations())
        self.cli('assign-origin',self.oids[0],'--group','g','--event-id','assign','--actor','reviewer',
                 '--reason','Declared origin','--expected-revision','0')
        self.assertEqual(self.command('assign-origin',self.origin_args()),{'event_id':'assign'})
        self.assertEqual(self.cli('inspect-lineage'),self.w.inspect_lineage())
        for route, expected in [('/api/derivations',self.w.inspect_derivations()),('/api/lineage',self.w.inspect_lineage())]:
            response=self.http(route)
            self.assertEqual(response['status'],200)
            self.assertEqual(json.loads(response['body']),expected)
        self.assertEqual(self.http('/api/derivations?unknown=1')['status'],400)

    def test_cli_and_api_merge_reverse_and_unknown_origin(self):
        self.command('assign-origin',self.origin_args())
        self.command('assign-origin',self.origin_args('second',1,'h',1))
        self.cli('merge-origins','--group','g','--group','h','--target','g','--event-id','merge',
                 '--actor','reviewer','--reason','Shared source','--expected-revision','2')
        self.assertEqual(set(self.w.inspect_lineage()['assignments'].values()),{'g'})
        self.command('reverse-lineage',dict(event_id='reverse',target_event_id='merge',actor='reviewer',reason='Mistake',expected_revision=3))
        self.assertEqual(self.w.inspect_lineage()['assignments'][self.oids[1]],'h')
        self.cli('assign-origin',self.oids[0],'--unknown','--event-id','clear','--actor','reviewer','--reason','Unknown','--expected-revision','4')
        self.assertIsNone(self.w.inspect_lineage()['assignments'][self.oids[0]])
        self.cli('reverse-lineage','clear','--event-id','restore','--actor','reviewer','--reason','Restore','--expected-revision','5')
        self.assertEqual(self.w.inspect_lineage()['assignments'][self.oids[0]],'g')

    def test_api_nested_validation_and_service_validation_reject_malformed_input(self):
        for changes in ({'premises':[]},{'premises':'not a list'}, {'conclusion':{'proposition_id':self.pids[2]}},
                        {'premises':[{'proposition_id':self.pids[0],'relation':'supports','mass':1}]},
                        {'premises':[{'proposition_id':self.pids[0],'relation':'uncertain'}]}):
            body=dict(operation='derive',arguments=self.derive_args()|changes,request_id=str(uuid4()))
            self.assertEqual(self.http('/api/commands',body)['status'],400)
            with self.assertRaises(ValueError): self.w.add_derivation(**body['arguments'])
        for changes in ({'expected_revision':True},{'expected_revision':-1},{'group_id':[]},{'extra':'field'}):
            self.assertEqual(self.http('/api/commands',dict(operation='assign-origin',arguments=self.origin_args()|changes,request_id=str(uuid4())))['status'],400)
        for groups in ([None,'g'],['g'],{'a':'b'}):
            with self.assertRaises(ValueError): self.command('merge-origins',dict(event_id='merge',group_ids=groups,target_group_id='g',actor='a',reason='r',expected_revision=0))
        self.assertEqual(self.w.inspect_derivations()['justifications'],[])
        self.assertEqual(self.w.inspect_lineage()['events'],[])

    def test_lineage_conflicts_map_to_http_409_and_cli_errors(self):
        self.command('assign-origin',self.origin_args())
        args=self.origin_args('stale',1,revision=0)
        self.assertEqual(self.http('/api/commands',dict(operation='assign-origin',arguments=args,request_id='stale'))['status'],409)
        self.cli('assign-origin',self.oids[1],'--group','g','--event-id','stale','--actor','a','--reason','r','--expected-revision','0',success=False)
        self.command('assign-origin',self.origin_args('newer',0,'h',1))
        body=dict(operation='reverse-lineage',arguments=dict(event_id='reverse',target_event_id='assign',actor='a',reason='r',expected_revision=2),request_id='blocked')
        self.assertEqual(self.http('/api/commands',body)['status'],409)

    def test_concurrent_api_retry_and_restart_keep_single_effect(self):
        args=self.derive_args()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:self.command('derive',args,'same'),range(3)))
        self.assertTrue(all(r=={'justification_id':'joint'} for r in results))
        self.app=Application(self.path)
        self.assertEqual(self.command('derive',args,'same'),results[0])
        self.assertEqual(len(self.w.inspect_derivations()['justifications']),1)
        self.assertEqual(self.command('derive',args,'different-request'),results[0])

    def test_shared_reads_are_read_only_and_hold_one_snapshot(self):
        self.w.db.execute('PRAGMA journal_mode=WAL')
        self.w.add_derivation(**self.derive_args())
        before_changes=self.w.db.total_changes
        self.w.inspect_derivations(); self.w.inspect_lineage()
        self.assertEqual(self.w.db.total_changes,before_changes)
        original=DerivationStore.inspect_derivations
        added=[]
        def interleaved(store):
            result=original(store)
            other=Workspace(self.path)
            try: added.append(other.create_proposition('Concurrent claim','T0'))
            finally: other.close()
            return result
        with patch.object(DerivationStore,'inspect_derivations',interleaved):
            snapshot=self.w.inspect_derivations()
        self.assertNotIn(added[0], [p['id'] for p in snapshot['propositions']])
        self.assertIn(added[0], [p['id'] for p in self.w.inspect_derivations()['propositions']])

    def test_service_and_api_on_migrated_schema2_preserve_original_readout(self):
        fixture=Path(__file__).resolve().parents[1]/'fixtures'
        path=Path(self.temp.name)/'old.sqlite3'
        with sqlite3.connect(path) as db: db.executescript((fixture/'derivation-schema2.sql').read_text())
        expected=json.loads((fixture/'derivation-schema2-expected.json').read_text())
        app=Application(path)
        with app.workspace() as workspace:
            self.assertEqual(workspace.inspect_derivations()['justifications'],[])
            self.assertEqual(workspace.inspect_lineage()['events'],[])
            self.assertEqual(json.loads(json.dumps(workspace.inspect(expected['proposition_id'],projection_policy='binary-beta-v1'))),expected['state'])
