"""Read-only synthetic desktop detail fixture. No capture, phone or VPN access.

Run directly; the printed loopback URL is the isolated app's backend URL.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


BUILD_ID = "flow-detail-ui-20261105"
DETAILS = {
    "json": {
        "request_text": '{"user":{"id":9007199254740993,"name":"测试用户"},"items":[{"sku":"A-01","quantity":2}]}',
        "response_text": '{"success":true,"data":{"id":9007199254740993,"items":[{"name":"示例商品","price":12.50}]},"message":"已保存"}',
    },
    "form": {
        "request_text": "tag=one&tag=two&name=a+b%2Bc&empty=",
        "request_body": {"content_type": "application/x-www-form-urlencoded", "size_bytes": 40},
        "response_json": {"result": {"saved": True, "message": 'line\n"quoted"'}},
    },
    "partial": {
        "response_text": '{"preview":"' + "synthetic data\n" * 18_000,
        "response_body": {"kind": "json", "size_bytes": 4_000_000, "truncated": True},
    },
    "binary": {
        "response_body": {"kind": "binary", "content_type": "image/png", "size_bytes": 42},
    },
    "pending": {"status": "NO_RESPONSE"},
    "empty": {"status": "204"},
}
for name, detail in DETAILS.items():
    detail.update(id=name, method="POST", url=f"https://example.test/{name}?tag=one&tag=two&limit=20")
    detail.setdefault("status", "200")
    detail["meta_json"] = {"summary": {
        "request_headers": [["Content-Type", detail.get("request_body", {}).get("content_type", "application/json")],
                            ["X-Test", "first"], ["X-Test", "second"]],
        "response_headers": [["Content-Type", detail.get("response_body", {}).get("content_type", "application/json")],
                             ["Set-Cookie", "sample=1"], ["Set-Cookie", "another=2"]],
    }}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        status = 200
        content_type = "application/json; charset=utf-8"
        if path == "/api/status":
            data = {"desktop": {"enabled": True, "build_id": BUILD_ID}, "active_session": None}
        elif path == "/api/captures":
            data = {"sessions": [{"id": 1, "platform": "ios", "status": "running",
                                  "app_name": "隔离数据验收", "mode": "ios-http-proxy"}]}
        elif path == "/api/captures/1/flows":
            rows = [{key: detail.get(key) for key in ("id", "method", "status", "url")} for detail in DETAILS.values()]
            data = {"flows": rows, "total": len(rows), "cursor": 0, "next_cursor": None}
        elif path.startswith("/api/captures/1/flows/"):
            name = path.split("/")[5]
            if path.endswith("/curl"):
                data = f"curl 'https://example.test/{name}'"
                content_type = "text/plain; charset=utf-8"
            else:
                data = DETAILS.get(name, {})
        elif path == "/api/ios-setup":
            data = {"phase": "idle", "connection_state": "idle", "recording_state": "idle"}
        elif path in {"/api/devices", "/api/log-devices/discover"}:
            data = {"devices": [], "blocked_devices": [], "count": 0}
        elif path == "/api/apps":
            data = {"apps": []}
        elif path == "/api/package-sources/jenkins/packages":
            data = {"packages": []}
        else:
            status, data = 404, {"detail": "synthetic fixture: endpoint not implemented"}
        body = (data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "build_id": BUILD_ID}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
