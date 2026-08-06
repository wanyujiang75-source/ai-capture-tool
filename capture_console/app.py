from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .device_discovery import build_discovered_devices
from .jenkins_source import JenkinsConfig, JenkinsPackageSource, JenkinsSourceError
from .local_config import load_local_config
from .network import build_device_network_state, build_host_network_check, proxy_from_env
from .platforms import capture_supported, unsupported_platform_detail
from .preflight import build_port_preflight, collect_port_listeners
from .preview import preview_base_url, preview_token, preview_url
from .readiness import build_readiness_report
from .results import build_curl, get_flow_detail, scan_capture
from .runner import CommandResult, ConsoleRunner
from .store import CAPTURE_MODES, CaptureStore, DEFAULT_DEVICE_ID, validate_app_environment


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = load_local_config(root_dir=ROOT_DIR)
if LOCAL_CONFIG.get("android", {}).get("sdk_root"):
    os.environ.setdefault("ANDROID_SDK_ROOT", str(LOCAL_CONFIG["android"]["sdk_root"]))
RUNTIME_DIR = Path(os.environ.get("CAPTURE_RUNTIME_DIR") or ROOT_DIR / "runtime").expanduser().resolve()
CAPTURES_DIR = RUNTIME_DIR / "captures"
UPLOADS_DIR = RUNTIME_DIR / "uploads"
LATEST_APKS_DIR = RUNTIME_DIR / "apks" / "latest"
WEB_URL = f"http://127.0.0.1:{LOCAL_CONFIG['capture']['web_port_start']}/?token={LOCAL_CONFIG['capture']['mitmweb_token']}"
IDLE_SLEEP_SECONDS = int(os.environ.get("CAPTURE_IDLE_SLEEP_SECONDS", "1800"))
SETUP_COMPLETED_KEY = "setup_completed"
SETUP_CHECKED_KEY = "setup_checked"
GOOGLE_LOGIN_REQUIRED = os.environ.get("REQUIRE_GOOGLE_LOGIN", "0").lower() in {"1", "true", "yes", "on"}

store = CaptureStore(RUNTIME_DIR / "console.db", devices_config_path=os.environ.get("CAPTURE_DEVICES_CONFIG"))
runner = ConsoleRunner(
    ROOT_DIR,
    proxy_port=int(LOCAL_CONFIG["capture"]["proxy_port_start"]),
    web_port=int(LOCAL_CONFIG["capture"]["web_port_start"]),
    frida_port=int(LOCAL_CONFIG["capture"]["frida_port_start"]),
    mitm_password=str(LOCAL_CONFIG["capture"]["mitmweb_token"]),
)
jenkins_source = JenkinsPackageSource(JenkinsConfig.from_mapping(LOCAL_CONFIG.get("jenkins", {})))
app = FastAPI(title="TraceDeck API", version="1.0.0")


class AppPayload(BaseModel):
    platform: str = "android"
    environment: str = "production"
    name: str
    package_name: str
    activity: str = ""
    default_mode: str = "auto"
    notes: str = ""


class CaptureStartPayload(BaseModel):
    app_id: int
    device_id: str = DEFAULT_DEVICE_ID
    mode: Optional[str] = None


class JenkinsInstallPayload(BaseModel):
    device_id: str = DEFAULT_DEVICE_ID
    job_name: str
    build_number: int
    artifact_relative_path: str
    environment: str = "test"


def normalize_requested_capture_mode(target_app: Dict[str, Any], mode: Optional[str]) -> str:
    requested = (mode or target_app.get("default_mode") or "auto").strip()
    allowed = CAPTURE_MODES | {"auto"}
    if requested not in allowed:
        raise HTTPException(status_code=400, detail=f"mode must be auto, system, or flutter-socks: {requested}")
    return requested


def capture_mode_candidates(target_app: Dict[str, Any], requested_mode: str) -> list[str]:
    if requested_mode in CAPTURE_MODES:
        return [requested_mode]

    candidates: list[str] = []
    for mode in (
        target_app.get("last_success_mode", ""),
        target_app.get("default_mode", ""),
        "system",
        "flutter-socks",
    ):
        if mode in CAPTURE_MODES and mode not in candidates:
            candidates.append(mode)
    return candidates


def clear_project_capture_records() -> None:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    store.clear_capture_sessions()


def device_or_404(device_id: str) -> Dict[str, Any]:
    device = store.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="capture device not found")
    if not device.get("enabled"):
        raise HTTPException(status_code=409, detail="capture device is disabled")
    return device


def runner_for_device_id(device_id: str):
    device = device_or_404(device_id)
    if hasattr(runner, "for_device"):
        return runner.for_device(device)
    return runner


def device_web_url(device: Dict[str, Any]) -> str:
    return f"http://127.0.0.1:{device['web_port']}/?token={LOCAL_CONFIG['capture']['mitmweb_token']}"


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def is_resident_device(device: Dict[str, Any] | str) -> bool:
    if isinstance(device, str):
        device = device_or_404(device)
    return bool(int(device.get("resident") or 0))


def device_runtime_policy(device: Dict[str, Any]) -> Dict[str, Any]:
    resident = is_resident_device(device)
    return {
        "runtime_policy": "resident" if resident else "on_demand",
        "can_shutdown": not resident,
        "release_behavior": "keep_emulator" if resident else "shutdown_emulator",
    }


def list_active_sessions() -> list[Dict[str, Any]]:
    if hasattr(store, "list_active_sessions"):
        return store.list_active_sessions()
    active = store.active_session()
    return [active] if active else []


def desktop_runtime_metadata() -> Dict[str, Any]:
    return {
        "enabled": os.environ.get("TRACEDECK_DESKTOP", "0").lower() in {"1", "true", "yes", "on"},
        "runtime_dir": str(RUNTIME_DIR),
        "config_path": os.environ.get("TRACEDECK_CONFIG", ""),
    }


def release_device_runtime(device_id: str, *, force_shutdown: bool = False) -> Dict[str, Any]:
    device = device_or_404(device_id)
    device_runner = runner_for_device_id(device_id)
    active = store.active_session(device_id=device_id)
    stop_result = device_runner.stop_capture()
    if active:
        store.update_session_status(active["id"], "stopped")
        store.mark_app_success(active.get("app_id"), mode=active.get("mode", ""))
    clear_result = (
        device_runner.clear_android_proxy()
        if hasattr(device_runner, "clear_android_proxy")
        else CommandResult(0, "", "")
    )
    should_shutdown = force_shutdown or not is_resident_device(device)
    kill_result = (
        device_runner.stop_emulator()
        if should_shutdown and hasattr(device_runner, "stop_emulator")
        else CommandResult(0, "kept resident emulator", "")
    )
    updated = store.release_device(device_id)
    if should_shutdown:
        updated = store.update_device(device_id, sleep_state="sleeping")
    release_behavior = "shutdown_emulator" if should_shutdown else "keep_emulator"
    return {
        "ok": stop_result.ok and clear_result.ok and kill_result.ok,
        "device": {**updated, **device_runtime_policy(updated)},
        "release_behavior": release_behavior,
        "stop": {"stdout": stop_result.stdout, "stderr": stop_result.stderr},
        "proxy": {"stdout": clear_result.stdout, "stderr": clear_result.stderr},
        "emulator": {"stdout": kill_result.stdout, "stderr": kill_result.stderr},
    }


def stop_capture_and_clear_proxy(device_runner: Any) -> tuple[CommandResult, CommandResult]:
    stop_result = device_runner.stop_capture()
    clear_result = (
        device_runner.clear_android_proxy()
        if hasattr(device_runner, "clear_android_proxy")
        else CommandResult(0, "", "")
    )
    return stop_result, clear_result


