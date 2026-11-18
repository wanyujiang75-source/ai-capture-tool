"""Plan, verify and publish desktop preview releases from GitHub Actions."""

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = "release/desktop-previews"
NOTES_PATTERN = re.compile(rf"{NOTES_DIR}/([0-9]{{8}})-[a-z0-9][a-z0-9-]*\.md")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")

BRIDGE_SOURCE_TREE = "a22f9e3a292e1e0155141f0b27634a7eeee0f98a"
BRIDGE_RELEASE = "desktop-preview-20261118-32895f9"
BRIDGE_ZIP_NAME = "AI-Capture-Desktop-20261118-32895f9-development-arm64.zip"
BRIDGE_ZIP_SHA256 = "a12e7e523c8990c2b169292ee30d0ac8918297f9017d55046e2b23cb57ae17d1"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def release_plan(repo, before, source):
    for sha in (before, source):
        if not SHA_PATTERN.fullmatch(sha):
            raise ValueError("Expected a full commit SHA for the push")
    notes_paths = []
    if before != "0" * 40:
        subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", before, source], check=True)
        added_paths = git(repo, "diff", "--no-renames", "--diff-filter=A", "--name-only", before, source, "--", NOTES_DIR)
        notes_paths = [path for path in added_paths.splitlines() if path.endswith(".md")]
    if len(notes_paths) > 1:
        raise ValueError("Add only one new release notes file per push")

    notes = notes_paths[0] if notes_paths else ""
    if notes:
        match = NOTES_PATTERN.fullmatch(notes)
        if not match:
            raise ValueError(f"Use {NOTES_DIR}/YYYYMMDD-name.md for release notes")
        date = match[1]
        datetime.strptime(date, "%Y%m%d")
        read_notes(repo / notes)
    else:
        timestamp = int(git(repo, "show", "-s", "--format=%ct", source))
        date = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    version = f"{date}-{source[:7]}"
    return {
        "notes": notes,
        "source": source,
        "version": version,
        "tag": f"desktop-preview-{version}",
        "asset": f"AI-Capture-Desktop-{version}-development-arm64.zip",
    }


def read_notes(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Release notes must be a regular file")
    notes = path.read_text(encoding="utf-8")
    if not notes.strip() or len(notes) > 12_000:
        raise ValueError("Release notes must contain 1–12000 characters")
    return notes


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_bridge(destination):
    if git(ROOT, "rev-parse", "HEAD:android-bridge") != BRIDGE_SOURCE_TREE:
        raise ValueError("Android helper sources changed. Update the signed APK baseline before publishing.")
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / BRIDGE_ZIP_NAME
        url = f"https://github.com/wanyujiang75-source/ai-capture-tool/releases/download/{BRIDGE_RELEASE}/{BRIDGE_ZIP_NAME}"
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
                        "--max-time", "300", "--output", str(archive), url], check=True)
        if sha256(archive) != BRIDGE_ZIP_SHA256:
            raise ValueError("Published Android helper baseline ZIP did not match its SHA-256")
        with ZipFile(archive, metadata_encoding="utf-8") as bundle:
            destination.write_bytes(bundle.read("抓包工具.app/Contents/Resources/android-bridge.apk"))


def asset_details(directory, name):
    archive = directory / name
    checksum = directory / f"{name}.sha256"
    digest = sha256(archive)
    if checksum.read_text().split() != [digest, name]:
        raise ValueError("Desktop package checksum does not match")
    return {
        name: (archive.stat().st_size, "sha256:" + digest),
        checksum.name: (checksum.stat().st_size, "sha256:" + sha256(checksum)),
    }


