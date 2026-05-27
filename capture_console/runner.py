from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .network import build_device_network_state
from .status import parse_capture_status


DESTRUCTIVE_COMMAND_PATTERNS = (
    ("emulator", "-wipe-data"),
    ("avdmanager", "delete"),
    ("adb", "pm", "clear"),
    ("adb", "uninstall"),
)
RETAINED_ADB_SERIAL = "emulator-5554"
RETAINED_AVD_NAME = "Medium_Phone_API_36.1"


def health_check_item(name: str, ok: bool, detail: str, user_message: str, fix: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "detail": detail,
        "user_message": user_message,
        "fix": fix,
    }


@dataclass
class CommandResult:
    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    @property
    def text(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


class ConsoleRunner:
    def __init__(
        self,
        root_dir: str | Path,
        *,
        adb_serial: str = "emulator-5554",
        avd_name: str = "Medium_Phone_API_36.1",
        proxy_port: int = 9090,
        web_port: int = 9091,
        frida_port: int = 27042,
        mitm_password: str = "android-capture",
        capture_instance: str = "device-1",
        allow_non_retained: bool = False,
        runtime_dir: str | Path | None = None,
    ):
        self.root_dir = Path(root_dir)
        self.runtime_dir = Path(runtime_dir or os.environ.get("CAPTURE_RUNTIME_DIR") or self.root_dir / "runtime").expanduser().resolve()
        self.scripts_dir = self.root_dir / "scripts"
        self.adb_serial = adb_serial
        self.avd_name = avd_name
        self.proxy_port = proxy_port
        self.web_port = web_port
        self.frida_port = frida_port
        self.mitm_password = mitm_password
        self.capture_instance = capture_instance
        self.allow_non_retained = allow_non_retained
        self.adb_bin = Path.home() / "Library/Android/sdk/platform-tools/adb"
        if not self.adb_bin.exists():
            self.adb_bin = Path("adb")

    def for_device(self, device: Dict[str, Any]) -> "ConsoleRunner":
        return ConsoleRunner(
            self.root_dir,
            adb_serial=str(device["adb_serial"]),
            avd_name=str(device["avd_name"]),
            proxy_port=int(device["proxy_port"]),
            web_port=int(device["web_port"]),
            frida_port=int(device["frida_port"]),
            mitm_password=self.mitm_password,
            capture_instance=str(device["device_id"]),
            allow_non_retained=True,
            runtime_dir=self.runtime_dir,
        )

    def emulator_port(self) -> str:
        match = re.fullmatch(r"emulator-(\d+)", self.adb_serial)
        return match.group(1) if match else ""

    def _env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "ADB_SERIAL": self.adb_serial,
                "ANDROID_CAPTURE_AVD": self.avd_name,
                "EMULATOR_PORT": self.emulator_port(),
                "EMULATOR_LAUNCH_MODE": env.get("EMULATOR_LAUNCH_MODE", "background"),
                "PROXY_PORT": str(self.proxy_port),
                "WEB_PORT": str(self.web_port),
                "FRIDA_PORT": str(self.frida_port),
                "FRIDA_HOST": f"127.0.0.1:{self.frida_port}",
                "CAPTURE_INSTANCE": self.capture_instance,
                "CAPTURE_RUNTIME_DIR": str(self.runtime_dir),
                "RUNTIME_DIR": str(self.runtime_dir),
                "MITMWEB_PASSWORD": self.mitm_password,
                "PATH": (
                    f"{self.root_dir}/.venv-console/bin:"
                    f"{Path.home()}/.local/bin:"
                    f"{Path.home()}/Library/Python/3.12/bin:"
                    f"{Path.home()}/Library/Python/3.11/bin:"
                    f"{Path.home()}/Library/Python/3.10/bin:"
                    f"{Path.home()}/Library/Python/3.9/bin:"
                    f"{Path.home()}/Library/Android/sdk/platform-tools:"
                    f"{Path.home()}/Library/Android/sdk/emulator:"
                    f"{Path.home()}/Library/Android/sdk/cmdline-tools/latest/bin:"
                    "/opt/homebrew/bin:/usr/local/bin:"
                )
                + env.get("PATH", ""),
            }
        )
        if extra:
            env.update(extra)
        return env

    def run(self, args: List[str], *, timeout: int = 30, env: Optional[Dict[str, str]] = None) -> CommandResult:
        self.reject_destructive_command(args)
        proc = subprocess.run(
            args,
            cwd=self.root_dir,
            env=self._env(env),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)

    def reject_destructive_command(self, args: List[str]) -> None:
        lowered = [Path(part).name.lower() if index == 0 else part.lower() for index, part in enumerate(args)]
        compact = " ".join(lowered)
        for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
            if all(token in compact for token in pattern):
                raise ValueError(
                    "refusing destructive Android command that can destroy the retained emulator login state: "
                    + " ".join(args)
                )

    def retained_target_check(self) -> Dict[str, Any]:
        if self.allow_non_retained:
            detail = f"serial={self.adb_serial} avd={self.avd_name}"
            return health_check_item(
                "retained_emulator",
                True,
                detail,
                "设备池配置的 Android 模拟器。",
                "",
            )
        ok = self.adb_serial == RETAINED_ADB_SERIAL and self.avd_name == RETAINED_AVD_NAME
        detail = f"serial={self.adb_serial} avd={self.avd_name}"
        return health_check_item(
            "retained_emulator",
            ok,
            detail,
            "只允许使用保留登录态的 Android 模拟器。",
            f"请使用 {RETAINED_AVD_NAME} / {RETAINED_ADB_SERIAL}，不要切换、wipe 或新建临时模拟器。",
        )

    def adb(self, args: List[str], *, timeout: int = 20) -> CommandResult:
        return self.run([str(self.adb_bin), "-s", self.adb_serial, *args], timeout=timeout)

    def emulator_status(self) -> Dict[str, Any]:
        process = self.run(["pgrep", "-af", f"emulator.*-avd {self.avd_name}"], timeout=10)
        devices = self.run([str(self.adb_bin), "devices"], timeout=10)
        adb_online = bool(re.search(rf"^{re.escape(self.adb_serial)}\s+device$", devices.stdout, re.M))

        current_avd = ""
        boot_completed = False
        unlocked = False
        foreground = ""
        android_proxy = ""
        if adb_online:
            current_avd_result = self.adb(["emu", "avd", "name"], timeout=10)
            if current_avd_result.ok:
                current_avd_lines = [
                    line.strip()
                    for line in current_avd_result.stdout.replace("\r", "").splitlines()
                    if line.strip() and line.strip() != "OK"
                ]
                current_avd = current_avd_lines[0] if current_avd_lines else ""

            boot = self.adb(["shell", "getprop", "sys.boot_completed"], timeout=10)
            boot_completed = boot.ok and boot.stdout.strip().replace("\r", "") == "1"

            user = self.adb(["shell", "dumpsys", "user"], timeout=15)
            unlocked = user.ok and "RUNNING_UNLOCKED" in user.stdout

            proxy = self.adb(["shell", "settings", "get", "global", "http_proxy"], timeout=10)
            android_proxy = proxy.stdout.strip().replace("\r", "") if proxy.ok else ""

            window = self.adb(["shell", "dumpsys", "window"], timeout=15)
            if window.ok:
                for line in window.stdout.replace("\r", "").splitlines():
                    if "mCurrentFocus" in line or "topResumedActivity" in line:
                        foreground = line.strip()
                        break

        process_lines = [line.strip() for line in process.stdout.splitlines() if line.strip()] if process.ok else []
        return {
            "avd_name": self.avd_name,
            "adb_serial": self.adb_serial,
            "process_running": bool(process_lines),
            "process": process_lines[0] if process_lines else "",
            "adb_online": adb_online,
            "current_avd": current_avd,
            "is_retained_avd": current_avd == self.avd_name if current_avd else False,
            "boot_completed": boot_completed,
            "unlocked": unlocked,
            "android_proxy": android_proxy,
            "foreground": foreground,
            "log_file": str(self.runtime_dir / f"emulator-{self.avd_name}.log"),
            "devices": devices.stdout.strip(),
        }

    def start_emulator(self) -> CommandResult:
        retained_check = self.retained_target_check()
        if not retained_check["ok"]:
            return CommandResult(1, "", retained_check["fix"])
        return self.run([str(self.scripts_dir / "start_play_emulator.sh"), self.avd_name], timeout=30)

    def stop_emulator(self) -> CommandResult:
        return self.adb(["emu", "kill"], timeout=20)

    def capture_status_text(self) -> str:
        result = self.run([str(self.scripts_dir / "ai_capture_status.sh")], timeout=20)
        return result.text

    def capture_status(self) -> Dict[str, str]:
        return parse_capture_status(self.capture_status_text())

    def stop_capture(self) -> CommandResult:
        return self.run([str(self.scripts_dir / "ai_capture_stop.sh")], timeout=45)

    def clear_android_proxy(self) -> CommandResult:
        return self.adb(["shell", "settings", "delete", "global", "http_proxy"], timeout=20)

    def set_android_proxy(self, proxy: str) -> CommandResult:
        proxy = proxy.strip()
        if not proxy:
            return self.clear_android_proxy()
        return self.adb(["shell", "settings", "put", "global", "http_proxy", proxy], timeout=20)

    def network_state(self) -> Dict[str, Any]:
        return build_device_network_state(self.emulator_status())

    def enter_capture_network(self) -> Dict[str, Any]:
        result = self.clear_android_proxy()
        return {"ok": result.ok, "stdout": result.stdout, "stderr": result.stderr, "network": self.network_state()}

    def enter_maintenance_network(self, proxy: str) -> Dict[str, Any]:
        result = self.set_android_proxy(proxy)
        return {"ok": result.ok, "stdout": result.stdout, "stderr": result.stderr, "network": self.network_state()}

    def env_check(self) -> Dict[str, Any]:
        env = self._env()

        def command_item(name: str, command: str, fix: str) -> Dict[str, Any]:
            path = shutil.which(command, path=env.get("PATH"))
            return health_check_item(
                name,
                bool(path),
                path or "not found",
                f"{command} 可用。" if path else f"{command} 未安装或不在 PATH。",
                "" if path else fix,
            )

        sdk_root = Path(env.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_SDK_ROOT") or Path.home() / "Library/Android/sdk")
        checks = [
            command_item("python3", "python3", "brew install python@3.12"),
            command_item("node", "node", "brew install node"),
            command_item("npm", "npm", "brew install node"),
            command_item("adb", "adb", "安装 Android SDK platform-tools，并确认 adb 在 PATH 中。"),
            command_item("emulator", "emulator", "安装 Android SDK emulator，并确认 emulator 在 PATH 中。"),
            command_item("sdkmanager", "sdkmanager", "安装 Android command line tools。"),
            command_item("avdmanager", "avdmanager", "安装 Android command line tools。"),
            command_item("mitmweb", "mitmweb", "brew install mitmproxy"),
            command_item("frida", "frida", "python3 -m pip install frida-tools"),
            command_item("frida-ps", "frida-ps", "python3 -m pip install frida-tools"),
            command_item("screen", "screen", "brew install screen"),
            command_item("xz", "xz", "brew install xz"),
        ]
        checks.append(
            health_check_item(
                "android_sdk",
                sdk_root.exists(),
                str(sdk_root),
                "Android SDK 目录存在。" if sdk_root.exists() else "Android SDK 目录不存在。",
                "" if sdk_root.exists() else "安装 Android SDK，并设置 ANDROID_SDK_ROOT。",
            )
        )
        return {"ok": all(item["ok"] for item in checks), "checks": checks}

    def prepare_frida_server(self) -> Dict[str, Any]:
        emulator = self.emulator_status()
        if not emulator.get("adb_online"):
            return {
                "ok": False,
                "stdout": "",
                "stderr": "adb unavailable",
                "frida": {"ok": False, "detail": "adb unavailable"},
            }
        result = self.run(
            [str(self.scripts_dir / "start_frida_server.sh")],
            timeout=120,
            env={"FORWARD_PORT": str(self.frida_port), "CAPTURE_INSTANCE": self.capture_instance},
        )
        frida_ok, frida_detail = self.frida_server_status(device_ok=True)
        return {
            "ok": result.ok and frida_ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "frida": {"ok": frida_ok, "detail": frida_detail},
        }

    def start_capture(
        self,
        *,
        package_name: str,
        activity: str,
        mode: str,
        outdir: str,
        interval: float = 1.0,
    ) -> CommandResult:
        args = [
            str(self.scripts_dir / "ai_capture.sh"),
            "android",
            "--mode",
            mode,
            "--package",
            package_name,
            "--serial",
            self.adb_serial,
            "--no-open-ui",
            "--interval",
            str(interval),
        ]
        if activity:
            args.extend(["--activity", activity])
        return self.run(args, timeout=90, env={"OUTDIR": outdir})

    def normalize_activity_component(self, package_name: str, activity: str) -> str:
        activity = activity.strip()
        if not activity:
            return ""
        if "/" in activity:
            return activity
        if activity.startswith("."):
            return f"{package_name}/{activity}"
        return f"{package_name}/{activity}"

    def launch_app(self, *, package_name: str, activity: str = "") -> CommandResult:
        health = self.health_check(package_name=package_name, mode="system", activity=activity)
        if not health["ok"]:
            return CommandResult(1, "", "app launch health check failed: " + str(health))

        component = self.normalize_activity_component(package_name, activity or health.get("resolved_activity", ""))
        if component:
            return self.adb(["shell", "am", "start", "-W", "-n", component], timeout=30)
        return self.adb(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"], timeout=30)

    def resolve_activity(self, package_name: str) -> str:
        result = self.adb(["shell", "cmd", "package", "resolve-activity", "--brief", package_name], timeout=15)
        if not result.ok:
            return ""
        lines = [line.strip().replace("\r", "") for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return ""
        candidate = lines[-1]
        return "" if candidate == "No activity found" else candidate

    @staticmethod
    def parse_apk_badging(badging: str) -> Dict[str, str]:
        package_line = next((line for line in badging.splitlines() if line.startswith("package:")), "")
        result = {"package_name": "", "version_code": "", "version_name": ""}
        for key, output_key in [
            ("name", "package_name"),
            ("versionCode", "version_code"),
            ("versionName", "version_name"),
        ]:
            match = re.search(rf"{re.escape(key)}='([^']*)'", package_line)
            if match:
                result[output_key] = match.group(1)
        return result

    def aapt_bin(self) -> str:
        candidates = [
            shutil.which("aapt"),
            str(Path.home() / "Library/Android/sdk/build-tools/36.1.0/aapt"),
            str(Path.home() / "Library/Android/sdk/build-tools/35.0.0/aapt"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return "aapt"

    def inspect_apk(self, apk_path: str | Path) -> Dict[str, str]:
        result = self.run([self.aapt_bin(), "dump", "badging", str(apk_path)], timeout=30)
        if not result.ok:
            return {"package_name": "", "version_code": "", "version_name": "", "error": result.text}
        info = self.parse_apk_badging(result.stdout)
        info["error"] = ""
        return info

    def package_info(self, package_name: str) -> Dict[str, str]:
        result = self.adb(["shell", "dumpsys", "package", package_name], timeout=30)
        if not result.ok:
            return {"package_name": package_name, "installed": False, "error": result.text}
        text = result.stdout.replace("\r", "")
        installed = f"Package [{package_name}]" in text
        version_code = ""
        version_name = ""
        last_update_time = ""
        installer_package = ""
        signature_hint = ""

        match = re.search(r"^\s*versionCode=([^\s]+)", text, re.M)
        if match:
            version_code = match.group(1)
        match = re.search(r"^\s*versionName=(.*)$", text, re.M)
        if match:
            version_name = match.group(1).strip()
        match = re.search(r"^\s*lastUpdateTime=(.*)$", text, re.M)
        if match:
            last_update_time = match.group(1).strip()
        match = re.search(r"^\s*installerPackageName=(.*)$", text, re.M)
        if match:
            installer_package = match.group(1).strip()
        match = re.search(r"signatures:\[([^\]]*)\]", text)
        if match:
            signature_hint = match.group(1).strip()

        return {
            "package_name": package_name,
            "installed": installed,
            "version_code": version_code,
            "version_name": version_name,
            "last_update_time": last_update_time,
            "installer_package": installer_package,
            "signature_hint": signature_hint,
            "activity": self.resolve_activity(package_name),
            "error": "" if installed else result.text[-500:],
        }

    def install_apks(self, apk_paths: List[str | Path]) -> CommandResult:
        ordered = [str(path) for path in apk_paths]
        ordered.sort(key=lambda path: (Path(path).name != "base.apk", Path(path).name))
        if len(ordered) == 1:
            return self.adb(["install", "-r", ordered[0]], timeout=240)
        return self.adb(["install-multiple", "-r", *ordered], timeout=300)

    @staticmethod
    def account_text_has_google_login(text: str) -> bool:
        normalized = text.replace("\r", "")
        patterns = [
            r"Account\s*\{[^}]*type=com\.google\b",
            r"\btype=com\.google\b[^\n]*\bname=",
            r"\bname=[^\n@]+@[^\n,}]+[^\n]*\btype=com\.google\b",
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[^\n]*\bcom\.google\b",
            r"\bcom\.google\b[^\n]*[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+",
        ]
        return any(re.search(pattern, normalized, re.I) for pattern in patterns)

    @staticmethod
    def redact_account_text(text: str) -> str:
        return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[redacted-email]", text.replace("\r", ""))

    def google_state(self, *, device_ok: bool = True) -> Dict[str, Any]:
        if not device_ok:
            return {
                "ok": False,
                "state": "adb_unavailable",
                "play_store_installed": False,
                "google_account_present": False,
                "detail": "adb unavailable",
                "message": "adb unavailable",
                "user_message": "模拟器未在线，无法检查 Google 登录状态。",
                "fix": "请先启动模拟器并等待 adb 在线。",
            }

        play_store = self.adb(["shell", "pm", "path", "com.android.vending"], timeout=15)
        play_store_installed = play_store.ok and bool(play_store.stdout.strip())
        if not play_store_installed:
            detail = play_store.text[-500:] or "com.android.vending not found"
            return {
                "ok": False,
                "state": "missing_play_store",
                "play_store_installed": False,
                "google_account_present": False,
                "detail": detail,
                "message": "missing Google Play",
                "user_message": "当前模拟器缺少 Google Play，不能作为服务器抓包设备。",
                "fix": "请使用 Google Play AVD 重建该设备，不要使用普通 AOSP 或仅 Google APIs 镜像。",
            }

        account_outputs: List[str] = []
        account = self.adb(["shell", "dumpsys", "account"], timeout=15)
        if account.text:
            account_outputs.append(account.text)
        if not self.account_text_has_google_login("\n".join(account_outputs)):
            fallback = self.adb(["shell", "cmd", "account", "list"], timeout=15)
            if fallback.text:
                account_outputs.append(fallback.text)

        combined_accounts = "\n".join(account_outputs)
        google_account_present = self.account_text_has_google_login(combined_accounts)
        detail = self.redact_account_text(combined_accounts)[:1000]
        if not google_account_present:
            return {
                "ok": False,
                "state": "not_logged_in",
                "play_store_installed": True,
                "google_account_present": False,
                "detail": detail or "no Google account found",
                "message": "Google account missing",
                "user_message": "请先在模拟器内登录 Google 账号。",
                "fix": "点击“去登录 Google”，在模拟器内完成登录后刷新状态。",
            }

        return {
            "ok": True,
            "state": "ok",
            "play_store_installed": True,
            "google_account_present": True,
            "detail": detail,
            "message": "Google Play available and Google account logged in",
            "user_message": "Google Play 可用，且已登录 Google 账号。",
            "fix": "",
        }

    def open_google_login(self) -> Dict[str, Any]:
        state = self.google_state()
        if state.get("play_store_installed"):
            result = self.adb(["shell", "monkey", "-p", "com.android.vending", "-c", "android.intent.category.LAUNCHER", "1"], timeout=30)
            if result.ok:
                return {"ok": True, "stdout": result.stdout, "stderr": result.stderr, "google_state": state}

        result = self.adb(["shell", "am", "start", "-a", "android.settings.ADD_ACCOUNT_SETTINGS"], timeout=30)
        return {"ok": result.ok, "stdout": result.stdout, "stderr": result.stderr, "google_state": state}

    def scan_installed_apps(self, query: str = "", limit: int = 200) -> List[Dict[str, str]]:
        result = self.adb(["shell", "pm", "list", "packages", "-3"], timeout=30)
        if not result.ok:
            return []
        query_l = query.lower().strip()
        packages = []
        for line in result.stdout.splitlines():
            package = line.replace("package:", "").strip().replace("\r", "")
            if not package:
                continue
            if query_l and query_l not in package.lower():
                continue
            packages.append(package)
        packages = sorted(packages)[:limit]
        apps = []
        for package in packages:
            apps.append({"package_name": package, "activity": self.resolve_activity(package)})
        return apps

    def frida_server_status(self, *, device_ok: bool) -> tuple[bool, str]:
        if not device_ok:
            return False, "adb unavailable"

        proc = self.adb(["shell", "pidof", "frida-server"], timeout=10)
        proc_detail = proc.stdout.strip().replace("\r", "") or proc.stderr.strip().replace("\r", "")
        process = self.adb(["shell", "ps", "-A"], timeout=10)
        process_line = ""
        process_user = ""
        if process.ok:
            for line in process.stdout.replace("\r", "").splitlines():
                if "frida-server" in line:
                    process_line = line.strip()
                    process_user = process_line.split()[0] if process_line.split() else ""
                    break

        forward = self.run([str(self.adb_bin), "-s", self.adb_serial, "forward", "--list"], timeout=10)
        forward_detail = ""
        if forward.ok:
            expected = f"{self.adb_serial} tcp:{self.frida_port} tcp:27042"
            forward_lines = [line.strip() for line in forward.stdout.splitlines() if line.strip()]
            forward_detail = next((line for line in forward_lines if line.strip() == expected), "")

        reachable = self.run(["frida-ps", "-H", f"127.0.0.1:{self.frida_port}"], timeout=10)
        if reachable.ok and "PID" in reachable.stdout:
            if process_user == "shell":
                return (
                    False,
                    "frida-ps reachable but frida-server is running as shell; "
                    f"process={process_line}; grant Shell root in Magisk and restart Frida",
                )
            details = [f"frida-ps reachable on 127.0.0.1:{self.frida_port}"]
            if proc_detail:
                details.append(f"pid={proc_detail}")
            if process_line:
                details.append(f"process={process_line}")
            if forward_detail:
                details.append(f"forward={forward_detail}")
            return True, "; ".join(details)

        detail_parts = [
            f"pidof={proc_detail or 'not found'}",
            f"forward={forward_detail or 'missing'}",
            f"frida-ps={(reachable.text or 'empty')[-500:]}",
        ]
        return False, "; ".join(detail_parts)

    def health_check(self, *, package_name: str, mode: str, activity: str = "") -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []

        retained_check = self.retained_target_check()
        checks.append(retained_check)
        if not retained_check["ok"]:
            return {"ok": False, "checks": checks, "resolved_activity": ""}

        devices = self.run([str(self.adb_bin), "devices"], timeout=10)
        device_ok = bool(re.search(rf"^{re.escape(self.adb_serial)}\s+device$", devices.stdout, re.M))
        checks.append(
            health_check_item(
                "adb_device",
                device_ok,
                self.adb_serial if device_ok else devices.text,
                "保留模拟器未在线。",
                f"启动 {RETAINED_AVD_NAME}，并确认 adb serial 是 {RETAINED_ADB_SERIAL}。",
            )
        )

        unlocked = False
        user = self.adb(["shell", "dumpsys", "user"], timeout=15) if device_ok else CommandResult(1, "", "adb unavailable")
        if user.ok:
            unlocked = "RUNNING_UNLOCKED" in user.stdout
        checks.append(
            health_check_item(
                "android_unlocked",
                unlocked,
                "RUNNING_UNLOCKED" if unlocked else user.text[-500:],
                "模拟器未解锁。",
                "请先在模拟器里手动解锁，再回到控制台启动抓包。",
            )
        )

        google = self.google_state(device_ok=device_ok)
        checks.append(
            health_check_item(
                "google_login",
                bool(google.get("ok")),
                google.get("detail") or google.get("state", ""),
                google.get("user_message", "Google 登录状态不可用。"),
                google.get("fix", ""),
            )
        )

        package = self.adb(["shell", "pm", "path", package_name], timeout=15) if device_ok else CommandResult(1, "", "adb unavailable")
        package_exists = package.ok and bool(package.stdout.strip())
        activity = activity.strip() or (self.resolve_activity(package_name) if device_ok else "")
        checks.append(
            health_check_item(
                "package_activity",
                bool(activity) and package_exists,
                activity if package_exists else f"cannot find {package_name}: {package.text}",
                "目标应用不存在或无法解析启动 Activity。",
                "请确认应用已安装，包名正确；如果自动解析失败，请在应用库中填写 Activity。",
            )
        )

        if mode == "flutter-socks":
            frida_running, frida_detail = self.frida_server_status(device_ok=device_ok)
            checks.append(
                health_check_item(
                    "frida_server",
                    frida_running,
                    frida_detail,
                    "Frida server 未运行，无法启动 flutter-socks 抓包。",
                    "运行 ./scripts/start_frida_server.sh 后再启动抓包。",
                )
            )

        proxy_status = self.run(["lsof", f"-iTCP:{self.proxy_port}", "-sTCP:LISTEN", "-n", "-P"], timeout=10)
        web_status = self.run(["lsof", f"-iTCP:{self.web_port}", "-sTCP:LISTEN", "-n", "-P"], timeout=10)
        checks.append(health_check_item("proxy_port", True, "listening" if proxy_status.ok else "free", "代理端口可用。"))
        checks.append(health_check_item("web_port", True, "listening" if web_status.ok else "free", "mitmweb 端口可用。"))

        return {"ok": all(check["ok"] for check in checks), "checks": checks, "resolved_activity": activity}

    def make_outdir(self, app_name: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", app_name).strip("-") or "capture"
        label = time.strftime("%Y%m%d-%H%M%S")
        return self.runtime_dir / "captures" / f"web-{label}-{safe}"