def auto_release_idle_on_demand_devices() -> list[Dict[str, Any]]:
    released = []
    now = datetime.now(timezone.utc).astimezone()
    for device in store.list_devices(include_disabled=False):
        if is_resident_device(device) or device.get("lease_status") == "running":
            continue
        idle_minutes = int(device.get("idle_release_minutes") or 0)
        if idle_minutes <= 0:
            continue
        last = parse_timestamp(device.get("last_active_at") or device.get("last_release_at"))
        if last is None:
            continue
        if (now - last).total_seconds() < idle_minutes * 60:
            continue
        device_runner = runner_for_device_id(device["device_id"])
        emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
        if emulator.get("adb_online") or emulator.get("process_running"):
            released.append(release_device_runtime(device["device_id"], force_shutdown=True))
        else:
            store.release_device(device["device_id"])
    return released


def ensure_resident_devices() -> list[Dict[str, Any]]:
    store.set_system_state("waking")
    results = []
    for device in store.list_devices(include_disabled=False):
        if not is_resident_device(device):
            continue
        device_runner = runner_for_device_id(device["device_id"])
        emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
        if emulator.get("adb_online") and emulator.get("boot_completed"):
            updated = store.update_device(device["device_id"], sleep_state="awake", error="")
            results.append({"device": {**updated, **device_runtime_policy(updated)}, "started": False, "ok": True})
            continue
        result = device_runner.start_emulator()
        updated = store.update_device(
            device["device_id"],
            sleep_state="awake",
            error="" if result.ok else result.text,
            last_active_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        )
        results.append({
            "device": {**updated, **device_runtime_policy(updated)},
            "started": True,
            "ok": result.ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
    store.set_system_state("running")
    return results


def process_resource_rows() -> list[Dict[str, Any]]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,rss=,command="],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    rows: list[Dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 3:
            continue
        pid, rss, command = parts
        try:
            rows.append({"pid": int(pid), "rss_kb": int(rss), "command": command})
        except ValueError:
            continue
    return rows


def resource_category(command: str) -> Optional[str]:
    command = command.lower()
    if "qemu-system" in command or "emulator" in command and "-avd" in command:
        return "emulator"
    if "flutter_proxy_unpin_capture.py" in command:
        return "frida"
    if "ai_capture_export.py" in command:
        return "exporter"
    if "mitmweb" in command or "mitmdump" in command:
        return "mitm"
    if "uvicorn" in command or "vite" in command:
        return "web"
    return None


def mb(value_kb: int) -> float:
    return round(value_kb / 1024, 2)


def maybe_auto_sleep() -> None:
    if IDLE_SLEEP_SECONDS <= 0:
        return
    if store.get_system_state().get("state") == "sleeping":
        return
    auto_release_idle_on_demand_devices()
    if list_active_sessions():
        return
    devices = store.list_devices(include_disabled=False)
    if not devices:
        return
    last_active = [parse_timestamp(device.get("last_active_at")) for device in devices]
    if any(value is None for value in last_active):
        return
    newest = max(value for value in last_active if value is not None)
    if (datetime.now(timezone.utc).astimezone() - newest).total_seconds() >= IDLE_SLEEP_SECONDS:
        api_system_sleep()


def reconcile_active_session(device_id: str = DEFAULT_DEVICE_ID) -> None:
    active = store.active_session(device_id=device_id)
    device_runner = runner_for_device_id(device_id)
    status = device_runner.capture_status()
    if not active:
        recover_running_session(status, device_id=device_id)
        return
    if active.get("status") == "starting":
        return
    if status.get("exporter") != "running" and status.get("frida_hook") != "running":
        store.update_session_status(active["id"], "stopped")
        return
    runtime_outdir = status.get("outdir") or ""
    if runtime_outdir and active.get("outdir") != runtime_outdir:
        store.update_session_status(active["id"], "stopped")
        recover_running_session(status, device_id=device_id)


def recover_running_session(status: Dict[str, str], *, device_id: str = DEFAULT_DEVICE_ID) -> None:
    if status.get("health") != "running":
        return
    outdir = status.get("outdir", "")
    package_name = status.get("package", "")
    mode = status.get("mode", "")
    if not outdir or not package_name or mode not in {"system", "flutter-socks"}:
        return

    existing = store.get_session_by_outdir(outdir)
    if existing:
        if existing.get("status") not in {"starting", "running", "stopping"}:
            store.update_session_status(existing["id"], "running", web_url=status.get("web") or device_web_url(device_or_404(device_id)))
        return

    target_app = store.get_app_by_package(package_name)
    if not target_app:
        return
    try:
        store.create_session(
            app_id=target_app["id"],
            device_id=device_id,
            mode=mode,
            outdir=outdir,
            status="running",
            web_url=status.get("web") or device_web_url(device_or_404(device_id)),
        )
    except ValueError:
        return


def session_or_404(session_id: int) -> Dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="capture session not found")
    return session


def frontend_html() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def app_or_404(app_id: int) -> Dict[str, Any]:
    target_app = store.get_app(app_id)
    if not target_app:
        raise HTTPException(status_code=404, detail="app not found")
    if not capture_supported(target_app.get("platform")):
        raise HTTPException(status_code=501, detail=unsupported_platform_detail(target_app.get("platform")))
    return target_app


def ensure_no_active_capture_for_update(device_id: str = DEFAULT_DEVICE_ID) -> None:
    reconcile_active_session(device_id=device_id)
    if store.active_session(device_id=device_id):
        raise HTTPException(status_code=409, detail="another capture session is active; stop or cleanup first")
    current = runner_for_device_id(device_id).capture_status()
    if current.get("exporter") == "running" or current.get("frida_hook") == "running":
        raise HTTPException(status_code=409, detail="dirty capture process state; run cleanup first")


def ensure_emulator_ready_for_install(device_id: str = DEFAULT_DEVICE_ID) -> None:
    device_runner = runner_for_device_id(device_id)
    emulator = device_runner.emulator_status()
    if not emulator.get("adb_online") or not emulator.get("boot_completed"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "emulator is not ready for package install",
                "user_message": "请先启动模拟器，等待系统启动完成后再上传更新包。",
                "emulator": emulator,
            },
        )
    if not emulator.get("unlocked"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "emulator is locked",
                "user_message": "请先解锁模拟器后再上传更新包。",
                "emulator": emulator,
            },
        )
    ensure_google_ready(device_runner, device_id=device_id)


def google_not_ready_detail(state: Dict[str, Any], *, device_id: str) -> Dict[str, Any]:
    return {
        "message": "google login required",
        "device_id": device_id,
        "state": state.get("state", "unknown"),
        "ok": False,
        "play_store_installed": bool(state.get("play_store_installed")),
        "google_account_present": bool(state.get("google_account_present")),
        "user_message": state.get("user_message", "请先确认模拟器 Google 登录状态。"),
        "fix": state.get("fix", ""),
        "google_state": state,
    }


