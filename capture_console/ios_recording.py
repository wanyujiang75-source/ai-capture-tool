"""Worker-side recording generation, independent of the phone connection lifetime."""

from pathlib import Path
import sqlite3

from .ios_projects import domain_matches, normalize_domains
from .ios_results import IOSCaptureArchive


class IOSRecording:
    def __init__(self, config, state):
        self.root = Path(config.get("capture_root", Path(config["state_path"]).parent / "captures")).resolve()
        self.state = state
        self.archive = None
        self.domains = []
        self.pending_passthrough = False
        self.state.update(recording_state="idle", session_id=None, applied_revision=0)

    def apply(self, command, switch):
        if command["revision"] <= self.state["applied_revision"]:
            return
        if command["action"] == "start":
            if self.state["connection_state"] != "ready":
                raise ValueError("请先在 iPhone 完成 HTTPS 连接检查。")
            if self.state["recording_state"] == "recording":
                raise ValueError("请先停止当前抓包，再切换项目。")
            domains = normalize_domains(command["project"]["domains"])
            outdir = Path(command["outdir"]).resolve()
            if not outdir.is_relative_to(self.root) or outdir == self.root:
                raise ValueError("invalid capture directory")
            archive = IOSCaptureArchive(outdir)
            switch(domains)
            self.archive, self.domains = archive, domains
            self.pending_passthrough = False
            self.state.update(recording_state="recording", session_id=command["session_id"],
                              project=command["project"], flow_count=0, phase="capturing", limit_reason=None)
        elif command["action"] == "stop":
            self.stop(switch)
        else:
            raise ValueError("unknown recording command")
        self.state["applied_revision"] = command["revision"]

    def stop(self, switch, state="stopped"):
        # Close the archive before dropping connections: late callbacks must not write.
        if self.archive:
            self.archive.close()
        self.domains = []
        self.state.update(recording_state=state, phase="ready")
        switch([])

    def check_limit(self, switch):
        if self.pending_passthrough:
            switch([])
            self.pending_passthrough = False
        if self.archive and self.archive.limit_reason and self.state["recording_state"] == "recording":
            self.state["limit_reason"] = self.archive.limit_reason
            self.stop(switch, state="limit_reached")

    def invalidate_phone(self):
        if self.state["connection_state"] == "waiting_trust":
            return
        if self.archive:
            self.archive.close()
        self.domains = []
        self.pending_passthrough = True
        self.state.update(recording_state="failed", connection_state="waiting_trust", phase="waiting_trust",
                          message="手机网络地址已改变，请在手机重新打开连接检查，再开始抓包。")

    def requestheaders(self, flow):
        if (self.state["recording_state"] != "recording" or not self.archive
                or not domain_matches(flow.request.host, self.domains)):
            return
        if self.save(self.archive.begin, flow):
            flow.metadata["ios_session_id"] = self.state["session_id"]
            self.state["flow_count"] += 1
            flow.request.stream = self.stream(flow.id, "request")

    def owns(self, flow):
        return (self.archive is not None and not self.archive.closed
                and flow.metadata.get("ios_session_id") == self.state["session_id"])

    def stream(self, flow_id, kind):
        archive = self.archive

        def passthrough(chunk):
            try:
                archive.append_body(flow_id, kind, chunk)
            except (OSError, sqlite3.Error):
                archive._limit("storage_error")
            return chunk

        return passthrough

    def save(self, operation, *args):
        try:
            return operation(*args)
        except (OSError, sqlite3.Error):
            self.archive._limit("storage_error")
            return False

    def request(self, flow):
        if self.owns(flow):
            self.save(self.archive.request_complete, flow)

    def responseheaders(self, flow):
        if self.owns(flow):
            self.save(self.archive.headers, flow)
            flow.response.stream = self.stream(flow.id, "response")

    def finish(self, flow):
        if self.owns(flow):
            self.save(self.archive.finish, flow)
