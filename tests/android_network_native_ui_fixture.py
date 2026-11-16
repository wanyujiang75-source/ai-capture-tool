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
    parser.add_argument('--ios-guidance', action='store_true', help='Show synthetic iPhone setup instructions')
    parser.add_argument('--confirm-recovery', action='store_true', help='Enable confirmation for the synthetic device only')
    args = parser.parse_args()
    scenario = {'state': 'recovery_required' if args.confirm_recovery else 'waiting'}

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
                if scenario['state'] in {'idle', 'preparing', 'failed', 'recovery_required', 'stopped'}:
                    value['phase'] = scenario['state']
                    value.pop('application_network')
                    value.pop('phone_network')
                    value.pop('upstream_network')
                if scenario['state'] == 'recovery_required' and not args.confirm_recovery:
                    value['pending_recoveries'] = [{'serial': 'synthetic', 'name': '[合成验收] 无真实手机'}]
            elif path == '/api/ios-setup':
                value = {'phase': 'idle', 'flow_count': 0, 'flows': [], 'recording_state': 'idle'}
                if args.ios_guidance:
                    value.update(phase='waiting_phone', certificate_name='Synthetic Preview CA',
                                 profile_path='/tmp/capture-copy-preview/ios-setup/iPhone.mobileconfig')
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
                             'quiet', 'unverified', 'unavailable', 'idle', 'preparing', 'failed', 'recovery_required'}:
                self.reply(400, {})
                return
            scenario['state'] = state
            self.reply(200, scenario)

        def do_POST(self):
            if args.confirm_recovery and self.path == '/api/android-physical/confirm-network/synthetic':
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 128 and json.loads(self.rfile.read(size)) == {'confirmed': True}:
                    scenario['state'] = 'stopped'
                    self.reply(200, {'phase': 'stopped', 'message': '已由用户确认当前网络正常，恢复提醒已解除。'})
                    return
            self.reply(409, {'detail': 'Synthetic view only: no capture or phone access'})

        def reply(self, code, value):
            data = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
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