def ensure_google_ready(device_runner: Any, *, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
    device_ok = bool(emulator.get("adb_online", True))
    state = device_runner.google_state(device_ok=device_ok)
    if GOOGLE_LOGIN_REQUIRED and not state.get("ok"):
        raise HTTPException(status_code=409, detail=google_not_ready_detail(state, device_id=device_id))
    return state


def version_code_number(value: Any) -> Optional[int]:
    match = re_match_first_int(str(value or ""))
    return int(match) if match is not None else None


def re_match_first_int(value: str) -> Optional[str]:
    import re

    match = re.search(r"\d+", value)
    return match.group(0) if match else None


VERSION_FIELDS = [
    "version_name",
    "version_code",
    "last_update_time",
    "installer_package",
    "signature_hint",
    "apk_archive_path",
    "last_version_check_at",
    "last_validation_status",
    "last_validation_message",
    "last_validation_at",
]


def database_version(app_data: Dict[str, Any]) -> Dict[str, Any]:
    return {field: app_data.get(field) or "" for field in VERSION_FIELDS}


def build_version_response(app_data: Dict[str, Any], device: Dict[str, Any]) -> Dict[str, Any]:
    database = database_version(app_data)
    drift = False
    device_installed = device.get("installed", bool(device.get("version_code") or device.get("version_name")))
    if device_installed:
        drift = bool(
            (database.get("version_code") and database.get("version_code") != (device.get("version_code") or ""))
            or (database.get("version_name") and database.get("version_name") != (device.get("version_name") or ""))
            or not database.get("version_code")
        )
    return {"database": database, "device": device, "drift": drift}


def uploaded_name(filename: str) -> str:
    name = Path(filename or "upload.apk").name
    suffix = Path(name).suffix.lower()
    if suffix not in {".apk", ".zip", ".apks"}:
        raise HTTPException(status_code=400, detail="only .apk, .zip and .apks uploads are supported")
    return name


def collect_uploaded_apks(upload_path: Path, work_dir: Path) -> list[Path]:
    suffix = upload_path.suffix.lower()
    if suffix == ".apk":
        return [upload_path]
    extracted_dir = work_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    apk_paths: list[Path] = []
    try:
        with zipfile.ZipFile(upload_path) as archive:
            for index, member in enumerate(archive.infolist()):
                if member.is_dir() or not member.filename.lower().endswith(".apk"):
                    continue
                target = extracted_dir / f"{index:03d}-{Path(member.filename).name}"
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                apk_paths.append(target)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="uploaded split package is not a valid zip/apks file") from exc
    if not apk_paths:
        raise HTTPException(status_code=400, detail="uploaded zip/apks does not contain apk files")
    return apk_paths


def select_base_apk(apk_paths: list[Path]) -> Path:
    sorted_paths = sorted(apk_paths, key=lambda path: path.name)
    for path in sorted_paths:
        if path.name == "base.apk":
            return path
    for path in sorted_paths:
        if "base" in path.name:
            return path
    return sorted_paths[0]


def archive_latest_apks(package_name: str, apk_paths: list[Path], metadata: Dict[str, Any]) -> Path:
    archive_dir = LATEST_APKS_DIR / package_name
    tmp_dir = archive_dir.with_name(f"{archive_dir.name}.tmp-{uuid.uuid4().hex}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for index, apk_path in enumerate(sorted(apk_paths, key=lambda path: (path.name != "base.apk", path.name))):
            target_name = apk_path.name if apk_path.name.endswith(".apk") else f"{index:03d}.apk"
            shutil.copy2(apk_path, tmp_dir / target_name)
        (tmp_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
        tmp_dir.rename(archive_dir)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    return archive_dir


def uploaded_environment_label(environment: str) -> str:
    return "测试包" if environment == "test" else "生产包"


def auto_app_name(package_name: str, environment: str) -> str:
    return f"{package_name} {uploaded_environment_label(environment)}"


async def save_upload_to_work_dir(request: Request, filename: str, work_dir: Path) -> tuple[str, Path]:
    upload_name = uploaded_name(filename or request.headers.get("x-filename", ""))
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="uploaded package is empty")
    upload_path = work_dir / upload_name
    upload_path.write_bytes(body)
    return upload_name, upload_path


def assert_not_downgrade(package_name: str, apk_info: Dict[str, Any], device_runner: Any) -> None:
    current = device_runner.package_info(package_name)
    current_code = version_code_number(current.get("version_code"))
    upload_code = version_code_number(apk_info.get("version_code"))
    if current.get("installed") and current_code is not None and upload_code is not None and upload_code < current_code:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "downgrade install is not supported",
                "current_version_code": current.get("version_code"),
                "uploaded_version_code": apk_info.get("version_code"),
            },
        )


def build_install_metadata(
    *,
    package_name: str,
    upload_name: str,
    apk_info: Dict[str, Any],
    device: Dict[str, Any],
    apk_paths: list[Path],
    environment: str,
) -> Dict[str, Any]:
    return {
        "package_name": package_name,
        "environment": environment,
        "uploaded_filename": upload_name,
        "apk_info": apk_info,
        "device": device,
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "apk_files": [path.name for path in sorted(apk_paths, key=lambda path: path.name)],
    }


def install_uploaded_package_for_app(
    *,
    device_id: str,
    device_runner: Any,
    target_app: Optional[Dict[str, Any]],
    environment: str,
    upload_name: str,
    apk_paths: list[Path],
    apk_info: Dict[str, Any],
) -> Dict[str, Any]:
    package_name = apk_info.get("package_name") or ""
    if not package_name:
        raise HTTPException(status_code=400, detail={"message": "failed to parse apk package name", "apk": apk_info})
    if target_app and package_name != target_app["package_name"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "uploaded package name does not match selected app",
                "expected": target_app["package_name"],
                "actual": package_name,
            },
        )

    assert_not_downgrade(package_name, apk_info, device_runner)

    install = device_runner.install_apks(apk_paths)
    if not install.ok:
        raise HTTPException(status_code=400, detail={"message": "adb install failed", "output": install.text})

    device = device_runner.package_info(package_name)
    existing_app = target_app or store.get_app_by_package(package_name)
    if existing_app:
        app_record = store.update_app(existing_app["id"], platform="android", environment=environment)
    else:
        app_record = store.create_app(
            platform="android",
            environment=environment,
            name=auto_app_name(package_name, environment),
            package_name=package_name,
            activity=device.get("activity", ""),
            default_mode="flutter-socks",
            notes=f"通过上传更新包自动添加到{uploaded_environment_label(environment)}列表。",
        )

    metadata = build_install_metadata(
        package_name=package_name,
        environment=environment,
        upload_name=upload_name,
        apk_info=apk_info,
        device=device,
        apk_paths=apk_paths,
    )
    archive_dir = archive_latest_apks(package_name, apk_paths, metadata)
    updated = store.update_app_version(app_record["id"], {**device, "apk_archive_path": str(archive_dir)})
    device_app_state = store.update_device_app_version(
        device_id,
        app_record["id"],
        {**device, "apk_archive_path": str(archive_dir)},
    )
    return {
        "ok": True,
        "app": updated,
        "device_app_state": device_app_state,
        "install": {"stdout": install.stdout, "stderr": install.stderr},
        "version": build_version_response(updated, device),
        "archive_path": str(archive_dir),
    }


def validation_result(status: str, message: str, *, flow_count: int = 0, session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": status == "passed",
        "validation": {
            "status": status,
            "message": message,
            "flow_count": flow_count,
            "session": session,
        },
    }


def system_env_check() -> Dict[str, Any]:
    if hasattr(runner, "env_check"):
        return runner.env_check()
    return {"ok": True, "checks": []}


def system_port_preflight() -> Dict[str, Any]:
    return build_port_preflight(
        store.list_devices(include_disabled=False),
        env=os.environ,
        project_root=ROOT_DIR,
        runtime_dir=RUNTIME_DIR,
        collect=collect_port_listeners,
    )


