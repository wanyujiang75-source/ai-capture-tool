from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _find_check(checks: Iterable[Dict[str, Any]], names: set[str]) -> Optional[Dict[str, Any]]:
    return next((check for check in checks if check.get("name") in names), None)


def _required_state(checks: Iterable[Dict[str, Any]], names: set[str]) -> str:
    matched = [check for check in checks if check.get("name") in names]
    if not matched:
        return "warn"
    return "ok" if all(check.get("ok") for check in matched) else "fail"


def _check(name: str, label: str, state: str, summary: str, detail: str = "") -> Dict[str, str]:
    return {
        "name": name,
        "label": label,
        "state": state,
        "summary": summary,
        "detail": detail,
    }


def _health_summary(checks: List[Dict[str, Any]], names: set[str], ok_summary: str, fail_summary: str) -> tuple[str, str]:
    failed = next((check for check in checks if check.get("name") in names and not check.get("ok")), None)
    if failed:
        return failed.get("user_message") or fail_summary, failed.get("detail") or ""
    details = [str(check.get("detail") or "") for check in checks if check.get("name") in names and check.get("detail")]
    return ok_summary, "；".join(details)


def _capture_stack_state(
    *,
    app: Dict[str, Any],
    capture_status: Dict[str, Any],
    active_session: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    if not active_session:
        return _check("capture_stack", "抓包链路", "warn", "抓包尚未启动。", "点击“启动抓包”后会自动复查。")

    if active_session.get("package_name") != app.get("package_name"):
        return _check(
            "capture_stack",
            "抓包链路",
            "warn",
            "当前 active capture 不是所选应用。",
            f"active={active_session.get('package_name') or '-'} selected={app.get('package_name') or '-'}",
        )

    exporter_ok = capture_status.get("exporter") == "running"
    proxy_ok = "listening" in str(capture_status.get("proxy") or "")
    frida_ok = app.get("default_mode") != "flutter-socks" or capture_status.get("frida_hook") == "running"
    if exporter_ok and proxy_ok and frida_ok:
        return _check("capture_stack", "抓包链路", "ok", "抓包链路运行中。", str(capture_status))

    return _check("capture_stack", "抓包链路", "fail", "抓包进程或代理未完全运行。", str(capture_status))


def _active_target_capture(app: Dict[str, Any], active_session: Optional[Dict[str, Any]]) -> bool:
    return bool(active_session and active_session.get("package_name") == app.get("package_name"))


def _traffic_state(
    *,
    app: Dict[str, Any],
    active_session: Optional[Dict[str, Any]],
    flow_count: int,
) -> Dict[str, str]:
    if not active_session or active_session.get("package_name") != app.get("package_name"):
        return _check("target_traffic", "接口捕获", "warn", "启动抓包并操作 App 后校验。")
    if flow_count > 0:
        return _check("target_traffic", "接口捕获", "ok", f"已捕获 {flow_count} 条候选接口。")
    return _check("target_traffic", "接口捕获", "warn", "等待目标 App 产生可捕获请求。")


def build_readiness_report(
    *,
    app: Dict[str, Any],
    health: Dict[str, Any],
    capture_status: Dict[str, Any],
    active_session: Optional[Dict[str, Any]],
    flow_count: int,
    foreground: str,
) -> Dict[str, Any]:
    health_checks = list(health.get("checks") or [])

    emulator_summary, emulator_detail = _health_summary(
        health_checks,
        {"retained_emulator", "adb_device", "android_unlocked"},
        "模拟器在线并已解锁。",
        "模拟器未就绪。",
    )
    app_summary, app_detail = _health_summary(
        health_checks,
        {"package_activity"},
        "应用已安装，Activity 可启动。",
        "应用未安装或 Activity 不可用。",
    )

    package_name = app.get("package_name") or ""
    foreground_match = bool(package_name and package_name in (foreground or ""))
    foreground_state = "ok" if foreground_match else "warn"
    foreground_summary = "目标应用在前台。" if foreground_match else "目标应用当前不在前台。"

    checks = [
        _check("emulator", "模拟器", _required_state(health_checks, {"retained_emulator", "adb_device", "android_unlocked"}), emulator_summary, emulator_detail),
        _check("app", "应用", _required_state(health_checks, {"package_activity"}), app_summary, app_detail),
        _check("foreground", "前台应用", foreground_state, foreground_summary, foreground or "-"),
    ]

    google_check = _find_check(health_checks, {"google_login"})
    if google_check:
        checks.append(
            _check(
                "google_login",
                "Google 登录",
                "ok" if google_check.get("ok") else "fail",
                "Google Play 可用，且已登录账号。" if google_check.get("ok") else google_check.get("user_message", "Google 登录不可用。"),
                google_check.get("detail", ""),
            )
        )

    frida_check = _find_check(health_checks, {"frida_server"})
    if frida_check:
        hook_pid_running = (
            app.get("default_mode") == "flutter-socks"
            and _active_target_capture(app, active_session)
            and capture_status.get("frida_hook") == "running"
        )
        frida_ok = bool(frida_check.get("ok"))
        if frida_ok:
            frida_summary = "Frida server 可用。"
            frida_detail = frida_check.get("detail", "")
        elif hook_pid_running:
            frida_summary = frida_check.get("user_message", "Frida server 不可用。")
            frida_detail = f"{frida_check.get('detail', '')}; hook pid is running but Frida server is unreachable"
        else:
            frida_summary = frida_check.get("user_message", "Frida server 不可用。")
            frida_detail = frida_check.get("detail", "")
        checks.append(
            _check(
                "frida",
                "Frida",
                "ok" if frida_ok else "fail",
                frida_summary,
                frida_detail,
            )
        )

    checks.append(_capture_stack_state(app=app, capture_status=capture_status, active_session=active_session))
    checks.append(_traffic_state(app=app, active_session=active_session, flow_count=flow_count))

    if any(check["state"] == "fail" for check in checks):
        state = "fail"
    elif any(check["state"] == "warn" for check in checks):
        state = "warn"
    else:
        state = "ok"

    return {
        "state": state,
        "app_id": app.get("id"),
        "app_name": app.get("name", ""),
        "package_name": package_name,
        "mode": app.get("default_mode", "system"),
        "active_session_id": active_session.get("id") if active_session else None,
        "flow_count": flow_count,
        "checks": checks,
    }
