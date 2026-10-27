import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from holon.cli import main
from holon.inference.inference import Interpretation
from holon.inference.ollama import OllamaInterpreter
from holon.workspace.service import Workspace


class InterpretationTests(unittest.TestCase):
    def test_adapter_request_and_validation(self):
        envelope = {'model': 'test:model', 'done': True, 'message': {
            'content': json.dumps({'relation': 'contradicts', 'reason': 'Same instant, opposite state.'})}}
        with patch('holon.inference.ollama.urlopen', return_value=io.BytesIO(json.dumps(envelope).encode())) as call:
            result = OllamaInterpreter().interpret({'claim': 'closed', 'scope': 'T0'}, 'open at T0')
        self.assertEqual(result.relation, 'contradicts')
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertFalse(body['stream'])
        self.assertFalse(body['think'])
        self.assertEqual(result.prompt_version, 'report-relation-v2')
        self.assertEqual(json.loads(body['messages'][1]['content'])['report'], 'open at T0')
        for value in [{}, {'relation': 'yes', 'reason': 'x'},
                      {'relation': 'supports', 'reason': ''},
                      {'relation': 'supports', 'reason': 'x', 'extra': 1},
                      {'relation': [], 'reason': 'x'}]:
            with self.assertRaises(ValueError):
                Interpretation.validate(value, 'test')
        for envelope in [{}, {'done': False}, {'done': True, 'message': {'content': 'bad json'}}]:
            with patch('holon.inference.ollama.urlopen', return_value=io.BytesIO(json.dumps(envelope).encode())):
                with self.assertRaises(ValueError):
                    OllamaInterpreter().interpret({'claim': 'closed', 'scope': 'T0'}, 'report')

    def test_cli_acceptance_rejection_abstention_and_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            workspace = Workspace(path)
            pid = workspace.create_proposition('Door closed', 'T0')
            workspace.close()
            argv = ['holon', '--db', str(path), 'interpret', pid,
                    '--source', 'sensor B', '--text', '  open at T0  ']
            def run(proposal, answer='n', error=None):
                with patch('sys.argv', argv), patch('builtins.input', return_value=answer) as prompt, \
                     patch('holon.cli.OllamaInterpreter.interpret', return_value=proposal, side_effect=error), \
                     patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
                    if error:
                        with self.assertRaises(SystemExit) as exit:
                            main()
                        self.assertEqual(exit.exception.code, 2)
                    else:
                        main()
                    return prompt.call_count
            proposal = Interpretation('contradicts', 'Same door at T0.', 'test:model')
            run(proposal)
            for outcome in ['unrelated', 'uncertain']:
                self.assertEqual(run(Interpretation(outcome, 'No match.', 'test')), 0)
            run(None, error=ValueError('malformed'))
            run(None, error=URLError('connection refused'))
            run(None, error=TimeoutError('timed out'))
            workspace = Workspace(path)
            self.assertEqual(workspace.inspect(pid)['history'], [])
            self.assertEqual(workspace.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 0)
            workspace.close()
            run(proposal, 'yes')
            workspace = Workspace(path)
            state = workspace.inspect(pid)
            workspace.close()
            self.assertEqual(state['status'], 'opposed')
            self.assertEqual(state['evidence'][0]['report'], '  open at T0  ')
            self.assertEqual(state['evidence'][0]['model'], 'test:model')
            self.assertEqual(state['evidence'][0]['reason'], proposal.reason)

    def test_existing_database_and_atomic_interpretation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.sqlite3'
            # Simulate a database created before interpretation metadata existed.
            from holon.workspace.storage import SCHEMA
            db = sqlite3.connect(path)
            old = SCHEMA[0:SCHEMA.index('CREATE TABLE IF NOT EXISTS interpretations')] + SCHEMA[SCHEMA.index('CREATE TABLE IF NOT EXISTS revisions'):]
            db.executescript(old)
            db.close()
            workspace = Workspace(path)
            try:
                pid = workspace.create_proposition('closed', 'T0')
                workspace.db.execute("CREATE TRIGGER reject_metadata BEFORE INSERT ON interpretations BEGIN SELECT RAISE(ABORT, 'failure'); END")
                with self.assertRaises(sqlite3.IntegrityError):
                    workspace.add_report(pid, 'A', 'closed', 'supports', Interpretation('supports', 'match', 'test'))
                self.assertEqual(workspace.inspect(pid)['evidence'], [])
                self.assertEqual(workspace.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 0)
            finally:
                workspace.close()