def assert_device_ports_available(device_id: str) -> Dict[str, Any]:
    preflight = system_port_preflight()
    device_prefix = f"{device_id} "
    blocking = [
        item
        for item in preflight["ports"]
        if not item["ok"] and any(part.strip().startswith(device_prefix) for part in item.get("label", "").split(","))
    ]
    if blocking:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "capture device ports are occupied by another project",
                "user_message": "目标设备端口被其他项目占用，已拒绝启动抓包，避免误操作本机其他服务。",
                "blocking_ports": blocking,
                "preflight": preflight,
            },
        )
    return preflight


def frida_state_for_device(device: Dict[str, Any], emulator: Dict[str, Any]) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device["device_id"])
    if not hasattr(device_runner, "frida_server_status"):
        return {"ok": False, "detail": "runner does not support Frida checks"}
    ok, detail = device_runner.frida_server_status(device_ok=bool(emulator.get("adb_online")))
    return {"ok": ok, "detail": detail}


def has_passed_capture_validation() -> bool:
    return any(app.get("last_validation_status") == "passed" for app in store.list_apps())


def setup_completed() -> bool:
    return store.get_system_value(SETUP_COMPLETED_KEY, "0").get("value") == "1"


def build_setup_state(*, force_progress: bool = False) -> Dict[str, Any]:
    env = system_env_check()
    devices = []
    ready_device_count = 0
    for device in store.list_devices(include_disabled=False):
        device_runner = runner_for_device_id(device["device_id"])
        emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
        google = (
            device_runner.google_state(device_ok=bool(emulator.get("adb_online")))
            if hasattr(device_runner, "google_state")
            else {"ok": False, "state": "unknown", "user_message": "无法检查 Google 状态。"}
        )
        frida = frida_state_for_device(device, emulator)
        emulator_ready = bool(emulator.get("adb_online") and emulator.get("boot_completed") and emulator.get("unlocked"))
        google_ready = bool(google.get("ok")) or not GOOGLE_LOGIN_REQUIRED
        ready = bool(emulator_ready and google_ready and frida.get("ok"))
        if ready:
            ready_device_count += 1
        devices.append({
            **device,
            **device_runtime_policy(device),
            "emulator": emulator,
            "google_state": google,
            "frida_state": frida,
            "ready": ready,
        })

    app_count = len(store.list_apps())
    validation_passed = has_passed_capture_validation()
    completed = setup_completed()
    checked = force_progress or store.get_system_value(SETUP_CHECKED_KEY, "0").get("value") == "1"
    step_defs = [
        ("env", "服务环境检查", bool(env.get("ok")), "检查 Python、Node、Android SDK、mitmproxy、Frida 等依赖。"),
        ("devices", "设备发现", bool(devices), "发现至少一台在线 Android 设备。"),
        (
            "emulator",
            "设备就绪",
            any(
                device.get("emulator", {}).get("adb_online")
                and device.get("emulator", {}).get("boot_completed")
                and device.get("emulator", {}).get("unlocked")
                for device in devices
            ),
            "确认设备在线、Android 系统完成启动，并完成解锁。",
        ),
        (
            "google",
            "Google 状态",
            True if not GOOGLE_LOGIN_REQUIRED else any(device.get("google_state", {}).get("ok") for device in devices),
            "按目标 App 需要确认 Google Play 或账号状态。",
        ),
        ("frida", "Frida 准入", any(device.get("frida_state", {}).get("ok") for device in devices), "启动 Frida server 并确认可连接。"),
        ("app", "上传或选择 App", app_count > 0, "上传 APK 或选择已有应用。"),
        ("smoke", "抓包冒烟测试", validation_passed, "完成一次抓包校验并捕获接口。"),
        ("complete", "完成初始化", completed, "进入主控制台。"),
    ]
    current_step = "complete" if completed else "env"
    if checked and not completed:
        current_step = "complete"
        for key, _label, ok, _description in step_defs[:-1]:
            if not ok:
                current_step = key
                break

    steps = [
        {
            "key": key,
            "label": label,
            "ok": bool(ok),
            "current": key == current_step,
            "description": description,
        }
        for key, label, ok, description in step_defs
    ]
    return {
        "completed": completed,
        "checked": checked,
        "current_step": current_step,
        "ready_to_complete": bool(env.get("ok") and ready_device_count >= 1 and validation_passed),
        "google_login_required": GOOGLE_LOGIN_REQUIRED,
        "env": env,
        "devices": devices,
        "app_count": app_count,
        "validation_passed": validation_passed,
        "steps": steps,
    }


@app.on_event("startup")
def startup() -> None:
    clear_project_capture_records()
    threading.Thread(target=ensure_resident_devices, daemon=True).start()


@app.on_event("shutdown")
def shutdown() -> None:
    clear_project_capture_records()


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    device = store.get_device(DEFAULT_DEVICE_ID)
    if device is not None and not device.get("enabled"):
        device = None
    if device is None:
        devices = store.list_devices(include_disabled=False)
        device = devices[0] if devices else None
    if device is None:
        return {
            "health": "idle",
            "exporter": "missing",
            "frida_hook": "missing",
            "active_session": None,
            "emulator": {"adb_online": False, "boot_completed": False, "unlocked": False},
            "system": store.get_system_state(),
            "desktop": desktop_runtime_metadata(),
            "user_message": "未发现在线设备。请连接 Android 设备或启动模拟器后刷新设备。",
        }
    device_id = str(device["device_id"])
    reconcile_active_session(device_id)
    default_runner = runner_for_device_id(device_id)
    status = default_runner.capture_status()
    status["active_session"] = store.active_session(device_id=device_id)
    status["emulator"] = default_runner.emulator_status()
    status["system"] = store.get_system_state()
    status["device_id"] = device_id
    status["desktop"] = desktop_runtime_metadata()
    return status


@app.get("/api/system/env-check")
def api_system_env_check() -> Dict[str, Any]:
    return {"env": system_env_check()}


@app.get("/api/system/preflight")
def api_system_preflight() -> Dict[str, Any]:
    return {"preflight": system_port_preflight()}


@app.get("/api/system/network-check")
def api_system_network_check() -> Dict[str, Any]:
    return {"network": build_host_network_check(os.environ)}


@app.get("/api/setup/state")
def api_setup_state() -> Dict[str, Any]:
    return {"setup": build_setup_state()}


@app.post("/api/setup/check")
def api_setup_check() -> Dict[str, Any]:
    store.set_system_value(SETUP_CHECKED_KEY, "1")
    return {"setup": build_setup_state(force_progress=True)}


@app.post("/api/setup/mark-complete")
def api_setup_mark_complete() -> Dict[str, Any]:
    state = build_setup_state(force_progress=True)
    if not state["ready_to_complete"]:
        raise HTTPException(status_code=409, detail={"message": "setup is not ready to complete", "setup": state})
    store.set_system_value(SETUP_COMPLETED_KEY, "1")
    store.set_system_value(SETUP_CHECKED_KEY, "1")
    return {"setup": build_setup_state(force_progress=True)}


@app.post("/api/setup/reset")
def api_setup_reset() -> Dict[str, Any]:
    store.set_system_value(SETUP_COMPLETED_KEY, "0")
    store.set_system_value(SETUP_CHECKED_KEY, "0")
    return {"setup": build_setup_state()}


