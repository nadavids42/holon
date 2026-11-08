"""Loopback-only HTTP transport for the research workspace (not deployment)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from holon.web.application import Application, Conflict
from holon.workspace.operations import StalePreview
from holon.workspace.derivation_storage import LineageConflict


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, application, port=8765):
        self.application = application
        super().__init__(('127.0.0.1', port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Avoid logging reports, search strings, tokens, and database paths.
        pass

    def _send(self, status, value, content_type='application/json; charset=utf-8'):
        body = json.dumps(value, allow_nan=False).encode() if content_type.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _allowed(self, write=False):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        host = self.headers.get('Host')
        origin = self.headers.get('Origin')
        if host not in hosts or (origin is not None and origin != 'http://' + host):
            self._send(403, {'error': 'Only same-origin local requests are allowed'})
            return False
        if write and not secrets.compare_digest(self.headers.get('X-Holon-Token', '').encode(), self.server.application.csrf.encode()):
            self._send(403, {'error': 'Reload the workspace before submitting'})
            return False
        return True

    def do_GET(self):
        if not self._allowed():
            return
        path = urlsplit(self.path)
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/structure.js': ('structure.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path.path in assets:
            name, mime = assets[path.path]
            self._send(200, files('holon.web').joinpath('static', name).read_bytes(), mime)
            return
        try:
            app = self.server.application
            if path.path == '/api/workspace':
                self._send(200, app.info())
                return
            query = parse_qs(path.query, keep_blank_values=True)
            if any(len(values) != 1 for values in query.values()):
                raise ValueError('Repeated query parameters are not supported')
            query = {key: values[0] for key, values in query.items()}
            with app.workspace() as workspace:
                if path.path in ('/api/propositions', '/api/observations'):
                    propositions = path.path.endswith('propositions')
                    allowed = {'q', 'limit', 'offset', 'status' if propositions else 'source'}
                    if set(query) - allowed:
                        raise ValueError('Unknown filter')
                    arguments = dict(query=query.get('q', ''), limit=int(query.get('limit', 50)),
                                     offset=int(query.get('offset', 0)))
                    if propositions:
                        rows = workspace.list_propositions(status=query.get('status', ''), **arguments)
                    else:
                        rows = workspace.list_observations(source=query.get('source', ''), **arguments)
                    result = {'items': rows}
                elif path.path in ('/api/derivations', '/api/lineage'):
                    if query:
                        raise ValueError('This route returns the whole workspace; filters are not supported')
                    result = (workspace.inspect_derivations() if path.path == '/api/derivations'
                              else workspace.inspect_lineage())
                elif path.path.startswith('/api/propositions/'):
                    result = workspace.inspect(path.path.removeprefix('/api/propositions/'), projection_policy='binary-beta-v1')
                elif path.path.startswith('/api/observations/'):
                    result = workspace.inspect_observation(path.path.removeprefix('/api/observations/'))
                else:
                    self._send(404, {'error': 'Unknown route'})
                    return
            self._send(200, result)
        except ValueError as error:
            self._send(404 if str(error).startswith(('Unknown proposition:', 'Unknown observation:')) else 400,
                       {'error': str(error)})
        except (sqlite3.Error, OSError):
            self._send(503, {'error': 'Workspace unavailable or busy. Retry the request.'})

    def do_POST(self):
        if not self._allowed(write=True):
            return
        routes = {'/api/commands': self.server.application.command,
                  '/api/preview': self.server.application.preview,
                  '/api/discard': self.server.application.discard}
        if self.path not in routes:
            self._send(404, {'error': 'Unknown route'})
            return
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Content-Type must be application/json')
            size = int(self.headers.get('Content-Length', '-1'))
            if not 0 < size <= 262144 or self.headers.get('Transfer-Encoding'):
                raise ValueError('A JSON body of at most 256 KiB is required')
            self.connection.settimeout(10)
            body = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
            result = routes[self.path](body)
            self._send(200, result)
        except (Conflict, StalePreview, LineageConflict) as error:
            self._send(409, {'error': str(error)})
        except (ValueError, UnicodeError) as error:
            self._send(400, {'error': str(error)})
        except (sqlite3.Error, OSError):
            self._send(503, {'error': 'Workspace or model unavailable. Check the model server and retry.'})


def serve(path, *, port=8765, **options):
    if not 0 <= port <= 65535:
        raise ValueError('Port must be between 0 and 65535')
    app = Application(path, **options)
    # Explicit server startup initializes/upgrades only the selected workspace.
    with app.workspace():
        pass
    with LocalServer(app, port) as server:
        print(f'Holon workspace: {app.path}', flush=True)
        print(f'Open http://127.0.0.1:{server.server_port} (Ctrl+C to stop)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
