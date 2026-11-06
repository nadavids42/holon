"""Public-only replay. Methods receive JSON views, never a private bundle."""
from copy import deepcopy

from .schema import VERSION, digest, keys, require, validate_public, validate_response


class Replay:
    def __init__(self, public):
        validate_public(public)
        self._public = deepcopy(public)
        self._cursor = 0
        self._responses = []
        self._restart_required = False

    def pending_task(self):
        if not self._cursor:
            return None
        last = self._public['events'][self._cursor - 1]
        if last['kind'] == 'task' and last['payload']['id'] not in {r['task_id'] for r in self._responses}:
            return deepcopy(last['payload'])
        return None

    def advance(self):
        require(self.pending_task() is None, 'Answer the pending task before advancing')
        require(not self._restart_required, 'Save and restore the checkpoint before continuing')
        require(self._cursor < len(self._public['events']), 'Episode is complete')
        event = deepcopy(self._public['events'][self._cursor])
        self._cursor += 1
        self._restart_required = event['kind'] == 'restart'
        return event

    def advance_to_boundary(self):
        if self.pending_task() or self._restart_required:
            return self.view()
        while self._cursor < len(self._public['events']):
            self.advance()
            if self.pending_task() or self._restart_required:
                break
        return self.view()

    def submit(self, response):
        task = self.pending_task()
        require(task is not None, 'No pending task')
        validate_response(response, task)
        # Availability and correctness are scored offline. No grading feedback here.
        self._responses.append(deepcopy(response))

    def view(self):
        return dict(schema_version=VERSION, episode_id=self._public['episode_id'],
                    project_id=self._public['project_id'], rules=deepcopy(self._public['rules']),
                    events=deepcopy(self._public['events'][:self._cursor]),
                    audit_queries=deepcopy([a for a in self._public['audit_queries']
                                           if a['after_task_id'] in {r['task_id'] for r in self._responses}]),
                    pending_task=self.pending_task(), restart_required=self._restart_required,
                    complete=self._cursor == len(self._public['events']) and self.pending_task() is None)

    def checkpoint(self):
        return dict(schema_version=VERSION, public_digest=digest(self._public),
                    cursor=self._cursor, responses=deepcopy(self._responses))

    @classmethod
    def restore(cls, public, checkpoint):
        keys(checkpoint, 'schema_version public_digest cursor responses')
        require(checkpoint['schema_version'] == VERSION and checkpoint['public_digest'] == digest(public),
                'Checkpoint belongs to a different public schedule')
        cursor = checkpoint['cursor']
        require(type(cursor) is int and 0 <= cursor <= len(public['events']), 'Invalid checkpoint cursor')
        require(isinstance(checkpoint['responses'], list), 'Invalid saved responses')
        replay = cls(public)
        response_index = 0
        # Replay validates sequence and responses; no arbitrary future cursor jumps.
        while replay._cursor < cursor:
            if replay.pending_task():
                require(response_index < len(checkpoint['responses']), 'Checkpoint skipped an unanswered task')
                replay.submit(checkpoint['responses'][response_index])
                response_index += 1
            replay._restart_required = False  # Restoration is the restart acknowledgement.
            replay.advance()
        if replay.pending_task() and response_index < len(checkpoint['responses']):
            replay.submit(checkpoint['responses'][response_index])
            response_index += 1
        require(response_index == len(checkpoint['responses']), 'Checkpoint has extra/reordered responses')
        replay._restart_required = False
        return replay

    def responses(self):
        return dict(schema_version=VERSION, episode_id=self._public['episode_id'],
                    public_digest=digest(self._public), responses=deepcopy(self._responses))