def build_device_status(device: Dict[str, Any]) -> Dict[str, Any]:
    reconcile_active_session(device_id=device["device_id"])
    device_runner = runner_for_device_id(device["device_id"])
    emulator = device_runner.emulator_status()
    current_avd = str(emulator.get("current_avd") or "").strip()
    if current_avd and not str(device.get("avd_name") or "").strip():
        device = store.update_device(str(device["device_id"]), avd_name=current_avd)
    return {
        **device,
        **device_runtime_policy(device),
        "emulator": emulator,
        "capture": device_runner.capture_status(),
        "google_state": device_runner.google_state(device_ok=bool(emulator.get("adb_online"))),
        "active_session": store.active_session(device_id=device["device_id"]),
    }


def runner_network_state(device_runner: Any) -> Dict[str, Any]:
    if hasattr(device_runner, "network_state"):
        return device_runner.network_state()
    emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
    return build_device_network_state(emulator)


def discovery_occupied_ports(slot_count: int = 20) -> set[int]:
    capture = LOCAL_CONFIG["capture"]
    ports: set[int] = set()
    for slot in range(slot_count):
        for port in (
            int(capture["proxy_port_start"]) + slot * 10,
            int(capture["web_port_start"]) + slot * 10,
            int(capture["frida_port_start"]) + slot * 100,
        ):
            if collect_port_listeners(port):
                ports.add(port)
    return ports


@app.get("/api/devices")
def api_list_devices() -> Dict[str, Any]:
    maybe_auto_sleep()
    return {
        "system": store.get_system_state(),
        "devices": [build_device_status(device) for device in store.list_devices(include_disabled=False)],
    }


@app.get("/api/devices/discover")
def api_discover_devices() -> Dict[str, Any]:
    adb_devices = runner.discover_adb_devices() if hasattr(runner, "discover_adb_devices") else []
    discovered = build_discovered_devices(
        adb_devices,
        proxy_port_start=int(LOCAL_CONFIG["capture"]["proxy_port_start"]),
        web_port_start=int(LOCAL_CONFIG["capture"]["web_port_start"]),
        frida_port_start=int(LOCAL_CONFIG["capture"]["frida_port_start"]),
        occupied_ports=discovery_occupied_ports(),
    )
    device_fields = {
        "device_id",
        "name",
        "avd_name",
        "adb_serial",
        "proxy_port",
        "web_port",
        "frida_port",
        "enabled",
        "resident",
        "idle_release_minutes",
    }
    seen_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    persisted = []
    for device in discovered:
        stored_device = store.upsert_device(**{key: device[key] for key in device_fields})
        stored_device = store.update_device(
            stored_device["device_id"],
            sleep_state="awake",
            error="",
            last_active_at=seen_at,
        )
        persisted.append(stored_device)
    if hasattr(store, "disable_devices_except"):
        store.disable_devices_except([str(device["device_id"]) for device in persisted])
    return {
        "devices": persisted,
        "count": len(persisted),
        "source": "adb",
        "user_message": "已发现在线 Android 设备。" if persisted else "未发现在线设备。请连接设备或启动模拟器后重试。",
    }


@app.get("/api/emulator")
def api_emulator_status(device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    return runner_for_device_id(device_id).emulator_status()


@app.post("/api/emulator/start")
def api_start_emulator(device_id: str = DEFAULT_DEVICE_ID, visible: bool = False) -> Dict[str, Any]:
    store.set_system_state("waking")
    device_runner = runner_for_device_id(device_id)
    result = device_runner.start_emulator(visible=visible)
    store.set_system_state("running")
    store.touch_device(device_id)
    return {
        "ok": result.ok,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "status": device_runner.emulator_status(),
    }


@app.post("/api/devices/{device_id}/start")
def api_start_device(device_id: str, visible: bool = False) -> Dict[str, Any]:
    return api_start_emulator(device_id=device_id, visible=visible)


@app.get("/api/devices/{device_id}/preview")
def api_device_preview(device_id: str, request: Request) -> Dict[str, Any]:
    device = device_or_404(device_id)
    host = request.url.hostname or (request.client.host if request.client else "127.0.0.1")
    token = preview_token()
    url = preview_url(
        preview_base_url(host),
        token,
        device_id=str(device["device_id"]),
        adb_serial=str(device["adb_serial"]),
    )
    return {
        "device_id": device["device_id"],
        "adb_serial": device["adb_serial"],
        "url": url,
        "available": True,
        "token_configured": bool(token),
        "user_message": "已生成模拟器预览入口。",
    }


@app.post("/api/devices/{device_id}/lease")
def api_lease_device(device_id: str, owner: str = "") -> Dict[str, Any]:
    store.set_system_state("running")
    return {"device": store.lease_device(device_id, owner=owner)}


@app.post("/api/devices/{device_id}/release")
def api_release_device(device_id: str, force_shutdown: bool = False) -> Dict[str, Any]:
    return release_device_runtime(device_id, force_shutdown=force_shutdown)


@app.get("/api/devices/{device_id}/google-state")
def api_device_google_state(device_id: str) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    emulator = device_runner.emulator_status() if hasattr(device_runner, "emulator_status") else {}
    return {"device_id": device_id, "google_state": device_runner.google_state(device_ok=bool(emulator.get("adb_online", True)))}


@app.get("/api/devices/{device_id}/network-state")
def api_device_network_state(device_id: str) -> Dict[str, Any]:
    return {"device_id": device_id, "network": runner_network_state(runner_for_device_id(device_id))}


@app.post("/api/devices/{device_id}/network/maintenance")
def api_device_network_maintenance(device_id: str, proxy: str = "") -> Dict[str, Any]:
    if store.active_session(device_id=device_id):
        raise HTTPException(status_code=409, detail="active capture exists; stop capture before switching to maintenance proxy")
    target_proxy = proxy.strip() or proxy_from_env(os.environ)
    if not target_proxy:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "maintenance proxy is not configured",
                "user_message": "未配置维护代理，无法切换模拟器到网页登录/下载使用的代理网络。",
                "fix": "设置 CAPTURE_EMULATOR_PROXY，例如 127.0.0.1:7890，然后重试。",
            },
        )
    device_runner = runner_for_device_id(device_id)
    if not hasattr(device_runner, "enter_maintenance_network"):
        result = device_runner.set_android_proxy(target_proxy)
        return {"device_id": device_id, "ok": result.ok, "stdout": result.stdout, "stderr": result.stderr, "network": runner_network_state(device_runner)}
    return {"device_id": device_id, **device_runner.enter_maintenance_network(target_proxy)}


@app.post("/api/devices/{device_id}/network/capture")
def api_device_network_capture(device_id: str) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    if not hasattr(device_runner, "enter_capture_network"):
        result = device_runner.clear_android_proxy()
        return {"device_id": device_id, "ok": result.ok, "stdout": result.stdout, "stderr": result.stderr, "network": runner_network_state(device_runner)}
    return {"device_id": device_id, **device_runner.enter_capture_network()}


@app.post("/api/devices/{device_id}/network/clear-proxy")
def api_device_network_clear_proxy(device_id: str) -> Dict[str, Any]:
    return api_device_network_capture(device_id)


@app.post("/api/devices/{device_id}/open-google-login")
def api_open_google_login(device_id: str) -> Dict[str, Any]:
    return {"device_id": device_id, **runner_for_device_id(device_id).open_google_login()}


@app.post("/api/devices/{device_id}/prepare-frida")
def api_prepare_frida(device_id: str) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    if not hasattr(device_runner, "prepare_frida_server"):
        raise HTTPException(status_code=501, detail="runner does not support Frida preparation")
    return {"device_id": device_id, **device_runner.prepare_frida_server()}


