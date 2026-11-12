"""Durable per-phone recovery obligations, independent of the current capture."""

import hashlib
import json


class PendingRecoveries:
    def __init__(self, root):
        self.root = root / 'pending-recovery'
        self.root.mkdir(mode=0o700, exist_ok=True)

    def path(self, serial):
        return self.root / (hashlib.sha256(serial.encode()).hexdigest() + '.json')

    def summaries(self):
        result = []
        for path in sorted(self.root.glob('*.json')):
            info = json.loads(path.read_text())
            result.append({'serial': info['serial'], 'name': info.get('name', '')})
        return result

    def defer(self, marker):
        if marker.exists():
            info = json.loads(marker.read_text())
            marker.replace(self.path(info['serial']))
