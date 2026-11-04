"""Opt-in iPhone recording adapter; authenticated phone admission stays in PairingMonitor."""

from ..ios_projects import domain_matches
from ..ios_recording import IOSRecording
from .runtime import RecordingRuntime


class IOSBreakpointRecording(IOSRecording):
    def __init__(self, config, state):
        super().__init__(config, state)
        self.runtime = None
        self.master = None

    async def apply(self, command, switch):
        if command['revision'] <= self.state['applied_revision']:
            return
        if command['action'] == 'stop':
            await self.drain()
            super().apply(command, switch)
            return
        if self.state['recording_state'] == 'recording':
            raise ValueError('请先停止当前抓包。')
        await self.drain()
        super().apply(command, switch)
        self.state['recording_state'] = 'preparing'
        self.runtime = RecordingRuntime(self.master, command['outdir'], str(command['session_id']), 'iphone')
        self.archive = self.runtime.archive
        await self.runtime.start()
        self.state['recording_state'] = 'recording'

    async def drain(self):
        runtime = self.runtime
        if runtime:
            await runtime.close()
            if self.runtime is runtime:
                self.runtime = None

    def check_limit(self, switch):
        if self.archive and self.archive.closed and self.runtime:
            self.runtime.addon.engine.stop()
        super().check_limit(switch)

    def invalidate_phone(self):
        if self.runtime:
            self.runtime.addon.engine.stop()
        super().invalidate_phone()

    def requestheaders(self, flow):
        if (self.state['recording_state'] != 'recording' or not self.runtime
                or flow.request.host.lower().rstrip('.') == 'capture-check.invalid'
                or self.domains is not None and not domain_matches(flow.request.host, self.domains)):
            return
        self.runtime.requestheaders(flow)
        if self.runtime.owns(flow):
            self.state['flow_count'] += 1

    def responseheaders(self, flow):
        if self.runtime:
            self.runtime.responseheaders(flow)

    def request(self, flow):
        pass  # PairingBreakpointMonitor awaits the transport decision.

    def finish(self, flow):
        if flow.error and self.runtime:
            self.runtime.error(flow)