def verify_package(directory, name, source, bridge):
    asset_details(directory, name)
    archive = directory / name
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run(["ditto", "-x", "-k", str(archive), temporary], check=True)
        extracted = Path(temporary)
        for guide in ("INSTALL.md", "USER_GUIDE.md", "BREAKPOINTS.md", "安装说明.md"):
            if not (extracted / guide).is_file():
                raise ValueError(f"Missing package guide: {guide}")
        app = extracted / "抓包工具.app"
        contents = app / "Contents"
        resources = contents / "Resources"
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        architectures = subprocess.check_output(
            ["lipo", "-archs", str(contents / "MacOS/抓包工具")], text=True
        ).strip()
        if architectures != "arm64":
            raise ValueError(f"Expected an arm64 desktop package, got {architectures}")
        if (resources / "backend-build-id.txt").read_text().strip() != source[:12]:
            raise ValueError("App build ID does not match the source commit")
        with (contents / "Info.plist").open("rb") as stream:
            if plistlib.load(stream)["LSMinimumSystemVersion"] != "14.0":
                raise ValueError("Unexpected minimum macOS version")
        if sha256(resources / "android-bridge.apk") != sha256(bridge):
            raise ValueError("Packaged Android helper differs from the signed baseline")
        for runtime in ("runtime", "physical-runtime"):
            subprocess.run([str(resources / runtime / "bin/python3"), "-B", "-c", "import fastapi"], check=True)


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def finish_draft(run, repo, tag, notes, release, expected, directory):
    if not release["prerelease"] or release.get("body", "").strip() != notes.strip():
        raise ValueError("Existing release notes or type differ")
    assets = {asset["name"]: asset for asset in release["assets"]}
    if assets.keys() - expected.keys():
        raise ValueError("Existing release contains unexpected files")
    if not release["draft"]:
        if assets.keys() != expected.keys() or any(
            asset["state"] != "uploaded" or not asset.get("digest") for asset in assets.values()
        ):
            raise ValueError("Published release has incomplete assets")
        print(f"{tag} is already published.")
        return

    missing = set(expected) - assets.keys()
    for name, remote in assets.items():
        if remote["state"] == "starter" and remote["size"] == 0 and not remote.get("digest"):
            run("api", "--method", "DELETE", f"repos/{repo}/releases/assets/{remote['id']}")
            missing.add(name)
        elif remote["state"] != "uploaded" or (remote["size"], remote.get("digest")) != expected[name]:
            raise ValueError(f"Uploaded asset {name} no longer matches the original build")
    for name in sorted(missing):
        run("release", "upload", tag, str(directory / name), "--repo", repo)

    fresh = json.loads(run("api", f"repos/{repo}/releases/{release['id']}"))
    details = {asset["name"]: (asset["size"], asset.get("digest")) for asset in fresh["assets"]}
    if (details != expected or any(asset["state"] != "uploaded" for asset in fresh["assets"])
            or not fresh["draft"] or not fresh["prerelease"] or fresh.get("body", "").strip() != notes.strip()):
        raise ValueError("Draft assets or release notes failed verification")
    run("release", "edit", tag, "--repo", repo, "--draft=false", "--prerelease", "--latest=false")
    published = json.loads(run("api", f"repos/{repo}/releases/{release['id']}"))
    if published["draft"] or not published["prerelease"]:
        raise ValueError("GitHub did not publish the preview release")
    print(published.get("html_url", tag))


def publish(repo, notes_path, source, tag, asset, directory):
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Desktop previews can only be published from main")
    if repo != "wanyujiang75-source/ai-capture-tool" or source != git(ROOT, "rev-parse", "HEAD"):
        raise ValueError("Unexpected release repository or checkout")
    match = NOTES_PATTERN.fullmatch(notes_path)
    if not match:
        raise ValueError("Invalid release note path")
    version = f"{match[1]}-{source[:7]}"
    if tag != f"desktop-preview-{version}" or asset != f"AI-Capture-Desktop-{version}-development-arm64.zip":
        raise ValueError("Release tag or asset does not match the source commit")

    expected = asset_details(directory, asset)
    notes = read_notes(ROOT / notes_path)
    remote = git(ROOT, "ls-remote", "--tags", "origin", f"refs/tags/{tag}")
    if not remote:
        gh("api", "--method", "POST", f"repos/{repo}/git/refs", "-f", f"ref=refs/tags/{tag}", "-f", f"sha={source}")
        remote = git(ROOT, "ls-remote", "--tags", "origin", f"refs/tags/{tag}")
    if remote.split() != [source, f"refs/tags/{tag}"]:
        raise ValueError("Remote tag does not point at the build commit")

    def find_release():
        pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
        return next((release for page in pages for release in page if release["tag_name"] == tag), None)

    existing = find_release()
    if existing is None:
        gh("release", "create", tag, "--repo", repo, "--verify-tag", "--draft", "--prerelease",
           "--latest=false", "--title", f"抓包工具桌面预览版 · {match[1]}", "--notes-file", str(ROOT / notes_path))
        existing = find_release()
    if existing is None:
        raise ValueError("GitHub did not return the release draft")
    finish_draft(gh, repo, tag, notes, existing, expected, directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    plan = subcommands.add_parser("plan")
    plan.add_argument("before")
    plan.add_argument("source")
    bridge = subcommands.add_parser("bridge")
    bridge.add_argument("destination", type=Path)
    verify = subcommands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("asset")
    verify.add_argument("source")
    verify.add_argument("bridge", type=Path)
    release = subcommands.add_parser("publish")
    release.add_argument("repository")
    release.add_argument("notes")
    release.add_argument("source")
    release.add_argument("tag")
    release.add_argument("asset")
    release.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print("\n".join(f"{key}={value}" for key, value in release_plan(ROOT, args.before, args.source).items()))
        elif args.command == "bridge":
            prepare_bridge(args.destination)
        elif args.command == "verify":
            verify_package(args.directory, args.asset, args.source, args.bridge)
        else:
            publish(args.repository, args.notes, args.source, args.tag, args.asset, args.directory)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
