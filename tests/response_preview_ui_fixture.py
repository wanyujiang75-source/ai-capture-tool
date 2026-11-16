"""Local UI fixture with synthetic data; never contacts devices or real capture services."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/status':
            value = {'desktop': {'enabled': True, 'build_id': 'response-preview-fixture'}}
        elif path == '/api/captures':
            value = {'sessions': [{'id': 1, 'platform': 'android', 'mode': 'android-physical-wireguard',
                                   'status': 'stopped', 'app_name': '合成验收'}]}
        elif path == '/api/captures/1/flows':
            value = {'flows': [{'id': 'synthetic', 'method': 'GET', 'status': '200',
                                'url': 'https://example.invalid/synthetic'}],
                     'total': 1, 'cursor': 1, 'next_cursor': None}
        elif path == '/api/captures/1/flows/synthetic':
            value = {'id': 'synthetic', 'status': '200', 'url': 'https://example.invalid/synthetic',
                     'response_text': '中文' + 'a' * (256 * 1024),
                     'response_body': {'kind': 'text', 'size_bytes': 4 * 1024 * 1024, 'truncated': True}}
        elif path == '/api/ios-setup':
            value = {'phase': 'idle', 'flow_count': 0, 'flows': []}
        elif path == '/api/android-physical':
            value = {'phase': 'idle'}
        else:
            value = {'devices': [], 'apps': [], 'sessions': [], 'packages': []}
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.send_error(409)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
