import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from capture_console.android_physical_api import physical_router


class PhysicalAPITests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.status.return_value = {'phase': 'idle'}
        self.service.start.return_value = {'phase': 'preparing'}
        self.app = FastAPI()
        self.app.include_router(physical_router(self.service))
        self.headers = {'X-Capture-Desktop': 'android-physical'}

    def request(self, method, path, *, headers, payload=None):
        async def exchange():
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': json.dumps(payload).encode(), 'more_body': False}
            async def send(message):
                messages.append(message)
            fields = {'Host': '127.0.0.1', 'Content-Type': 'application/json', **headers}
            await self.app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                            'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
                            'query_string': b'', 'root_path': '', 'server': ('127.0.0.1', 80),
                            'client': ('127.0.0.1', 1234),
                            'headers': [(k.lower().encode(), v.encode()) for k, v in fields.items()]}, receive, send)
            return SimpleNamespace(status_code=messages[0]['status'],
                                   body=json.loads(b''.join(m.get('body', b'') for m in messages)))
        return asyncio.run(exchange())

    def test_browser_and_foreign_origin_cannot_control_capture(self):
        for headers in ({}, {**self.headers, 'Origin': 'https://example.org'}):
            self.assertEqual(self.request('POST', '/api/android-physical/stop', headers=headers).status_code, 403)
        self.service.stop.assert_not_called()

    def test_rebinding_host_is_rejected(self):
        response = self.request('GET', '/api/android-physical', headers={**self.headers, 'Host': 'attacker.example'})
        self.assertEqual(response.status_code, 403)
        self.service.status.assert_not_called()

    def test_start_passes_only_explicit_consent_and_selected_device(self):
        payload = {'serial': 'test', 'desktop_pid': 42, 'experimental_consent': True}
        response = self.request('POST', '/api/android-physical/start', headers=self.headers, payload=payload)
        self.assertEqual(response.body, {'phase': 'preparing'})
        self.service.start.assert_called_once_with('test', 42, True)
        response = self.request('POST', '/api/android-physical/start', headers=self.headers, payload={**payload, 'config': 'secret'})
        self.assertEqual(response.status_code, 422)

    def test_recovery_conflict_is_a_user_action_not_raw_diagnostics(self):
        self.service.start.side_effect = ValueError('请先恢复网络。')
        response = self.request('POST', '/api/android-physical/start', headers=self.headers,
                                payload={'serial': 'test', 'desktop_pid': 42})
        self.assertEqual((response.status_code, response.body), (409, {'detail': {'user_message': '请先恢复网络。'}}))
