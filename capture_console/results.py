from __future__ import annotations

import csv
from datetime import datetime
import json
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


MAX_TEXT_BYTES = 2 * 1024 * 1024


def _safe_join(outdir: Path, name: str) -> Path:
    path = (outdir / name).resolve()
    root = outdir.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"path escapes capture directory: {name}")
    return path


def _json_sidecar(bin_name: str) -> str:
    if bin_name.endswith(".request.bin"):
        return bin_name[: -len(".request.bin")] + ".request.json"
    if bin_name.endswith(".response.bin"):
        return bin_name[: -len(".response.bin")] + ".response.json"
    return bin_name + ".json"


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_TEXT_BYTES:
        data = data[:MAX_TEXT_BYTES]
        suffix = f"\n\n... truncated at {MAX_TEXT_BYTES} bytes ..."
    else:
        suffix = ""
    return data.decode("utf-8", errors="replace") + suffix


def _load_meta(outdir: Path, meta_name: str) -> Dict[str, Any]:
    if not meta_name:
        return {}
    path = _safe_join(outdir, meta_name)
    if not path.exists():
        return {}
    return _read_json(path)


def _epoch_iso(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return datetime.fromtimestamp(float(value)).astimezone().isoformat(timespec="milliseconds")
    except (TypeError, ValueError, OSError):
        return ""


def _duration_ms(start: Any, end: Any) -> Optional[int]:
    if start is None or end is None or start == "" or end == "":
        return None
    try:
        start_value = float(start)
        end_value = float(end)
    except (TypeError, ValueError):
        return None
    if end_value < start_value:
        return None
    return int(round((end_value - start_value) * 1000))


def _summary_timing(summary: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    fields = {
        "request_started_at": summary.get("request_started_at") or "",
        "request_finished_at": summary.get("request_finished_at") or "",
        "response_started_at": summary.get("response_started_at") or "",
        "response_finished_at": summary.get("response_finished_at") or "",
        "request_duration_ms": summary.get("request_duration_ms"),
        "wait_duration_ms": summary.get("wait_duration_ms"),
        "response_duration_ms": summary.get("response_duration_ms"),
        "total_duration_ms": summary.get("total_duration_ms"),
    }
    if any(value not in ("", None) for value in fields.values()):
        return fields

    flow = meta.get("mitm_flow") or {}
    request = flow.get("request") or {}
    response = flow.get("response") if isinstance(flow.get("response"), dict) else {}
    request_start = request.get("timestamp_start")
    request_end = request.get("timestamp_end")
    response_start = response.get("timestamp_start")
    response_end = response.get("timestamp_end")
    return {
        "request_started_at": _epoch_iso(request_start),
        "request_finished_at": _epoch_iso(request_end),
        "response_started_at": _epoch_iso(response_start),
        "response_finished_at": _epoch_iso(response_end),
        "request_duration_ms": _duration_ms(request_start, request_end),
        "wait_duration_ms": _duration_ms(request_end, response_start),
        "response_duration_ms": _duration_ms(response_start, response_end),
        "total_duration_ms": _duration_ms(request_start, response_end),
    }


def _flow_from_row(outdir: Path, row: Dict[str, str]) -> Dict[str, Any]:
    meta = _load_meta(outdir, row.get("meta", ""))
    summary = meta.get("summary", {})
    url = row.get("url") or summary.get("url") or ""
    parsed = urlparse(url)
    meta_name = row.get("meta", "")
    flow_id = Path(meta_name).stem if meta_name else summary.get("id") or url
    request_json = _safe_join(outdir, _json_sidecar(row.get("request_bin", "")))
    response_json = _safe_join(outdir, _json_sidecar(row.get("response_bin", "")))
    return {
        "id": flow_id,
        "flow_id": summary.get("id", ""),
        "kind": row.get("kind") or ("noise" if row.get("noise_reason") else "candidate"),
        "noise_reason": row.get("noise_reason", ""),
        "time": row.get("time", ""),
        "score": int(row.get("score") or 0),
        "method": row.get("method") or summary.get("method") or "",
        "status": row.get("status") or str(summary.get("status") or ""),
        "host": row.get("host") or summary.get("host") or parsed.netloc,
        "path": parsed.path,
        "pattern": row.get("pattern", ""),
        "url": url,
        "meta": meta_name,
        "request_bin": row.get("request_bin", ""),
        "response_bin": row.get("response_bin", ""),
        "has_request_json": request_json.exists(),
        "has_response_json": response_json.exists(),
        **_summary_timing(summary, meta),
    }


def _scan_tsv(outdir: Path, tsv_path: Path) -> List[Dict[str, Any]]:
    if not tsv_path.exists():
        return []
    with tsv_path.open(encoding="utf-8", errors="replace", newline="") as fp:
        reader = csv.DictReader(fp, delimiter="\t")
        return [_flow_from_row(outdir, row) for row in reader if row.get("url")]


def scan_capture(outdir: str | Path) -> List[Dict[str, Any]]:
    outdir = Path(outdir)
    all_flows = outdir / "all-flows.tsv"
    if all_flows.exists():
        header = all_flows.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if header and {"meta", "request_bin", "response_bin"}.issubset(set(header[0].split("\t"))):
            flows = _scan_tsv(outdir, all_flows)
            if flows:
                return flows

    candidates = outdir / "candidates.tsv"
    return _scan_tsv(outdir, candidates)


def get_flow_detail(outdir: str | Path, flow_id: str) -> Dict[str, Any]:
    outdir = Path(outdir)
    flows = scan_capture(outdir)
    flow = next((item for item in flows if item["id"] == flow_id or item.get("flow_id") == flow_id), None)
    if flow is None:
        raise KeyError(f"flow not found: {flow_id}")

    meta = _load_meta(outdir, flow["meta"])
    detail = dict(flow)
    detail["meta_json"] = meta
    detail["request_json"] = None
    detail["response_json"] = None
    detail["request_text"] = ""
    detail["response_text"] = ""

    request_json = _safe_join(outdir, _json_sidecar(flow["request_bin"]))
    response_json = _safe_join(outdir, _json_sidecar(flow["response_bin"]))
    request_bin = _safe_join(outdir, flow["request_bin"]) if flow["request_bin"] else None
    response_bin = _safe_join(outdir, flow["response_bin"]) if flow["response_bin"] else None

    if request_json.exists():
        detail["request_json"] = _read_json(request_json)
    elif request_bin and request_bin.exists():
        detail["request_text"] = _read_text(request_bin)

    if response_json.exists():
        detail["response_json"] = _read_json(response_json)
    elif response_bin and response_bin.exists():
        detail["response_text"] = _read_text(response_bin)

    detail["files"] = {
        "meta": str(_safe_join(outdir, flow["meta"])) if flow["meta"] else "",
        "request": str(request_bin) if request_bin else "",
        "response": str(response_bin) if response_bin else "",
        "request_json": str(request_json) if request_json.exists() else "",
        "response_json": str(response_json) if response_json.exists() else "",
    }
    return detail


def _headers_from_detail(detail: Dict[str, Any]) -> List[List[str]]:
    summary = detail.get("meta_json", {}).get("summary", {})
    headers = summary.get("request_headers") or []
    return [[str(name), str(value)] for name, value in headers if name and value is not None]


def build_curl(detail: Dict[str, Any]) -> str:
    method = detail.get("method") or "GET"
    url = detail.get("url") or ""
    parts = ["curl", "-X", method, shlex.quote(url)]
    for name, value in _headers_from_detail(detail):
        parts.extend(["-H", shlex.quote(f"{name}: {value}")])
    body = ""
    if detail.get("request_json") is not None:
        body = json.dumps(detail["request_json"], ensure_ascii=False, separators=(",", ":"))
    elif detail.get("request_text"):
        body = detail["request_text"]
    if body and method.upper() not in {"GET", "HEAD"}:
        parts.extend(["--data-raw", shlex.quote(body)])
    return " \\\n  ".join(parts)
