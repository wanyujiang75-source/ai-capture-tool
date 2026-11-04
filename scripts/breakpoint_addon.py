"""Loaded only by explicitly enabled, per-capture launch arguments."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_console.breakpoints.android import AndroidBreakpoints

with open(os.environ['CAPTURE_BP_CONFIG'], encoding='utf-8') as config_file:
    addons = [AndroidBreakpoints(json.load(config_file))]
