"""Operation-scoped application boundary with durable command retry receipts."""
from contextlib import contextmanager
import json
import math
from pathlib import Path
import secrets
from threading import Lock
import time

from holon.inference.ollama import OllamaInterpreter
from holon.workspace.metadata import canonical, digest
from holon.workspace.operations import accept_interpretation, preview_interpretation
from holon.workspace.service import Workspace


class Conflict(ValueError):
    pass


def fields(value, required=(), optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional):
        raise ValueError('Unexpected fields or invalid object')
    if set(required) - set(value):
        raise ValueError('Missing fields: ' + ', '.join(sorted(set(required) - set(value))))
    for key, item in value.items():
        if key == 'expected_revision':
            if type(item) is not int or item < 0:
                raise ValueError('expected_revision must be a nonnegative integer')
        elif key == 'group_id' and item is None:
            continue
        elif key == 'conclusion':
            fields(item, ('proposition_id', 'relation'))
        elif key == 'premises':
            if not isinstance(item, list) or not 1 <= len(item) <= 1000:
                raise ValueError('premises must be a nonempty list of at most 1000 signed claims')
            for premise in item:
                fields(premise, ('proposition_id', 'relation'))
        elif key == 'group_ids':
            if not isinstance(item, list) or not 2 <= len(item) <= 1000:
                raise ValueError('group_ids must contain 2–1000 groups')
            for group in item:
                fields({'group_id': group}, ('group_id',))
                if group is None:
                    raise ValueError('Unknown origins cannot be merged')
        elif key == 'mass':
            if type(item) not in (int, float) or not math.isfinite(item) or item < 0:
                raise ValueError('mass must be a finite nonnegative number')
        elif not isinstance(item, str) or len(item) > 100000:
            raise ValueError(f'{key} must be text (at most 100000 characters)')
    return value


# The HTTP adapter cannot dispatch arbitrary service attributes or choose paths.
COMMANDS = {
    'propose': (('claim', 'scope'), ()),
    'observe': (('source', 'report'), ('observed_at',)),
    'report': (('proposition_id', 'source', 'report', 'relation'), ('observed_at', 'mass')),
    'link': (('observation_id', 'proposition_id', 'relation'), ('mass',)),
    'withdraw': (('evidence_id', 'actor', 'reason'), ()),
    'correct': (('evidence_id', 'actor', 'reason', 'source', 'report', 'relation'), ('observed_at', 'mass')),
    'reinterpret': (('evidence_id', 'actor', 'reason', 'relation'), ('mass',)),
    'accept': (('token',), ()),
    'derive': (('justification_id', 'conclusion', 'premises', 'rule', 'actor', 'reason'), ()),
    'assign-origin': (('event_id', 'observation_id', 'group_id', 'actor', 'reason', 'expected_revision'), ()),
    'merge-origins': (('event_id', 'group_ids', 'target_group_id', 'actor', 'reason', 'expected_revision'), ()),
    'reverse-lineage': (('event_id', 'target_event_id', 'actor', 'reason', 'expected_revision'), ()),
}


