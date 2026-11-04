"""Bounded iOS HTTP archive, independent of Android exporter files."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import shlex
import sqlite3
import time
import zlib
from pathlib import Path


PREVIEW_LIMIT = 256 * 1024
SUMMARY_KEYS = ("id", "flow_id", "time", "method", "status", "host", "path", "url", "total_duration_ms")


class IOSCaptureArchive:
    def __init__(self, root, *, read_only=False, body_limit=8 * 1024 * 1024,
                 storage_limit=500 * 1024 * 1024, record_limit=10000):
        self.root = Path(root).resolve()
        self.db = self.root / "ios-flows.sqlite"
        self.closed = read_only
        self.body_limit = body_limit
        self.storage_limit = storage_limit
        self.record_limit = record_limit
        self.limit_reason = None
        self.index_reserve = min(32 * 1024 * 1024, max(16384, storage_limit // 8))
        if not read_only:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.connect() as conn:
                conn.execute(f"PRAGMA max_page_count={self.index_reserve // 4096}")
                conn.execute("CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, revision INTEGER, meta TEXT, summary TEXT)")
                conn.execute("CREATE INDEX IF NOT EXISTS flow_revision ON flows(revision)")
            self.db.chmod(0o600)
        self.body_bytes = 0 if read_only else sum(p.stat().st_size for p in self.root.glob("*.bin"))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db if not self.closed else self.db.as_uri() + "?mode=ro", uri=self.closed)
        conn.row_factory = sqlite3.Row
        if not self.closed:
            conn.execute(f"PRAGMA max_page_count={self.index_reserve // 4096}")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @property
    def stored_bytes(self):
        return self.body_bytes + self.db.stat().st_size

    def close(self):
        self.closed = True

    def _limit(self, reason):
        self.limit_reason = reason
        self.close()

    def _read(self, flow_id):
        with self.connect() as conn:
            row = conn.execute("SELECT meta FROM flows WHERE id=?", (flow_id,)).fetchone()
        if row is None:
            raise KeyError("接口不存在或不属于本次抓包。")
        return json.loads(row[0])

    def _write(self, flow_id, meta):
        if self.closed:
            return
        data = json.dumps(meta, ensure_ascii=False)
        if len(data.encode()) > 128 * 1024:
            self._limit("metadata_limit")
            return
        summary_fields = {key: meta[key] for key in SUMMARY_KEYS}
        for kind in ("request", "response"):
            content_type = next((value for name, value in meta[kind + "_headers"]
                                 if name.lower() == "content-type"), "")
            summary_fields[kind + "_content_type"] = content_type.split(";", 1)[0].strip().lower()[:256]
        summary = json.dumps(summary_fields, ensure_ascii=False)
        try:
            with self.connect() as conn:
                revision = conn.execute("SELECT COALESCE(MAX(revision), 0)+1 FROM flows").fetchone()[0]
                conn.execute("INSERT INTO flows VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision, meta=excluded.meta, summary=excluded.summary",
                             (flow_id, revision, data, summary))
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode != sqlite3.SQLITE_FULL:
                raise
            self._limit("storage_limit")

    def begin(self, flow):
        if self.closed:
            return False
        with self.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM flows").fetchone()[0] >= self.record_limit:
                self._limit("record_limit")
                return False
        request = flow.request
        stamp = request.timestamp_start or time.time()
        meta = {"id": flow.id, "flow_id": flow.id, "time": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                "method": request.method, "status": "NO_RESPONSE", "host": request.host,
                "path": request.path, "url": request.url, "started": stamp, "total_duration_ms": None,
                "request_headers": list(request.headers.items(multi=True)), "response_headers": [],
                "request_size": 0, "response_size": 0, "request_truncated": False, "response_truncated": False,
                "request_complete": False, "response_complete": False}
        self._write(flow.id, meta)
        return not self.closed

    def _body_path(self, flow_id, kind):
        if kind not in {"request", "response"}:
            raise ValueError("unknown body kind")
        return self.root / (hashlib.sha256(flow_id.encode()).hexdigest() + "." + kind + ".bin")

    def append_body(self, flow_id, kind, data):
        if self.closed or not data:
            return
        meta = self._read(flow_id)
        size_key = kind + "_size"
        # Reserve space for both the index and its rollback journal.
        remaining = max(0, self.storage_limit - 2 * self.index_reserve - 4096 - self.body_bytes)
        count = min(len(data), max(0, self.body_limit - meta[size_key]), remaining)
        path = self._body_path(flow_id, kind)
        with path.open("ab") as file:
            file.write(data[:count])
        path.chmod(0o600)
        self.body_bytes += count
        meta[size_key] += count
        meta[kind + "_truncated"] |= count < len(data)
        self._write(flow_id, meta)
        if remaining <= count:
            self._limit("storage_limit")

    def headers(self, flow):
        if self.closed:
            return
        meta = self._read(flow.id)
        meta["status"] = str(flow.response.status_code)
        meta["response_headers"] = list(flow.response.headers.items(multi=True))
        self._write(flow.id, meta)

    def request_complete(self, flow):
        if not self.closed:
            meta = self._read(flow.id)
            meta["request_complete"] = True
            self._write(flow.id, meta)

    def finish(self, flow):
        if self.closed:
            return
        meta = self._read(flow.id)
        response = flow.response
        if response:
            meta["status"] = str(response.status_code)
            meta["response_headers"] = list(response.headers.items(multi=True))
        meta["response_complete"] = response is not None and flow.error is None
        meta["total_duration_ms"] = str(max(0, round(((response.timestamp_end if response else None) or time.time()) * 1000 - meta["started"] * 1000)))
        if flow.error:
            meta["error"] = str(flow.error)[:2048]
        if any(stage.get('action') == 'abort' for stage in meta.get('breakpoints', {}).values()):
            meta['status'] = 'ABORTED'
            meta['response_complete'] = False
        self._write(flow.id, meta)

    def page(self, *, cursor=0, limit=200):
        cursor, limit = max(0, int(cursor)), min(200, max(1, int(limit)))
        with self.connect() as conn:
            rows = conn.execute("SELECT revision, summary FROM flows WHERE revision>? ORDER BY revision LIMIT ?", (cursor, limit + 1)).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM flows").fetchone()[0]
        selected, size = [], 0
        for row in rows[:limit]:
            row_size = len(json.dumps(json.loads(row["summary"])).encode()) + 2
            if selected and size + row_size > 1024 * 1024:
                break
            selected.append(row)
            size += row_size
        position = selected[-1]["revision"] if selected else cursor
        return {"flows": [json.loads(row["summary"]) for row in selected],
                "total": total, "cursor": position, "next_cursor": position if len(rows) > len(selected) else None}

    def detail(self, flow_id):
        meta = self._read(flow_id)
        detail = {key: meta[key] for key in ("id", "method", "status", "url")}
        detail["meta_json"] = {"summary": meta}
        if 'breakpoints' in meta:
            from .breakpoint_preview import preview_versions
            detail['breakpoints'] = preview_versions(self.root, meta['breakpoints'])
        detail["files"] = {}
        for kind in ("request", "response"):
            path = self._body_path(flow_id, kind)
            headers = {name.lower(): value for name, value in meta[kind + "_headers"]}
            content_type = headers.get("content-type", "")
            data = b""
            truncated = meta[kind + "_truncated"] or (meta[kind + "_size"] > 0 and not meta[kind + "_complete"])
            if path.exists():
                encoding = headers.get("content-encoding", "identity").lower()
                if encoding in {"gzip", "deflate"}:
                    decoder = zlib.decompressobj(31 if encoding == "gzip" else 15)
                    try:
                        with path.open("rb") as file:
                            while len(data) <= PREVIEW_LIMIT:
                                chunk = file.read(65536)
                                if not chunk:
                                    break
                                data += decoder.decompress(chunk, PREVIEW_LIMIT + 1 - len(data))
                        truncated |= not decoder.eof
                    except zlib.error:
                        data, truncated = "压缩正文无法预览。".encode(), True
                elif encoding in {"identity", ""}:
                    with path.open("rb") as file:
                        data = file.read(PREVIEW_LIMIT + 1)
                else:
                    data, truncated = "此压缩格式暂不提供正文预览。".encode(), True
            text = data[:PREVIEW_LIMIT].decode("utf-8", "replace").encode()
            truncated |= len(data) > PREVIEW_LIMIT or len(text) > PREVIEW_LIMIT
            body_kind = "json" if "json" in content_type else "text"
            if not meta[kind + "_size"]:
                body_kind = "empty"
            elif (content_type.startswith(("image/", "audio/", "video/"))
                  or content_type.split(";")[0] in {"application/octet-stream", "application/pdf"}):
                body_kind, text = "binary", b""
            detail[kind + "_body_kind"] = body_kind
            detail[kind + "_text"] = text[:PREVIEW_LIMIT].decode("utf-8", "ignore")
            detail[kind + "_body"] = {"kind": body_kind, "content_type": content_type,
                                      "size_bytes": meta[kind + "_size"], "truncated": truncated,
                                      "path": str(path) if path.exists() else None}
            detail["files"][kind] = str(path) if path.exists() else ""
        return detail

    def curl(self, flow_id):
        meta = self._read(flow_id)
        if meta["request_truncated"] or not meta["request_complete"]:
            raise ValueError("请求正文未完整保存，无法生成可重放的 cURL。")
        parts = ["curl", "-X", shlex.quote(meta["method"]), shlex.quote(meta["url"])]
        for name, value in meta["request_headers"]:
            if name.lower() not in {"proxy-authorization", "proxy-connection", "content-length", "host", "connection"}:
                parts.extend(["-H", shlex.quote(name + ": " + value)])
        if meta["request_size"]:
            parts.extend(["--data-binary", shlex.quote("@" + str(self._body_path(flow_id, "request")))])
        return " \\\n  ".join(parts)
