from __future__ import annotations

import base64
import copy
import json
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


INSTALLABLE_SUFFIXES = (".apk", ".apks", ".zip")


class JenkinsSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class JenkinsConfig:
    base_url: str
    username: str = ""
    password: str = ""
    job_exclude_keywords: tuple[str, ...] = ("api-test",)
    artifact_limit: int = 10

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "JenkinsConfig":
        keywords = value.get("job_exclude_keywords") or ("api-test",)
        if isinstance(keywords, str):
            keywords = tuple(item.strip() for item in keywords.split(",") if item.strip())
        else:
            keywords = tuple(str(item).strip() for item in keywords if str(item).strip())
        return cls(
            base_url=str(value.get("base_url") or "http://192.168.77.150:8080").rstrip("/"),
            username=str(value.get("username") or ""),
            password=str(value.get("password") or ""),
            job_exclude_keywords=keywords or ("api-test",),
            artifact_limit=max(1, int(value.get("artifact_limit") or 10)),
        )


class JenkinsPackageSource:
    def __init__(self, config: JenkinsConfig):
        self.config = config
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.last_errors: list[str] = []
        self._lock = threading.Lock()
        self._inflight: Future | None = None
        self._artifact_cache: OrderedDict = OrderedDict()

    def list_latest_packages(self) -> list[dict[str, Any]]:
        result = self.list_package_snapshot()
        self.last_errors = result["errors"]
        return result["packages"]

    def list_package_snapshot(self) -> dict[str, Any]:
        # Share in-flight work, not stale list results: every later refresh checks builds.
        with self._lock:
            future = self._inflight
            leader = future is None
            if leader:
                future = self._inflight = Future()
        if leader:
            try:
                future.set_result(self._load_package_snapshot())
            except Exception as exc:
                future.set_exception(exc)
            finally:
                with self._lock:
                    self._inflight = None
        return copy.deepcopy(future.result())

    def _load_package_snapshot(self) -> dict[str, Any]:
        data = self._get_json(
            "/api/json?tree=jobs[name,color,builds[number,result,timestamp]"
            f"{{0,{self.config.artifact_limit}}}]"
        )
        packages: list[dict[str, Any]] = []
        errors, failed_jobs = [], []
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="jenkins-list") as pool:
            queries = [
                (str(job["name"]), pool.submit(self._latest_package_for_job, str(job["name"]), job.get("builds", [])))
                for job in data.get("jobs", [])
                if job.get("name") and not self._skip_job(str(job["name"]), str(job.get("color") or ""))
            ]
            for name, query in queries:
                try:
                    package = query.result()
                except JenkinsSourceError as exc:
                    errors.append(f"{name}: {exc}")
                    failed_jobs.append(name)
                    continue
                if package:
                    packages.append(package)
        return {
            "packages": sorted(packages, key=lambda item: int(item.get("timestamp") or 0), reverse=True),
            "errors": errors,
            "failed_jobs": failed_jobs,
        }

    def download_package(
        self,
        *,
        job_name: str,
        build_number: int,
        artifact_relative_path: str,
        destination_dir: Path,
    ) -> tuple[str, Path]:
        artifact = self._artifact_for_build(
            job_name=job_name,
            build_number=build_number,
            artifact_relative_path=artifact_relative_path,
        )
        filename = Path(artifact["file_name"]).name
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / filename
        url = self._artifact_url(job_name, build_number, artifact["relative_path"])
        request = self._request(url)
        try:
            with self._opener.open(request, timeout=90) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
        except Exception as exc:
            raise JenkinsSourceError(f"failed to download Jenkins artifact {job_name} #{build_number}: {exc}") from exc
        if not destination.exists() or destination.stat().st_size == 0:
            raise JenkinsSourceError(f"downloaded Jenkins artifact is empty: {filename}")
        return filename, destination

    def _latest_package_for_job(self, job_name: str, builds: list[dict[str, Any]]) -> dict[str, Any] | None:
        for build in builds[:self.config.artifact_limit]:
            if build.get("result") != "SUCCESS":
                continue
            build_number = int(build.get("number") or 0)
            timestamp = int(build.get("timestamp") or 0)
            artifacts = self._cached_build_artifacts(job_name, build_number, timestamp)
            if not artifacts:
                continue
            artifact = artifacts[0]
            return {
                "id": f"{job_name}-{build_number}-{artifact['relative_path']}",
                "job_name": job_name,
                "build_number": build_number,
                "result": build.get("result") or "",
                "timestamp": timestamp,
                "build_time": self._format_timestamp(timestamp),
                "artifact_file_name": artifact["file_name"],
                "artifact_relative_path": artifact["relative_path"],
                "artifact_url": self._artifact_url(job_name, build_number, artifact["relative_path"]),
                "environment": self._infer_environment(job_name),
            }
        return None

    def _cached_build_artifacts(self, job_name: str, number: int, timestamp: int) -> list[dict[str, str]]:
        key = (job_name, number, timestamp)
        with self._lock:
            cached = self._artifact_cache.get(key)
            if cached is not None and cached[0] > time.monotonic():
                self._artifact_cache.move_to_end(key)
                return cached[1]
        data = self._get_json(
            f"/job/{self._quote_segment(job_name)}/{number}/api/json?"
            "tree=artifacts[fileName,relativePath]"
        )
        artifacts = self._installable_artifacts(data.get("artifacts") or [])
        with self._lock:
            self._artifact_cache[key] = (time.monotonic() + 300, artifacts)
            self._artifact_cache.move_to_end(key)
            while len(self._artifact_cache) > 256:
                self._artifact_cache.popitem(last=False)
        return artifacts

    def _artifact_for_build(
        self,
        *,
        job_name: str,
        build_number: int,
        artifact_relative_path: str,
    ) -> dict[str, str]:
        path = (
            f"/job/{self._quote_segment(job_name)}/{build_number}/api/json?"
            "tree=number,result,artifacts[fileName,relativePath]"
        )
        data = self._get_json(path)
        artifacts = self._installable_artifacts(data.get("artifacts") or [])
        for artifact in artifacts:
            if artifact["relative_path"] == artifact_relative_path:
                return artifact
        raise JenkinsSourceError(
            f"Jenkins artifact not found: {job_name} #{build_number} {artifact_relative_path}"
        )

    def _get_json(self, path_or_url: str) -> dict[str, Any]:
        request = self._request(self._absolute_url(path_or_url))
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=15) as response:
                payload = response.read()
        except Exception as exc:
            raise JenkinsSourceError(f"failed to read Jenkins API: {exc}") from exc
        try:
            loaded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise JenkinsSourceError(f"failed to parse Jenkins API response: {exc}") from exc
        if not isinstance(loaded, dict):
            raise JenkinsSourceError("Jenkins API response is not an object")
        return loaded

    def _request(self, url: str) -> urllib.request.Request:
        headers = {"User-Agent": "ai-capture-tool/jenkins-source"}
        if self.config.username and self.config.password:
            token = f"{self.config.username}:{self.config.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(token).decode("ascii")
        return urllib.request.Request(url, headers=headers)

    def _absolute_url(self, path_or_url: str) -> str:
        parsed = urllib.parse.urlparse(path_or_url)
        if parsed.scheme and parsed.netloc:
            parsed_base = urllib.parse.urlparse(self.config.base_url)
            return urllib.parse.urlunparse(parsed._replace(scheme=parsed_base.scheme, netloc=parsed_base.netloc))
        return f"{self.config.base_url}/{path_or_url.lstrip('/')}"

    def _artifact_url(self, job_name: str, build_number: int, relative_path: str) -> str:
        return (
            f"{self.config.base_url}/job/{self._quote_segment(job_name)}/{build_number}/artifact/"
            f"{urllib.parse.quote(relative_path, safe='/')}"
        )

    def _skip_job(self, name: str, color: str) -> bool:
        if color == "disabled":
            return True
        lower_name = name.lower()
        if "api-test" in self.config.job_exclude_keywords and re.search(r"(?:^|[-_])api[-_]?test(?:$|[-_])", lower_name):
            return True
        return any(keyword.lower() in lower_name for keyword in self.config.job_exclude_keywords)

    def _installable_artifacts(self, artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
        installable: list[dict[str, str]] = []
        for artifact in artifacts:
            file_name = str(artifact.get("fileName") or "")
            relative_path = str(artifact.get("relativePath") or "")
            candidate = (file_name or relative_path).lower()
            if not candidate.endswith(INSTALLABLE_SUFFIXES):
                continue
            installable.append(
                {
                    "file_name": Path(file_name or relative_path).name,
                    "relative_path": relative_path,
                }
            )
        return installable

    def _infer_environment(self, job_name: str) -> str:
        lower_name = job_name.lower()
        if any(token in lower_name for token in ("prod", "release", "store")):
            return "production"
        return "test"

    def _format_timestamp(self, timestamp_ms: int) -> str:
        if timestamp_ms <= 0:
            return ""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp_ms / 1000))

    def _quote_segment(self, value: str) -> str:
        return urllib.parse.quote(value, safe="")
