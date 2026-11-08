"""Browser/application acceptance without requiring network or a live model."""
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from holon.cli import main
from holon.inference.inference import Interpretation
from holon.web.application import Application, Conflict
from holon.web.server import Handler
from holon.workspace.operations import StalePreview
from holon.workspace.service import Workspace


class FakeInterpreter:
    def __init__(self, relation='supports'):
        self.relation = relation

    def interpret(self, proposition, report):
        return Interpretation(self.relation, 'Same door and instant.', 'test:model')


class BrowserWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'browser.sqlite3'
        self.app = Application(self.path, interpreter_factory=lambda _: FakeInterpreter())
        self.pid = self.command('propose', claim='Door closed', scope='Lab at T0')['proposition_id']

    def command(self, operation, **arguments):
        return self.app.command({'operation': operation, 'arguments': arguments, 'request_id': str(uuid4())})

    def preview(self, kind='report', **arguments):
        if not arguments:
            arguments = dict(proposition_id=self.pid, source='sensor A', report='Closed at T0')
        return self.app.preview({'kind': kind, 'arguments': arguments, 'model': 'test:model'})

    def state(self):
        with self.app.workspace() as workspace:
            return workspace.inspect(self.pid, projection_policy='binary-beta-v1')

    def test_full_observe_interpret_accept_correct_reinterpret_withdraw_workflow(self):
        oid = self.command('observe', source='A', report='Closed at T0', observed_at='2026-11-06T12:00:00-05:00')['observation_id']
        preview = self.preview('observation', observation_id=oid, proposition_id=self.pid)
        self.assertEqual(self.state()['evidence'], [])
        result = self.command('accept', token=preview['token'])
        self.assertEqual(result['status'], 'supported')
        corrected = self.command('correct', evidence_id=result['evidence_id'], actor='reviewer', reason='Bad report',
                                 source='A', report='Open at T0', relation='contradicts')
        reinterpreted = self.command('reinterpret', evidence_id=corrected['replacement_evidence_id'],
                                    actor='reviewer', reason='Wrong relation', relation='supports')
        self.command('withdraw', evidence_id=reinterpreted['replacement_evidence_id'], actor='reviewer', reason='No longer usable')
        state = self.state()
        self.assertEqual(state['status'], 'insufficient_evidence')
        self.assertEqual([r['status'] for r in state['history']], ['supported', 'opposed', 'supported', 'insufficient_evidence'])
        self.assertEqual(len(state['evidence']), 3)
        self.assertEqual(state['evidence'][0]['observed_at'], '2026-11-06T17:00:00.000000+00:00')
        self.assertEqual(state['evidence'][1]['observation_id'], state['evidence'][2]['observation_id'])
        self.assertNotEqual(oid, state['evidence'][1]['observation_id'])
        self.assertEqual(state['projection']['readout']['evidence_strength'], 0)

    def test_browsing_literal_search_filters_pagination_and_reuse(self):
        other = self.command('propose', claim='Door locked 100%', scope='Lab at T0')['proposition_id']
        oid = self.command('observe', source='sensor A', report='Closed and locked')['observation_id']
        for pid in (self.pid, other):
            self.command('link', observation_id=oid, proposition_id=pid, relation='supports')
        with self.app.workspace() as workspace:
            self.assertEqual(len(workspace.list_propositions(query='DOOR', status='supported')), 2)
            self.assertEqual(workspace.list_propositions(query='%')[0]['id'], other)
            self.assertEqual(workspace.list_propositions(limit=1, offset=1)[0]['id'], self.pid)
            self.assertEqual(workspace.list_observations(query='LOCK', source='sensor A')[0]['active_links'], 2)
            self.assertEqual(len(workspace.inspect_observation(oid)['links']), 2)
            for values in ({'limit': 101}, {'offset': -1}, {'limit': True}, {'status': 'certain'}):
                with self.assertRaises(ValueError):
                    workspace.list_propositions(**values)

    def test_receipts_survive_restart_and_reject_changed_requests(self):
        operations = [('propose', dict(claim='Another claim', scope='T0')),
                      ('observe', dict(source='A', report='Another observation')),
                      ('report', dict(proposition_id=self.pid, source='A', report='Closed', relation='supports'))]
        for operation, arguments in operations:
            body = {'operation': operation, 'arguments': arguments, 'request_id': operation}
            first = self.app.command(body)
            restarted = Application(self.path)
            self.assertEqual(first, restarted.command(body))
            changed = dict(body, arguments=dict(arguments, **{next(iter(arguments)): 'changed'}))
            with self.assertRaises(Conflict):
                restarted.command(changed)
        with self.app.workspace() as workspace:
            self.assertEqual(len(workspace.list_propositions()), 2)
            self.assertEqual(len(workspace.list_observations()), 2)
            self.assertEqual(len(workspace.inspect(self.pid)['history']), 1)

    def test_accept_is_once_even_with_different_request_ids_and_restart(self):
        token = self.preview()['token']
        first = self.command('accept', token=token)
        self.assertEqual(first, self.command('accept', token=token))
        self.app = Application(self.path)
        self.assertEqual(first, self.command('accept', token=token))
        self.assertEqual(len(self.state()['evidence']), 1)

    def test_concurrent_duplicate_submissions_commit_once(self):
        body = {'operation': 'report', 'request_id': 'concurrent', 'arguments':
                dict(proposition_id=self.pid, source='A', report='Closed', relation='supports')}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.app.command(body), range(4)))
        self.assertTrue(all(item == results[0] for item in results))
        self.assertEqual(len(self.state()['history']), 1)

    def test_receipt_failure_rolls_back_entire_mutation_and_allows_retry(self):
        with self.app.workspace() as workspace:
            workspace.db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON browser_receipts BEGIN SELECT RAISE(ABORT, 'injected'); END")
        before = self.state()
        body = {'operation': 'report', 'request_id': 'rollback', 'arguments':
                dict(proposition_id=self.pid, source='A', report='Closed', relation='supports')}
        with self.assertRaises(sqlite3.IntegrityError):
            self.app.command(body)
        self.assertEqual(self.state(), before)
        with self.app.workspace() as workspace:
            self.assertEqual(len(workspace.list_observations()), 0)
            workspace.db.execute('DROP TRIGGER reject_receipt')
        self.app.command(body)
        self.assertEqual(len(self.state()['history']), 1)

    def test_stale_preview_from_cli_change_is_rejected_atomically(self):
        preview = self.preview()
        with self.app.workspace() as workspace:
            workspace.add_report(self.pid, 'B', 'Open', 'contradicts')
        before = self.state()
        with self.assertRaises(StalePreview):
            self.command('accept', token=preview['token'])
        self.assertEqual(self.state(), before)

    def test_change_during_model_call_does_not_lock_database_and_invalidates_preview(self):
        class Competing:
            def interpret(inner, proposition, report):
                with WorkspaceContext(self.path) as workspace:
                    workspace.add_report(self.pid, 'B', 'Open', 'contradicts')
                return Interpretation('supports', 'Match', 'test')
        self.app.interpreter_factory = lambda _: Competing()
        preview = self.preview()
        with self.assertRaises(StalePreview):
            self.command('accept', token=preview['token'])
        self.assertEqual(len(self.state()['evidence']), 1)

    def test_reinterpret_preview_observation_is_retained_and_withdrawal_invalidates(self):
        old = self.command('report', proposition_id=self.pid, source='A', report='Closed', relation='contradicts')
        preview = self.preview('reinterpret', evidence_id=old['evidence_id'], actor='reviewer', reason='Model review')
        replacement = self.command('accept', token=preview['token'])
        self.assertEqual(old['observation_id'], replacement['observation_id'])
        self.assertEqual(self.state()['status'], 'supported')
        again = self.preview('reinterpret', evidence_id=replacement['replacement_evidence_id'], actor='reviewer', reason='Again')
        self.command('withdraw', evidence_id=replacement['replacement_evidence_id'], actor='reviewer', reason='Withdraw')
        with self.assertRaises(StalePreview):
            self.command('accept', token=again['token'])

    def test_decline_expiry_restart_abstention_and_model_errors_do_not_write_evidence(self):
        token = self.preview()['token']
        self.app.discard({'token': token})
        with self.assertRaises(Conflict):
            self.command('accept', token=token)
        self.app.preview_ttl = -1
        token = self.preview()['token']
        with self.assertRaises(Conflict):
            self.command('accept', token=token)
        self.app.preview_ttl = 1800
        token = self.preview()['token']
        restarted = Application(self.path)
        with self.assertRaises(Conflict):
            restarted.command({'operation': 'accept', 'arguments': {'token': token}, 'request_id': 'restart'})
        for relation in ('unrelated', 'uncertain'):
            self.app.interpreter_factory = lambda _, r=relation: FakeInterpreter(r)
            preview = self.preview()
            self.assertFalse(preview['acceptable'])
            with self.assertRaises(ValueError):
                self.command('accept', token=preview['token'])
        with patch.object(FakeInterpreter, 'interpret', side_effect=OSError('offline')):
            self.app.interpreter_factory = lambda _: FakeInterpreter()
            with self.assertRaises(OSError):
                self.preview()
        self.assertEqual(self.state()['history'], [])
        with self.app.workspace() as workspace:
            self.assertEqual(len(workspace.list_observations()), 0)

    def test_invalid_commands_are_rejected_without_writes(self):
        for arguments in [dict(claim=[], scope='T0'), dict(claim='test', scope='T0', database='/other'), dict(claim='', scope='T0')]:
            with self.assertRaises(ValueError):
                self.command('propose', **arguments)
        for mass in (True, float('nan'), -1, '1'):
            with self.assertRaises(ValueError):
                self.command('report', proposition_id=self.pid, source='A', report='Closed', relation='supports', mass=mass)
        self.assertEqual(self.state()['history'], [])

    def test_cli_and_browser_produce_equivalent_evidence_and_history(self):
        cli_path = Path(self.temp.name) / 'cli.sqlite3'
        def cli(*args, model=False):
            with patch('sys.argv', ['holon', '--db', str(cli_path), *args]), patch('sys.stdout', new_callable=io.StringIO) as out, \
                 patch('builtins.input', return_value='yes'), patch('holon.cli.OllamaInterpreter.interpret', return_value=Interpretation('supports', 'Same door and instant.', 'test:model')):
                main()
                # Model commands print a preview followed by the result.
                decoder = json.JSONDecoder()
                text = out.getvalue().lstrip()
                result, end = decoder.raw_decode(text)
                if model:
                    result, _ = decoder.raw_decode(text[end:].lstrip())
                return result
        pid = cli('propose', 'Door closed', '--scope', 'Lab at T0')['proposition_id']
        cli_evidence = cli('interpret', pid, '--source', 'sensor A', '--text', 'Closed at T0', model=True)
        browser_evidence = self.command('accept', token=self.preview()['token'])
        cli_replacement = cli('correct', cli_evidence['evidence_id'], '--source', 'A', '--text', 'Open', '--relation', 'contradicts', '--actor', 'reviewer', '--reason', 'Correction')
        browser_replacement = self.command('correct', evidence_id=browser_evidence['evidence_id'], source='A', report='Open', relation='contradicts', actor='reviewer', reason='Correction')
        cli('withdraw', cli_replacement['replacement_evidence_id'], '--actor', 'reviewer', '--reason', 'Withdraw')
        self.command('withdraw', evidence_id=browser_replacement['replacement_evidence_id'], actor='reviewer', reason='Withdraw')
        with WorkspaceContext(cli_path) as workspace:
            cli_state = workspace.inspect(pid, projection_policy='binary-beta-v1')
        browser_state = self.state()
        keys = ('relation', 'source', 'report', 'observed_at', 'model', 'reason', 'prompt_version', 'active', 'withdrawal_actor', 'withdrawal_reason')
        for left, right in zip(cli_state['evidence'], browser_state['evidence']):
            self.assertEqual({k: left[k] for k in keys}, {k: right[k] for k in keys})
        self.assertEqual(len(cli_state['evidence']), len(browser_state['evidence']))
        self.assertEqual([(r['status'], r['policy'], len(r['evidence_ids'])) for r in cli_state['history']],
                         [(r['status'], r['policy'], len(r['evidence_ids'])) for r in browser_state['history']])
        for key in ('mean', 'variance', 'effective_support', 'effective_contradiction', 'evidence_strength'):
            self.assertEqual(cli_state['projection']['readout'][key], browser_state['projection']['readout'][key])

    def http(self, path, body=None, headers=None, raw=None):
        handler = Handler.__new__(Handler)
        handler.server = SimpleNamespace(application=self.app, server_port=8765)
        handler.path = path
        handler.headers = Message()
        values = {'Host': '127.0.0.1:8765'}
        encoded = raw if raw is not None else json.dumps(body).encode()
        if body is not None or raw is not None:
            values.update({'Content-Type': 'application/json', 'Content-Length': str(len(encoded)), 'X-Holon-Token': self.app.csrf})
        values.update(headers or {})
        for key, value in values.items():
            handler.headers[key] = value
        handler.connection = SimpleNamespace(settimeout=lambda _: None)
        handler.rfile, handler.wfile = io.BytesIO(encoded), io.BytesIO()
        response = {}
        handler.send_response = lambda status: response.update(status=status)
        handler.send_header = lambda key, value: response.update({key: value})
        handler.end_headers = lambda: None
        if body is not None or raw is not None:
            handler.do_POST()
        else:
            handler.do_GET()
        response['body'] = handler.wfile.getvalue()
        return response

    def test_http_routes_assets_headers_validation_and_origin_protection(self):
        for path in ('/', '/app.js', '/structure.js', '/style.css'):
            response = self.http(path)
            self.assertEqual(response['status'], 200)
            self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
            self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.http('/api/propositions')['status'], 200)
        self.assertEqual(self.http('/api/propositions/' + self.pid)['status'], 200)
        self.assertEqual(self.http('/api/observations/missing')['status'], 404)
        self.assertEqual(self.http('/api/propositions?limit=-1')['status'], 400)
        self.assertEqual(self.http('/api/propositions?limit=1&limit=2')['status'], 400)
        self.assertEqual(self.http('/api/unknown')['status'], 404)
        self.assertEqual(self.http('/api/workspace', headers={'Host': 'evil.example'})['status'], 403)
        self.assertEqual(self.http('/api/workspace', headers={'Origin': 'https://evil.example'})['status'], 403)
        body = {'operation': 'observe', 'arguments': {'source': 'A', 'report': '<script>not executable</script>'}, 'request_id': 'http'}
        self.assertEqual(self.http('/api/commands', body, headers={'X-Holon-Token': ''})['status'], 403)
        self.assertEqual(self.http('/api/commands', body, headers={'Origin': 'null'})['status'], 403)
        self.assertEqual(self.http('/api/commands', body, headers={'Content-Length': '300000'})['status'], 400)
        self.assertEqual(self.http('/api/commands', raw=b'{') ['status'], 400)
        self.assertEqual(self.http('/api/commands', raw=b'[]')['status'], 400)
        result = self.http('/api/commands', body, headers={'Origin': 'http://127.0.0.1:8765'})
        self.assertEqual(result['status'], 200)
        oid = json.loads(result['body'])['observation_id']
        self.assertEqual(json.loads(self.http('/api/observations/' + oid)['body'])['observation']['report'], body['arguments']['report'])
        self.assertEqual(self.http('/api/commands', dict(body, arguments={'source': 'B', 'report': 'changed'}))['status'], 409)
        preview = self.preview()
        self.command('report', proposition_id=self.pid, source='B', report='Open', relation='contradicts')
        self.assertEqual(self.http('/api/commands', {'operation': 'accept', 'arguments': {'token': preview['token']}, 'request_id': 'stale-http'})['status'], 409)
        with patch.object(self.app, 'preview', side_effect=OSError('offline')):
            self.assertEqual(self.http('/api/preview', {})['status'], 503)


class WorkspaceContext:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.workspace = Workspace(self.path)
        return self.workspace

    def __exit__(self, *args):
        self.workspace.close()