class Application:
    def __init__(self, path, *, model='qwen3:14b', host='http://127.0.0.1:11434',
                 timeout=120, interpreter_factory=None, preview_ttl=1800):
        self.path = Path(path).expanduser().resolve()
        self.model, self.host = model, host
        self.interpreter_factory = interpreter_factory or (lambda name: OllamaInterpreter(name, host, timeout))
        self.preview_ttl = preview_ttl
        self.previews = {}
        self.lock = Lock()
        self.csrf = secrets.token_urlsafe(32)

    @contextmanager
    def workspace(self):
        workspace = Workspace(self.path)
        try:
            yield workspace
        finally:
            workspace.close()

    def info(self):
        return {'database': str(self.path), 'model': self.model, 'ollama_host': self.host,
                'csrf_token': self.csrf}

    def _purge(self):
        now = time.monotonic()
        self.previews = {key: value for key, value in self.previews.items() if value[0] > now}

    def preview(self, body):
        if not isinstance(body, dict) or set(body) != {'kind', 'arguments', 'model'}:
            raise ValueError('Preview requires kind, arguments and model')
        kind, arguments, model = body['kind'], body['arguments'], body['model']
        fields({'kind': kind, 'model': model}, ('kind', 'model'))
        if not model.strip() or len(model) > 200:
            raise ValueError('Model name must be 1–200 characters')
        schemas = {
            'report': (('proposition_id', 'source', 'report'), ('observed_at', 'mass')),
            'observation': (('proposition_id', 'observation_id'), ('mass',)),
            'reinterpret': (('evidence_id', 'actor', 'reason'), ('mass',)),
        }
        if kind not in schemas:
            raise ValueError('Unknown preview kind')
        fields(arguments, *schemas[kind])
        with self.workspace() as workspace:
            preview = preview_interpretation(workspace, self.interpreter_factory(model), kind, **arguments)
        token = secrets.token_urlsafe(24)
        with self.lock:
            self._purge()
            if len(self.previews) >= 256:
                raise Conflict('Too many pending previews. Discard one or wait for expiry.')
            self.previews[token] = (time.monotonic() + self.preview_ttl, preview)
        return {'token': token, 'preview': preview.display(),
                'acceptable': preview.interpretation.relation in ('supports', 'contradicts')}

    def discard(self, body):
        fields(body, ('token',))
        with self.lock:
            self.previews.pop(body['token'], None)
        return {'discarded': True}

    def command(self, body):
        if not isinstance(body, dict) or set(body) != {'request_id', 'operation', 'arguments'}:
            raise ValueError('Command requires request_id, operation and arguments')
        request_id, operation, arguments = body['request_id'], body['operation'], body['arguments']
        fields({'request_id': request_id, 'operation': operation}, ('request_id', 'operation'))
        if not request_id.strip() or len(request_id) > 200:
            raise ValueError('request_id must be 1–200 characters')
        if operation not in COMMANDS:
            raise ValueError('Unknown operation')
        fields(arguments, *COMMANDS[operation])
        fingerprint = digest(canonical({'operation': operation, 'arguments': arguments}))
        # A proposal is accepted at most once, even under a different request ID.
        key = 'preview:' + arguments['token'] if operation == 'accept' else 'request:' + request_id
        with self.workspace() as workspace, workspace.transaction():
            workspace._begin(immediate=True)
            workspace.db.execute('''CREATE TABLE IF NOT EXISTS browser_receipts (
                request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, result_json TEXT NOT NULL)''')
            prior = workspace.db.execute('SELECT * FROM browser_receipts WHERE request_id=?', (key,)).fetchone()
            if prior:
                if prior['request_digest'] != fingerprint:
                    raise Conflict('Request ID reused with different content')
                return json.loads(prior['result_json'])
            if operation == 'accept':
                with self.lock:
                    self._purge()
                    entry = self.previews.get(arguments['token'])
                if entry is None:
                    raise Conflict('Preview expired, was discarded, or server restarted. Generate a fresh preview.')
                result = accept_interpretation(workspace, entry[1])
            elif operation == 'propose':
                result = {'proposition_id': workspace.create_proposition(**arguments)}
            elif operation == 'observe':
                result = {'observation_id': workspace.record_observation(**arguments)}
            else:
                method = {'report': workspace.add_report, 'link': workspace.link_observation,
                          'withdraw': workspace.withdraw_evidence, 'correct': workspace.withdraw_evidence,
                          'reinterpret': workspace.reinterpret_evidence,
                          'derive': workspace.add_derivation, 'assign-origin': workspace.assign_origin,
                          'merge-origins': workspace.merge_origins,
                          'reverse-lineage': workspace.reverse_lineage}[operation]
                result = method(**arguments)
            workspace.db.execute('INSERT INTO browser_receipts VALUES (?, ?, ?)',
                                 (key, fingerprint, canonical(result)))
            return result
