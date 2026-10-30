"""Local iPhone project configuration; domain scopes are never implicit."""

import copy
import ipaddress
import json
import re
import threading
import uuid
from pathlib import Path


def normalize_domains(values):
    if not values or len(values) > 64:
        raise ValueError("请填写 1 至 64 个目标域名。")
    result = []
    for value in values:
        if any(ord(c) < 32 for c in value):
            raise ValueError("目标域名不能包含控制字符。")
        value = value.strip().lower()
        wildcard = value.startswith("*.")
        host = value[2:] if wildcard else value
        try:
            host = host.encode("idna").decode("ascii").rstrip(".")
        except UnicodeError as exc:
            raise ValueError("目标域名格式无效。") from exc
        labels = host.split(".")
        if (not host or len(host) > 253 or host == "capture-check.invalid"
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)):
            raise ValueError("请填写域名，不包含协议、路径、端口或全局通配符。")
        if wildcard:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("IP 地址不能使用子域名通配符。")
            if len(labels) < 2:
                raise ValueError("请明确需要抓取的子域名范围。")
        normalized = ("*." if wildcard else "") + host
        if normalized not in result:
            result.append(normalized)
    return result


def domain_matches(host, domains):
    host = host.lower().rstrip(".")
    return any(host.endswith(rule[1:]) if rule.startswith("*.") else host == rule for rule in domains)


class IOSProjects:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def list(self):
        with self.lock:
            if self.path.exists():
                if self.path.stat().st_size > 512 * 1024:
                    raise ValueError("项目配置过大，请检查本地配置。")
                return json.loads(self.path.read_text())
            return [{"id": "pokehub", "name": "PokeHub", "domains": ["yqctnvcripabohfhzgya.supabase.co"]}]

    def get(self, project_id):
        for project in self.list():
            if project["id"] == project_id:
                return copy.deepcopy(project)
        raise ValueError("项目不存在，请重新选择抓包项目。")

    def save(self, *, name, domains, project_id=None):
        name = name.strip()
        if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise ValueError("请填写 1 至 80 个字符的项目名称。")
        domains = normalize_domains(domains)
        with self.lock:
            projects = self.list()
            if project_id and not any(p["id"] == project_id for p in projects):
                raise ValueError("项目不存在，请重新选择。")
            if not project_id and len(projects) >= 100:
                raise ValueError("最多保存 100 个项目，请修改已有项目。")
            project = {"id": project_id or uuid.uuid4().hex, "name": name, "domains": domains}
            projects = [p for p in projects if p["id"] != project["id"]] + [project]
            data = json.dumps(projects, ensure_ascii=False)
            if len(data.encode()) > 512 * 1024:
                raise ValueError("项目配置已达到存储上限，请减少项目或域名数量。")
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(data)
            temporary.chmod(0o600)
            temporary.replace(self.path)
            return copy.deepcopy(project)
