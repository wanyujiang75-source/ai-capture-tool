"""Isolated BP-1 worker for process-boundary tests; never attaches to a proxy."""

import asyncio
import json
from pathlib import Path
import sys

from capture_console.breakpoints.engine import BreakpointEngine
from capture_console.breakpoints.ipc import WorkerServer


async def main():
    engine = BreakpointEngine('fixture', 'fixture-device')
    worker = WorkerServer(Path(sys.argv[1]), engine)
    try:
        await worker.start()
        print(json.dumps({'path': str(worker.path), 'token': worker.token, 'epoch': engine.epoch}), flush=True)
        async with asyncio.timeout(10):
            while not engine.stopped:
                await asyncio.sleep(0.05)
    finally:
        await worker.close()


if __name__ == '__main__':
    asyncio.run(main())
