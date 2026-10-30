"""Wire-test process: synthetic phone identity and a test-only upstream trust root."""

import asyncio
import json
from functools import partial
import sys
from pathlib import Path

from capture_console import ios_pairing_proxy as proxy
from capture_console import ios_recording


if __name__ == "__main__":
    config = json.loads(Path(sys.argv[1]).read_text())
    real_master = proxy.DumpMaster

    def trusted_test_master(options, **kwargs):
        master = real_master(options, **kwargs)
        options.update(ssl_verify_upstream_trusted_ca=sys.argv[2])
        return master

    # Only this isolated test process treats the Mac client as a synthetic phone.
    # Production still rejects Mac self-checks as proof of phone readiness.
    proxy.PairingMonitor.eligible_phone = lambda self, flow: self.authenticated(flow)
    ios_recording.IOSCaptureArchive = partial(ios_recording.IOSCaptureArchive, record_limit=2)
    proxy.DumpMaster = trusted_test_master
    asyncio.run(proxy.run(config))
