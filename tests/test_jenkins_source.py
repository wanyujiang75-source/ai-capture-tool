import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from capture_console.jenkins_source import JenkinsConfig, JenkinsPackageSource, JenkinsSourceError


def build(number, result="SUCCESS", artifacts=None):
    return {
        "number": number, "result": result, "timestamp": number * 1000,
        "artifacts": artifacts if artifacts is not None else [
            {"fileName": "app.apk", "relativePath": "out/app.apk"}
        ],
    }


class FixtureSource(JenkinsPackageSource):
    def __init__(self, jobs):
        super().__init__(JenkinsConfig(base_url="http://jenkins.test"))
        self.jobs = jobs
        self.calls = []
        self.fail_jobs = set()

    def _get_json(self, path):
        self.calls.append(path)
        if path.startswith("/api/"):
            return {"jobs": copy.deepcopy(self.jobs)}
        name = path.split("/")[2]
        if name in self.fail_jobs:
            raise JenkinsSourceError("offline")
        job = next(job for job in self.jobs if job["name"] == name)
        if path.split("/")[3] == "api":
            return copy.deepcopy(job)
        return copy.deepcopy(next(b for b in job["builds"] if b["number"] == int(path.split("/")[3])))


class JenkinsSourceTests(unittest.TestCase):
    def test_lightweight_index_and_only_needed_successful_artifacts(self):
        source = FixtureSource([{"name": "music", "builds": [
            build(5, None), build(4, "FAILURE"), build(3, artifacts=[]), build(2), build(1)
        ]}])
        result = source.list_latest_packages()
        self.assertEqual([p["build_number"] for p in result], [2])
        self.assertEqual(source.calls, [
            "/api/json?tree=jobs[name,color,builds[number,result,timestamp]{0,10}]",
            "/job/music/3/api/json?tree=artifacts[fileName,relativePath]",
            "/job/music/2/api/json?tree=artifacts[fileName,relativePath]",
        ])

    def test_filter_aliases_do_not_exclude_application_test_packages(self):
        source = FixtureSource([
            {"name": name, "color": "blue", "builds": [build(1)]}
            for name in ["ai-music-apitest", "ai-api_test", "ai-api-test", "testapp", "PokeHub"]
        ])
        self.assertEqual({p["job_name"] for p in source.list_latest_packages()}, {"testapp", "PokeHub"})

    def test_refresh_checks_new_build_but_reuses_completed_artifacts(self):
        source = FixtureSource([{"name": "music", "builds": [build(2, artifacts=[]), build(1)]}])
        first = source.list_latest_packages()
        source.calls.clear()
        self.assertEqual(source.list_latest_packages(), first)
        self.assertEqual(len(source.calls), 1)
        source.jobs[0]["builds"].insert(0, build(3))
        self.assertEqual(source.list_latest_packages()[0]["build_number"], 3)
        self.assertEqual(len(source.calls), 3)

    def test_expired_cache_revalidates_removed_artifacts(self):
        source = FixtureSource([{"name": "music", "builds": [build(1)]}])
        with patch("capture_console.jenkins_source.time.monotonic", return_value=100):
            source.list_latest_packages()
        source.jobs[0]["builds"][0]["artifacts"] = []
        with patch("capture_console.jenkins_source.time.monotonic", return_value=401):
            self.assertEqual(source.list_latest_packages(), [])

    def test_partial_errors_are_snapshot_scoped_and_not_cached(self):
        source = FixtureSource([{"name": name, "builds": [build(1)]} for name in ["good", "bad"]])
        source.fail_jobs.add("bad")
        result = source.list_package_snapshot()
        self.assertEqual(result["failed_jobs"], ["bad"])
        self.assertEqual(result["errors"], ["bad: offline"])
        self.assertEqual([p["job_name"] for p in result["packages"]], ["good"])
        source.fail_jobs.clear()
        self.assertEqual(len(source.list_package_snapshot()["packages"]), 2)
        self.assertEqual(result["failed_jobs"], ["bad"])

    def test_cache_is_bounded(self):
        source = FixtureSource([{"name": f"app{i}", "builds": [build(1)]} for i in range(257)])
        self.assertEqual(len(source.list_latest_packages()), 257)
        self.assertLessEqual(len(source._artifact_cache), 256)

    def test_parallel_queries_are_bounded_and_overlapping_refreshes_share_work(self):
        source = FixtureSource([{"name": f"app{i}", "builds": [build(1)]} for i in range(8)])
        original = source._get_json
        release = threading.Event()
        four_workers = threading.Event()
        follower_waiting = threading.Event()
        lock = threading.Lock()
        active = peak = 0

        def blocked(path):
            nonlocal active, peak
            if path.startswith("/job/"):
                with lock:
                    active += 1
                    peak = max(active, peak)
                    if active == 4:
                        four_workers.set()
                if not release.wait(5):
                    raise JenkinsSourceError("test timed out")
                with lock:
                    active -= 1
            return original(path)

        source._get_json = blocked
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(source.list_latest_packages)
            try:
                self.assertTrue(four_workers.wait(2), "artifact queries must overlap")
                future = source._inflight
                wait = future.result

                def observe_wait():
                    follower_waiting.set()
                    return wait()

                with patch.object(future, "result", side_effect=observe_wait):
                    second = pool.submit(source.list_latest_packages)
                    self.assertTrue(follower_waiting.wait(2))
                    release.set()
                    self.assertEqual(first.result(), second.result())
            finally:
                release.set()
        self.assertEqual(peak, 4)
        self.assertEqual(len(source.calls), 9)

    def test_index_failure_can_be_retried(self):
        source = FixtureSource([])
        with patch.object(source, "_get_json", side_effect=JenkinsSourceError("offline")):
            with self.assertRaises(JenkinsSourceError):
                source.list_latest_packages()
        self.assertEqual(source.list_latest_packages(), [])
