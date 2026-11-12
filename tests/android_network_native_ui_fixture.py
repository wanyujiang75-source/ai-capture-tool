"""Loopback synthetic visual acceptance; never accesses phones, VPNs or proxies.

Run as a module with a matching --build-id. PUT /__scenario with a state to
exercise the view. All real capture actions return 409.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-id', required=True)
    args = parser.parse_args()
    scenario = {'state': 'waiting'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/status':
                value = {'desktop': {'enabled': True, 'build_id': args.build_id}}
            elif path == '/api/android-physical/devices':
                value = {'devices': [{'serial': 'synthetic', 'model': '[合成验收] 无真实手机', 'status': 'device'}]}
            elif path == '/api/android-physical':
                if scenario['state'] == 'unavailable':
                    self.reply(503, {})
                    return
                value = {'phase': 'capturing', 'serial': 'synthetic', 'device_name': '[合成验收] 无真实手机',
                         'phone_network': 'ready', 'upstream_network': 'ready',
                         'flow_count': 20, 'response_count': 10, 'application_network': dict(scenario)}
            elif path == '/api/ios-setup':
                value = {'phase': 'idle', 'connection_state': 'idle', 'recording_state': 'idle'}
            else:
                value = {'devices': [], 'apps': [], 'sessions': [], 'packages': []}
            self.reply(200, value)

        def do_PUT(self):
            size = int(self.headers.get('Content-Length', '0'))
            if self.path != '/__scenario' or not 0 < size <= 128:
                self.reply(400, {})
                return
            state = json.loads(self.rfile.read(size)).get('state')
            if state not in {'waiting', 'responded', 'partial', 'server_error', 'connection_failed',
                             'quiet', 'unverified', 'unavailable'}:
                self.reply(400, {})
                return
            scenario['state'] = state
            self.reply(200, scenario)

        def do_POST(self):
            self.reply(409, {'detail': 'Synthetic view only: no capture or phone access'})

        def reply(self, code, value):
            data = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(f'http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
