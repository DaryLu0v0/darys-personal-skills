"""Loopback dashboard; research is read-only, private attention decisions are local."""
import argparse
import json
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from library import ROOT, load_library
from attention import projection, decide

ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/attention.js': ('attention.js', 'text/javascript'), '/literature.js': ('literature.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
ACTION_TOKEN = secrets.token_urlsafe(32)


class LoopbackServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Windows SO_REUSEADDR permits competing listeners on the same port.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/api/attention/decision':
            self.send_error(501); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length < 4000: self.send_error(413); return
            self.connection.settimeout(5)
            request_body=self.rfile.read(length)
        except (ValueError,OSError):
            self.send_error(400); return
        host = self.headers.get('Host','')
        if (host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                or self.headers.get('Origin') != 'http://' + host
                or self.headers.get('X-Hikari-Token') != ACTION_TOKEN):
            self.send_error(403); return
        if self.headers.get('Content-Type') != 'application/json':
            self.send_error(415); return
        try:
            result = decide(ROOT, json.loads(request_body))
            result['action_token'] = ACTION_TOKEN
            self.send_json(result)
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.send_json({'error':str(error)},409)

    def send_json(self, value, status=200):
        body=json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host', '').split(':')[0] not in {'127.0.0.1', 'localhost'}:
            self.send_error(403); return
        path = urlsplit(self.path).path
        try:
            if path == '/api/attention':
                host=self.headers.get('Host','')
                if self.headers.get('Origin') not in {None,'http://'+host} or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    self.send_error(403); return
                value=projection(ROOT); value['action_token']=ACTION_TOKEN
                self.send_json(value); return
            elif path == '/api/library':
                body = json.dumps(load_library(ROOT), ensure_ascii=False).encode('utf-8')
                content_type = 'application/json'
            elif path in ASSETS:
                filename, content_type = ASSETS[path]
                body = (ROOT / 'dashboard' / filename).read_bytes()
            else:
                self.send_error(404); return
        except (ValueError, OSError, KeyError, TypeError) as error:
            body = json.dumps({'error': f'Library unavailable: {error}'}).encode('utf-8')
            content_type = 'application/json'
            self.send_response(503)
        else:
            self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers(); self.wfile.write(body)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8767)
    args = p.parse_args()
    server = LoopbackServer(('127.0.0.1', args.port), Handler)
    print(f'Hikari library: http://127.0.0.1:{server.server_port}/ (local attention; read-only research)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
