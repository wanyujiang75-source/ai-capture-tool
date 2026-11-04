"""Bounded original/effective archive shared by opt-in Android and iOS workers."""

import hashlib
import os
import secrets
import stat

from ..ios_results import IOSCaptureArchive
from .models import BODY_LIMIT


class BreakpointArchive(IOSCaptureArchive):
    @staticmethod
    def snapshot(flow, stage):
        message = getattr(flow, stage)
        return dict(url=flow.request.url, method=flow.request.method,
                    status=message.status_code if stage == 'response' else None,
                    headers=list(message.headers.items(multi=True)), body=message.raw_content or b'')

    def record_decision(self, flow, stage, original, action, reason):
        if self.closed:
            return False
        effective = self.snapshot(flow, stage)
        meta = self._read(flow.id)
        versions = {}
        for label, snapshot in (('original', original), ('effective', effective)):
            data = snapshot['body']
            if len(data) > BODY_LIMIT:
                self._limit('breakpoint_body_limit')
                return False
            digest = hashlib.sha256(data).hexdigest()
            name = digest + '.bp.bin'
            path = self.root / name
            if path.exists() or path.is_symlink():
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as file:
                    info = os.fstat(file.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_size != len(data)
                            or hashlib.sha256(file.read(BODY_LIMIT + 1)).hexdigest() != digest):
                        raise OSError('corrupt breakpoint body')
            else:
                if self.body_bytes + len(data) + 2 * self.index_reserve + 4096 > self.storage_limit:
                    self._limit('storage_limit')
                    return False
                temporary = path.with_name('.' + name + '.' + secrets.token_hex(8))
                try:
                    with temporary.open('xb') as file:
                        temporary.chmod(0o600)
                        if file.write(data) != len(data):
                            raise OSError('short breakpoint body write')
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
                self.body_bytes += len(data)
            versions[label] = {k: v for k, v in snapshot.items() if k != 'body'}
            versions[label].update(body_file=name, body_size=len(data), sha256=digest)
        versions.update(action=action, reason=reason, adopted=action != 'abort', delivered=False)
        meta.setdefault('breakpoints', {})[stage] = versions
        self._write(flow.id, meta)
        return not self.closed

    def request_complete(self, flow):
        if self.closed:
            return
        meta = self._read(flow.id)
        request = flow.request
        meta.update(url=request.url, path=request.path, host=request.host, method=request.method,
                    request_headers=list(request.headers.items(multi=True)))
        self._write(flow.id, meta)
        super().request_complete(flow)

    def detail(self, flow_id):
        result = super().detail(flow_id)
        result['breakpoints'] = self._read(flow_id).get('breakpoints', {})
        return result
