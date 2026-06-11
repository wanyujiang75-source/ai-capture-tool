from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping


DEFAULT_LOCAL_CONFIG: dict[str, Any] = {
    "console": {
        "host": "127.0.0.1",
        "port": 7001,
    },
    "android": {
        "sdk_root": "",
    },
    "capture": {
        "proxy_port_start": 9090,
        "web_port_start": 9091,
        "frida_port_start": 27042,
        "mitmweb_token": "android-capture",
    },
}


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _int_env(env: Mapping[str, str], *names: str) -> int | None:
    for name in names:
        value = env.get(name)
        if value is None or value == "":
            continue
        return int(value)
    return None


def load_local_config(
    *,
    root_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(root_dir or Path(__file__).resolve().parents[1])
    source_env = env or os.environ
    config_path = Path(source_env.get("TRACEDECK_CONFIG") or root / "config" / "local.json")
    payload: dict[str, Any] = {}
    if config_path.exists():
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded

    config = _deep_merge(DEFAULT_LOCAL_CONFIG, payload)

    if source_env.get("CONSOLE_HOST"):
        config["console"]["host"] = source_env["CONSOLE_HOST"]
    console_port = _int_env(source_env, "CONSOLE_PORT")
    if console_port is not None:
        config["console"]["port"] = console_port

    if source_env.get("ANDROID_SDK_ROOT"):
        config["android"]["sdk_root"] = source_env["ANDROID_SDK_ROOT"]

    proxy_port = _int_env(source_env, "CAPTURE_PROXY_PORT_START", "PROXY_PORT")
    web_port = _int_env(source_env, "CAPTURE_WEB_PORT_START", "WEB_PORT")
    frida_port = _int_env(source_env, "CAPTURE_FRIDA_PORT_START", "FRIDA_PORT")
    if proxy_port is not None:
        config["capture"]["proxy_port_start"] = proxy_port
    if web_port is not None:
        config["capture"]["web_port_start"] = web_port
    if frida_port is not None:
        config["capture"]["frida_port_start"] = frida_port

    token = source_env.get("CAPTURE_MITMWEB_TOKEN") or source_env.get("MITMWEB_PASSWORD")
    if token:
        config["capture"]["mitmweb_token"] = token

    return config
