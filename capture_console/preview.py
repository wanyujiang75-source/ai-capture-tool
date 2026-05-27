from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_PREVIEW_PORT = "19097"


def read_env_file_value(path: str | Path, key: str) -> str:
    env_path = Path(path).expanduser()
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    prefix = f"{key}="
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        return line[len(prefix):].strip().strip("\"'")
    return ""


def preview_token(env: Mapping[str, str] | None = None, *, home: Path | None = None) -> str:
    source = env or os.environ
    direct = (source.get("EMULATOR_PREVIEW_TOKEN") or source.get("PREVIEW_TOKEN") or "").strip()
    if direct:
        return direct
    env_file = (source.get("EMULATOR_PREVIEW_ENV_FILE") or "").strip()
    if env_file:
        return read_env_file_value(env_file, "PREVIEW_TOKEN")
    home_dir = home or Path.home()
    return read_env_file_value(home_dir / "emulator-preview" / ".env", "PREVIEW_TOKEN")


def preview_base_url(host: Optional[str], env: Mapping[str, str] | None = None) -> str:
    source = env or os.environ
    configured = (
        source.get("EMULATOR_PREVIEW_PUBLIC_URL")
        or source.get("EMULATOR_PREVIEW_URL")
        or ""
    ).strip()
    if configured:
        return configured.rstrip("/")
    public_host = host or "127.0.0.1"
    return f"http://{public_host}:{DEFAULT_PREVIEW_PORT}"


def preview_url(base_url: str, token: str, *, device_id: str = "", adb_serial: str = "") -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if token:
        query["token"] = token
    if device_id:
        query["device_id"] = device_id
    if adb_serial:
        query["serial"] = adb_serial
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))
