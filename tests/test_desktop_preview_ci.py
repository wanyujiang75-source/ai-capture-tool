import json
import runpy
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class DesktopPreviewCITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = runpy.run_path(str(ROOT / "release/desktop-preview-ci.py"))

    def test_trigger_uses_one_new_notes_file_and_final_pushed_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.git(repo, "init", "-q")
            self.commit(repo, "baseline")
            before = self.git(repo, "rev-parse", "HEAD")
            notes = repo / "release/desktop-previews/1.0.0-toolbar.md"
            notes.parent.mkdir(parents=True)
            notes.write_text("更新按钮\n", encoding="utf-8")
            self.commit(repo, "release intent")
            (repo / "source.txt").write_text("source update")
            self.commit(repo, "final code")
            sha = self.git(repo, "rev-parse", "HEAD")
            epoch = int(self.git(repo, "show", "-s", "--format=%ct", sha))
            date = datetime.fromtimestamp(epoch, ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
            plan = self.cli["release_plan"](repo, before, sha)
            self.assertEqual(
                {"notes": "release/desktop-previews/1.0.0-toolbar.md", "source": sha,
                 "app_version": "1.0.0", "version": f"{date}-{sha[:7]}", "tag": f"desktop-preview-{date}-{sha[:7]}",
                 "asset": f"AI-Capture-Desktop-{date}-{sha[:7]}-development-arm64.zip"},
                plan,
            )
            notes.write_text("改一个字\n", encoding="utf-8")
            self.commit(repo, "edit existing notes")
            new_sha = self.git(repo, "rev-parse", "HEAD")
            self.assertEqual("", self.cli["release_plan"](repo, sha, new_sha)["notes"])
            self.assertEqual("", self.cli["release_plan"](repo, "0" * 40, new_sha)["notes"])

    def test_rejects_two_new_releases_in_one_push(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.git(repo, "init", "-q")
            self.commit(repo, "baseline")
            before = self.git(repo, "rev-parse", "HEAD")
            directory = repo / "release/desktop-previews"
            directory.mkdir(parents=True)
            for name in ("1.0.0-first.md", "1.0.1-second.md"):
                (directory / name).write_text("说明\n", encoding="utf-8")
            self.commit(repo, "two releases")
            with self.assertRaisesRegex(ValueError, "one new release"):
                self.cli["release_plan"](repo, before, self.git(repo, "rev-parse", "HEAD"))

    def test_release_versions_must_advance_and_existing_tag_can_resume(self):
        existing = [
            {"tag_name": "desktop-preview-20261118-32895f9", "name": "旧预览包", "draft": False, "prerelease": True},
            {"tag_name": "tag-first", "name": "抓包工具桌面预览版 v1.0.0", "draft": False, "prerelease": True},
            {"tag_name": "tag-draft", "name": "抓包工具桌面预览版 v1.9.0", "draft": True, "prerelease": True},
        ]
        check = self.cli["check_preview_version"]
        check(existing, "tag-patch", "1.0.1")
        check(existing, "tag-minor", "1.2.0")
        check(existing, "tag-first", "1.0.0")
        with self.assertRaisesRegex(ValueError, "higher than"):
            check(existing, "tag-other", "1.0.0")
        with self.assertRaisesRegex(ValueError, "higher than"):
            check(existing, "tag-older", "0.9.9")

    def test_uses_the_created_draft_without_a_second_list_query(self):
        draft = {"id": 42, "name": "抓包工具桌面预览版 v1.0.0", "draft": True, "prerelease": True}
        args = []

        def run(*call):
            args.append(call)
            return json.dumps(draft)

        result = self.cli["create_preview_draft"](
            run, "example/app", "desktop-preview-20261118-abcdef1", "抓包工具桌面预览版 v1.0.0", Path("notes.md")
        )
        self.assertEqual(draft, result)
        self.assertEqual(1, len(args))
        self.assertEqual(("api", "--method", "POST", "repos/example/app/releases"), args[0][:4])
        self.assertIn("body=@notes.md", args[0])
        self.assertIn("draft=true", args[0])
        self.assertIn("prerelease=true", args[0])

    def test_draft_resumes_without_overwriting_uploaded_assets(self):
        actions = []
        state = {"draft": True, "prerelease": True, "body": "更新说明\n", "id": 42,
                 "assets": [{"name": "preview.zip", "state": "uploaded", "size": 4, "digest": "sha256:zip"}]}
        expected = {"preview.zip": (4, "sha256:zip"), "preview.zip.sha256": (5, "sha256:checksum")}

        def run(*args):
            actions.append(args)
            if args[:2] == ("api", "repos/example/app/releases/42"):
                return json.dumps(state)
            if args[:2] == ("release", "upload"):
                state["assets"].append(
                    {"name": "preview.zip.sha256", "state": "uploaded", "size": 5, "digest": "sha256:checksum"}
                )
            if args[:2] == ("release", "edit"):
                state["draft"] = False
            return ""

        self.cli["finish_draft"](run, "example/app", "tag", "更新说明\n", state, expected, Path("assets"))
        self.assertEqual(
            [("release", "upload", "tag", "assets/preview.zip.sha256", "--repo", "example/app")],
            [args for args in actions if args[:2] == ("release", "upload")],
        )
        self.assertFalse(state["draft"])

    def test_empty_upload_stub_can_be_retried(self):
        actions = []
        note = "更新说明"
        expected = {"preview.zip": (4, "sha256:zip")}
        state = {"draft": True, "prerelease": True, "body": note, "id": 42, "assets": [
            {"id": 7, "name": "preview.zip", "state": "starter", "size": 0, "digest": None},
        ]}

        def run(*args):
            actions.append(args)
            if args[:2] == ("api", "repos/example/app/releases/42"):
                return json.dumps(state)
            if args == ("api", "--method", "DELETE", "repos/example/app/releases/assets/7"):
                state["assets"].clear()
            if args[:2] == ("release", "upload"):
                state["assets"].append(
                    {"name": "preview.zip", "state": "uploaded", "size": 4, "digest": "sha256:zip"}
                )
            if args[:2] == ("release", "edit"):
                state["draft"] = False
            return ""

        self.cli["finish_draft"](run, "example/app", "tag", note, state, expected, Path("assets"))
        self.assertEqual(("api", "--method", "DELETE", "repos/example/app/releases/assets/7"), actions[0])
        self.assertFalse(state["draft"])

    def test_published_release_for_same_tag_is_idempotent(self):
        state = {"draft": False, "prerelease": True, "body": "更新说明", "assets": [
            {"name": "preview.zip", "state": "uploaded", "size": 4, "digest": "sha256:old-zip"},
            {"name": "preview.zip.sha256", "state": "uploaded", "size": 5, "digest": "sha256:old-checksum"},
        ]}
        expected = {"preview.zip": (6, "sha256:new-zip"), "preview.zip.sha256": (5, "sha256:new-checksum")}
        with patch("builtins.print"):
            self.cli["finish_draft"](
                lambda *args: self.fail(f"Already public: unexpected action {args}"),
                "example/app", "tag", "更新说明\n", state, expected, Path("assets"),
            )

    def test_draft_with_different_notes_or_damaged_asset_is_not_published(self):
        state = {"draft": True, "prerelease": True, "body": "其他说明", "id": 42, "assets": []}
        expected = {"preview.zip": (4, "sha256:zip")}
        def fail(*args):
            self.fail(f"Unexpected GitHub action: {args}")

        with self.assertRaisesRegex(ValueError, "notes"):
            self.cli["finish_draft"](fail, "example/app", "tag", "更新说明", state, expected, Path("assets"))
        state["body"] = "更新说明"
        state["assets"] = [{"name": "preview.zip", "state": "uploaded", "size": 7, "digest": "sha256:wrong"}]
        with self.assertRaisesRegex(ValueError, "matches"):
            self.cli["finish_draft"](fail, "example/app", "tag", "更新说明", state, expected, Path("assets"))

    @staticmethod
    def git(repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    def commit(self, repo, message):
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.email=fixture@example.com", "-c", "user.name=Fixture",
                 "commit", "-q", "--allow-empty", "-m", message)