@app.post("/api/system/sleep")
def api_system_sleep() -> Dict[str, Any]:
    if list_active_sessions():
        raise HTTPException(status_code=409, detail="active capture exists; stop captures before sleeping")
    store.set_system_state("sleeping")
    results = []
    for device in store.list_devices(include_disabled=False):
        device_runner = runner_for_device_id(device["device_id"])
        device_runner.stop_capture()
        if hasattr(device_runner, "clear_android_proxy"):
            device_runner.clear_android_proxy()
        if hasattr(device_runner, "stop_emulator"):
            device_runner.stop_emulator()
        updated = store.update_device(
            device["device_id"],
            lease_status="idle",
            lease_owner="",
            current_session_id=None,
            sleep_state="sleeping",
            last_active_at=store.get_system_state()["updated_at"],
        )
        results.append({**updated, **device_runtime_policy(updated)})
    return {"system": store.get_system_state(), "devices": results}


@app.post("/api/system/wake")
def api_system_wake() -> Dict[str, Any]:
    system = store.set_system_state("running")
    for device in store.list_devices(include_disabled=False):
        store.update_device(device["device_id"], sleep_state="awake", error="")
    return {"system": system, "devices": store.list_devices(include_disabled=False)}


@app.post("/api/system/ensure-resident")
def api_system_ensure_resident() -> Dict[str, Any]:
    return {"system": store.get_system_state(), "results": ensure_resident_devices()}


@app.get("/api/system/resources")
def api_system_resources() -> Dict[str, Any]:
    rows = []
    totals_kb = {"emulator": 0, "mitm": 0, "frida": 0, "exporter": 0, "web": 0}
    for row in process_resource_rows():
        category = resource_category(row["command"])
        if not category:
            continue
        totals_kb[category] += row["rss_kb"]
        rows.append({**row, "category": category, "rss_mb": mb(row["rss_kb"])})
    capture_related_kb = sum(totals_kb.values())
    return {
        "processes": rows,
        "totals": {
            "emulator_mb": mb(totals_kb["emulator"]),
            "mitm_mb": mb(totals_kb["mitm"]),
            "frida_mb": mb(totals_kb["frida"]),
            "exporter_mb": mb(totals_kb["exporter"]),
            "web_mb": mb(totals_kb["web"]),
            "capture_related_mb": mb(capture_related_kb),
        },
    }


@app.post("/api/cleanup")
def api_cleanup(device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    result, proxy_result = stop_capture_and_clear_proxy(device_runner)
    active = store.active_session(device_id=device_id)
    if active:
        store.update_session_status(active["id"], "stopped")
    return {
        "ok": result.ok and proxy_result.ok,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "proxy": {"stdout": proxy_result.stdout, "stderr": proxy_result.stderr},
    }


@app.get("/api/apps")
def api_list_apps() -> Dict[str, Any]:
    return {"apps": store.list_apps()}


@app.post("/api/apps")
def api_create_app(payload: AppPayload) -> Dict[str, Any]:
    return {"app": store.create_app(**payload.model_dump())}


@app.put("/api/apps/{app_id}")
def api_update_app(app_id: int, payload: AppPayload) -> Dict[str, Any]:
    try:
        return {"app": store.update_app(app_id, **payload.model_dump(exclude_unset=True))}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/apps/{app_id}")
def api_delete_app(app_id: int) -> Dict[str, Any]:
    store.delete_app(app_id)
    return {"ok": True}


@app.get("/api/package-sources/jenkins/packages")
def api_jenkins_packages() -> Dict[str, Any]:
    try:
        packages = jenkins_source.list_latest_packages()
    except JenkinsSourceError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc
    return {
        "source": {
            "type": "jenkins",
            "base_url": jenkins_source.config.base_url,
            "count": len(packages),
            "errors": jenkins_source.last_errors[:20],
        },
        "packages": packages,
    }


@app.post("/api/package-sources/jenkins/install")
def api_install_jenkins_package(payload: JenkinsInstallPayload) -> Dict[str, Any]:
    device_runner = runner_for_device_id(payload.device_id)
    ensure_no_active_capture_for_update(device_id=payload.device_id)
    ensure_emulator_ready_for_install(device_id=payload.device_id)
    target_environment = validate_app_environment(payload.environment)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jenkins-install-", dir=str(UPLOADS_DIR)) as tmp:
        work_dir = Path(tmp)
        try:
            upload_name, upload_path = jenkins_source.download_package(
                job_name=payload.job_name,
                build_number=payload.build_number,
                artifact_relative_path=payload.artifact_relative_path,
                destination_dir=work_dir,
            )
        except JenkinsSourceError as exc:
            raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc

        apk_paths = collect_uploaded_apks(upload_path, work_dir)
        base_apk = select_base_apk(apk_paths)
        apk_info = device_runner.inspect_apk(base_apk)
        result = install_uploaded_package_for_app(
            device_id=payload.device_id,
            device_runner=device_runner,
            target_app=None,
            environment=target_environment,
            upload_name=upload_name,
            apk_paths=apk_paths,
            apk_info=apk_info,
        )
        result["source"] = {
            "type": "jenkins",
            "job_name": payload.job_name,
            "build_number": payload.build_number,
            "artifact_relative_path": payload.artifact_relative_path,
        }
        return result


@app.post("/api/apps/{app_id}/launch")
def api_launch_app(app_id: int, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    target_app = store.get_app(app_id)
    if not target_app:
        raise HTTPException(status_code=404, detail="app not found")
    if not capture_supported(target_app.get("platform")):
        raise HTTPException(status_code=501, detail=unsupported_platform_detail(target_app.get("platform")))

    device_runner = runner_for_device_id(device_id)
    ensure_google_ready(device_runner, device_id=device_id)
    result = device_runner.launch_app(
        package_name=target_app["package_name"],
        activity=target_app.get("activity", ""),
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail={"message": "app launch failed", "output": result.text})
    return {
        "ok": True,
        "app": target_app,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "status": device_runner.emulator_status(),
    }


@app.get("/api/apps/{app_id}/readiness")
def api_app_readiness(app_id: int, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    target_app = store.get_app(app_id)
    if not target_app:
        raise HTTPException(status_code=404, detail="app not found")
    if not capture_supported(target_app.get("platform")):
        raise HTTPException(status_code=501, detail=unsupported_platform_detail(target_app.get("platform")))

    reconcile_active_session(device_id=device_id)
    device_runner = runner_for_device_id(device_id)
    capture_status = device_runner.capture_status()
    active = store.active_session(device_id=device_id)
    emulator = device_runner.emulator_status()
    health = device_runner.health_check(
        package_name=target_app["package_name"],
        mode=target_app.get("default_mode", "system"),
        activity=target_app.get("activity", ""),
    )

    flow_count = 0
    if active and active.get("package_name") == target_app["package_name"]:
        flow_count = len(scan_capture(Path(active["outdir"])))

    readiness = build_readiness_report(
        app=target_app,
        health=health,
        capture_status=capture_status,
        active_session=active,
        flow_count=flow_count,
        foreground=emulator.get("foreground", ""),
    )
    return {"readiness": readiness}


@app.get("/api/installed-apps")
def api_installed_apps(query: str = "", device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    return api_apps_installed(query=query, device_id=device_id)


@app.get("/api/apps/installed")
def api_apps_installed(query: str = "", device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    return {"apps": runner_for_device_id(device_id).scan_installed_apps(query=query)}


@app.get("/api/apps/{app_id}/version")
def api_get_app_version(app_id: int, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    target_app = app_or_404(app_id)
    device = runner_for_device_id(device_id).package_info(target_app["package_name"])
    device_state = store.get_device_app_state(device_id, app_id)
    return {"app": target_app, "device_app_state": device_state, "version": build_version_response(target_app, device)}


@app.post("/api/apps/{app_id}/sync-version")
def api_sync_app_version(app_id: int, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    target_app = app_or_404(app_id)
    device = runner_for_device_id(device_id).package_info(target_app["package_name"])
    if not device.get("installed", bool(device.get("version_code") or device.get("version_name"))):
        raise HTTPException(status_code=400, detail={"message": "app is not installed", "version": device})
    updated = store.update_app_version(app_id, device)
    device_app_state = store.update_device_app_version(device_id, app_id, device)
    return {"app": updated, "device_app_state": device_app_state, "version": build_version_response(updated, device)}


@app.post("/api/apps/{app_id}/install")
async def api_install_app(
    app_id: int,
    request: Request,
    filename: str = "",
    environment: str = "",
    device_id: str = DEFAULT_DEVICE_ID,
) -> Dict[str, Any]:
    target_app = app_or_404(app_id)
    device_runner = runner_for_device_id(device_id)
    ensure_no_active_capture_for_update(device_id=device_id)
    ensure_emulator_ready_for_install(device_id=device_id)
    target_environment = validate_app_environment(environment or target_app.get("environment") or "production")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="install-", dir=str(UPLOADS_DIR)) as tmp:
        work_dir = Path(tmp)
        upload_name, upload_path = await save_upload_to_work_dir(request, filename, work_dir)
        apk_paths = collect_uploaded_apks(upload_path, work_dir)
        base_apk = select_base_apk(apk_paths)
        apk_info = device_runner.inspect_apk(base_apk)
        return install_uploaded_package_for_app(
            device_id=device_id,
            device_runner=device_runner,
            target_app=target_app,
            environment=target_environment,
            upload_name=upload_name,
            apk_paths=apk_paths,
            apk_info=apk_info,
        )


@app.post("/api/apps/install")
async def api_install_uploaded_app(
    request: Request,
    filename: str = "",
    environment: str = "production",
    device_id: str = DEFAULT_DEVICE_ID,
) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    ensure_no_active_capture_for_update(device_id=device_id)
    ensure_emulator_ready_for_install(device_id=device_id)
    target_environment = validate_app_environment(environment)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="install-", dir=str(UPLOADS_DIR)) as tmp:
        work_dir = Path(tmp)
        upload_name, upload_path = await save_upload_to_work_dir(request, filename, work_dir)
        apk_paths = collect_uploaded_apks(upload_path, work_dir)
        base_apk = select_base_apk(apk_paths)
        apk_info = device_runner.inspect_apk(base_apk)
        return install_uploaded_package_for_app(
            device_id=device_id,
            device_runner=device_runner,
            target_app=None,
            environment=target_environment,
            upload_name=upload_name,
            apk_paths=apk_paths,
            apk_info=apk_info,
        )


@app.post("/api/apps/{app_id}/validate-capture")
def api_validate_capture(app_id: int, device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    target_app = app_or_404(app_id)
    device_runner = runner_for_device_id(device_id)
    ensure_no_active_capture_for_update(device_id=device_id)
    ensure_google_ready(device_runner, device_id=device_id)
    assert_device_ports_available(device_id)

    requested_mode = normalize_requested_capture_mode(target_app, None)
    candidates = capture_mode_candidates(target_app, requested_mode)
    mode_attempts: list[Dict[str, Any]] = []

    for mode in candidates:
        attempt: Dict[str, Any] = {"mode": mode, "status": "starting"}
        mode_attempts.append(attempt)
        if mode == "flutter-socks":
            if hasattr(device_runner, "enter_capture_network"):
                network_switch = device_runner.enter_capture_network()
                attempt["network"] = network_switch
                if not network_switch.get("ok"):
                    attempt["status"] = "failed"
                    attempt["reason"] = "network"
                    stop_capture_and_clear_proxy(device_runner)
                    continue
            elif hasattr(device_runner, "clear_android_proxy"):
                device_runner.clear_android_proxy()

        health = device_runner.health_check(
            package_name=target_app["package_name"],
            mode=mode,
            activity=target_app.get("activity", ""),
        )
        attempt["health"] = health
        if not health["ok"]:
            attempt["status"] = "failed"
            attempt["reason"] = "health"
            stop_capture_and_clear_proxy(device_runner)
            continue

        activity = target_app.get("activity") or health.get("resolved_activity", "")
        launch = device_runner.launch_app(package_name=target_app["package_name"], activity=activity)
        if not launch.ok:
            attempt["status"] = "failed"
            attempt["reason"] = "launch"
            attempt["output"] = launch.text
            stop_capture_and_clear_proxy(device_runner)
            continue

        outdir_name = f"{target_app['name']}-validation" if len(candidates) == 1 else f"{target_app['name']}-validation-{mode}"
        outdir = str(device_runner.make_outdir(outdir_name))
        session = store.create_session(
            app_id=app_id,
            device_id=device_id,
            mode=mode,
            outdir=outdir,
            status="starting",
            web_url=device_web_url(device_or_404(device_id)),
        )
        started = False
        try:
            started_capture = device_runner.start_capture(
                package_name=target_app["package_name"],
                activity=activity,
                mode=mode,
                outdir=outdir,
                interval=1.0,
            )
            if not started_capture.ok:
                failed_session = store.update_session_status(session["id"], "failed", error=started_capture.text)
                attempt["status"] = "failed"
                attempt["reason"] = "start"
                attempt["session"] = failed_session
                attempt["output"] = started_capture.text
                stop_capture_and_clear_proxy(device_runner)
                continue

            started = True
            store.update_session_status(session["id"], "running", web_url=device_web_url(device_or_404(device_id)))
            deadline = time.time() + 30
            flows = []
            while time.time() < deadline:
                flows = scan_capture(Path(outdir))
                if any(flow.get("has_request_json") or flow.get("has_response_json") for flow in flows):
                    break
                time.sleep(2)

            flow_count = len(flows)
            has_payload = any(flow.get("has_request_json") or flow.get("has_response_json") for flow in flows)
            stopped_session = store.update_session_status(session["id"], "stopped")
            stop_capture_and_clear_proxy(device_runner)
            started = False
            attempt["flow_count"] = flow_count
            attempt["session_id"] = stopped_session["id"]
            if has_payload:
                status = "passed"
                message = f"抓包校验通过，捕获到 {flow_count} 条接口。"
                updated = store.update_app_validation(app_id, status=status, message=message)
                store.update_device_app_validation(device_id, app_id, status=status, message=message)
                store.mark_app_success(app_id, mode=mode)
                attempt["status"] = "passed"
                return {
                    **validation_result(status, message, flow_count=flow_count, session=stopped_session),
                    "app": updated,
                    "requested_mode": requested_mode,
                    "mode_attempts": mode_attempts,
                }

            attempt["status"] = "warning"
            attempt["reason"] = "no_json"
            if requested_mode != "auto" or mode == candidates[-1]:
                status = "warning"
                message = "应用已启动，但 30 秒内未捕获到可解析接口；请手动操作应用进一步确认。"
                updated = store.update_app_validation(app_id, status=status, message=message)
                store.update_device_app_validation(device_id, app_id, status=status, message=message)
                return {
                    **validation_result(status, message, flow_count=flow_count, session=stopped_session),
                    "app": updated,
                    "requested_mode": requested_mode,
                    "mode_attempts": mode_attempts,
                }
        finally:
            if started:
                stop_capture_and_clear_proxy(device_runner)
                active = store.get_session(session["id"])
                if active and active.get("status") in {"starting", "running", "stopping"}:
                    store.update_session_status(session["id"], "stopped")

    message = "没有可用的抓包模式。"
    updated = store.update_app_validation(app_id, status="failed", message=message)
    store.update_device_app_validation(device_id, app_id, status="failed", message=message)
    return {
        **validation_result("failed", message),
        "app": updated,
        "requested_mode": requested_mode,
        "mode_attempts": mode_attempts,
    }


@app.get("/api/captures")
def api_list_captures() -> Dict[str, Any]:
    return {"sessions": store.list_sessions()}


@app.post("/api/captures/start")
def api_start_capture(payload: CaptureStartPayload) -> Dict[str, Any]:
    target_app = store.get_app(payload.app_id)
    if not target_app:
        raise HTTPException(status_code=404, detail="app not found")
    if not capture_supported(target_app.get("platform")):
        raise HTTPException(status_code=501, detail=unsupported_platform_detail(target_app.get("platform")))

    device_id = payload.device_id or DEFAULT_DEVICE_ID
    device_runner = runner_for_device_id(device_id)
    store.set_system_state("running")
    reconcile_active_session(device_id=device_id)
    if store.active_session(device_id=device_id):
        raise HTTPException(status_code=409, detail="another capture session is active; stop or cleanup first")

    current = device_runner.capture_status()
    if current.get("exporter") == "running" or current.get("frida_hook") == "running":
        raise HTTPException(status_code=409, detail="dirty capture process state; run cleanup first")
    ensure_google_ready(device_runner, device_id=device_id)
    assert_device_ports_available(device_id)

    requested_mode = normalize_requested_capture_mode(target_app, payload.mode)
    candidates = capture_mode_candidates(target_app, requested_mode)
    mode_attempts: list[Dict[str, Any]] = []

    for mode in candidates:
        attempt: Dict[str, Any] = {"mode": mode, "status": "starting"}
        mode_attempts.append(attempt)
        if mode == "flutter-socks":
            if hasattr(device_runner, "enter_capture_network"):
                network_switch = device_runner.enter_capture_network()
                attempt["network"] = network_switch
                if not network_switch.get("ok"):
                    attempt["status"] = "failed"
                    attempt["reason"] = "network"
                    stop_capture_and_clear_proxy(device_runner)
                    continue
            elif hasattr(device_runner, "clear_android_proxy"):
                clear = device_runner.clear_android_proxy()
                if not clear.ok:
                    attempt["status"] = "failed"
                    attempt["reason"] = "network"
                    attempt["output"] = clear.text
                    stop_capture_and_clear_proxy(device_runner)
                    continue

        health = device_runner.health_check(package_name=target_app["package_name"], mode=mode, activity=target_app.get("activity", ""))
        attempt["health"] = health
        if not health["ok"]:
            attempt["status"] = "failed"
            attempt["reason"] = "health"
            stop_capture_and_clear_proxy(device_runner)
            continue

        activity = target_app["activity"] or health.get("resolved_activity", "")
        outdir_name = target_app["name"] if len(candidates) == 1 else f"{target_app['name']}-{mode}"
        outdir = str(device_runner.make_outdir(outdir_name))
        try:
            session = store.create_session(
                app_id=target_app["id"],
                device_id=device_id,
                mode=mode,
                outdir=outdir,
                status="starting",
                web_url=device_web_url(device_or_404(device_id)),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        result = device_runner.start_capture(
            package_name=target_app["package_name"],
            activity=activity,
            mode=mode,
            outdir=outdir,
        )
        if not result.ok:
            failed = store.update_session_status(session["id"], "failed", error=result.text)
            attempt["status"] = "failed"
            attempt["reason"] = "start"
            attempt["session"] = failed
            attempt["output"] = result.text
            stop_capture_and_clear_proxy(device_runner)
            continue

        running = store.update_session_status(session["id"], "running", web_url=device_web_url(device_or_404(device_id)))
        attempt["status"] = "running"
        attempt["session_id"] = running["id"]
        return {
            "session": running,
            "output": result.stdout,
            "requested_mode": requested_mode,
            "mode_attempts": mode_attempts,
        }

    raise HTTPException(
        status_code=500 if any(attempt.get("reason") == "start" for attempt in mode_attempts) else 400,
        detail={
            "message": "no capture mode could start",
            "requested_mode": requested_mode,
            "mode_attempts": mode_attempts,
        },
    )


@app.post("/api/captures/stop")
def api_stop_capture(device_id: str = DEFAULT_DEVICE_ID) -> Dict[str, Any]:
    device_runner = runner_for_device_id(device_id)
    result, proxy_result = stop_capture_and_clear_proxy(device_runner)
    active = store.active_session(device_id=device_id)
    session = None
    if active:
        session = store.update_session_status(active["id"], "stopped")
        store.mark_app_success(active.get("app_id"), mode=active.get("mode", ""))
    return {
        "ok": result.ok and proxy_result.ok,
        "session": session,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "proxy": {"stdout": proxy_result.stdout, "stderr": proxy_result.stderr},
    }


@app.post("/api/captures/{session_id}/stop")
def api_stop_capture_session(session_id: int) -> Dict[str, Any]:
    session = session_or_404(session_id)
    device_id = session.get("device_id") or DEFAULT_DEVICE_ID
    device_runner = runner_for_device_id(device_id)
    result, proxy_result = stop_capture_and_clear_proxy(device_runner)
    stopped = store.update_session_status(session_id, "stopped")
    store.mark_app_success(session.get("app_id"), mode=session.get("mode", ""))
    return {
        "ok": result.ok and proxy_result.ok,
        "session": stopped,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "proxy": {"stdout": proxy_result.stdout, "stderr": proxy_result.stderr},
    }


@app.get("/api/captures/{session_id}")
def api_get_capture(session_id: int) -> Dict[str, Any]:
    session = session_or_404(session_id)
    outdir = Path(session["outdir"])
    flows = scan_capture(outdir)
    return {"session": session, "flow_count": len(flows)}


@app.get("/api/captures/{session_id}/flows")
def api_get_flows(session_id: int) -> Dict[str, Any]:
    session = session_or_404(session_id)
    flows = scan_capture(Path(session["outdir"]))
    return {"flows": flows}


@app.get("/api/captures/{session_id}/flows/{flow_id}")
def api_get_flow_detail(session_id: int, flow_id: str) -> Dict[str, Any]:
    session = session_or_404(session_id)
    try:
        return get_flow_detail(Path(session["outdir"]), flow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/captures/{session_id}/flows/{flow_id}/curl", response_class=PlainTextResponse)
def api_get_flow_curl(session_id: int, flow_id: str) -> str:
    session = session_or_404(session_id)
    try:
        detail = get_flow_detail(Path(session["outdir"]), flow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_curl(detail)


@app.get("/api/captures/{session_id}/export")
def api_export_capture(session_id: int) -> Dict[str, Any]:
    session = session_or_404(session_id)
    outdir = Path(session["outdir"])
    files = [str(path) for path in sorted(outdir.glob("*")) if path.is_file()]
    return {"outdir": str(outdir), "files": files}


dist_dir = ROOT_DIR / "web" / "dist"
app.mount("/assets", StaticFiles(directory=dist_dir / "assets", check_dir=False), name="assets")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    built_index = dist_dir / "index.html"
    if built_index.exists():
        return built_index.read_text(encoding="utf-8")
    return frontend_html()


@app.get("/{path:path}", response_class=HTMLResponse)
def spa_fallback(path: str) -> str:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="not found")
    return index()
