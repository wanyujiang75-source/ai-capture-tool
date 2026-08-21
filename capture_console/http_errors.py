from __future__ import annotations

import json
from typing import Any, Dict


def structured_http_error_body(*, path: str, status_code: int, detail: Any) -> Dict[str, Any]:
    detail_fields = dict(detail) if isinstance(detail, dict) else {}
    if isinstance(detail, str):
        technical_detail = detail
    else:
        technical_detail = str(
            detail_fields.get("technical_detail")
            or detail_fields.get("message")
            or json.dumps(detail_fields, ensure_ascii=False, default=str)
        )

    normalized = technical_detail.lower()
    state = str(
        detail_fields.get("state")
        or (detail_fields.get("google_state") or {}).get("state")
        or ""
    )
    code = ""
    title = ""
    user_message = ""
    recovery_action = ""

    if "another capture session" in normalized or "active capture exists" in normalized:
        code = "capture_active"
        title = "其他应用正在抓包"
        user_message = "当前模拟器正在抓包，请停止后重试。"
        recovery_action = "停止抓包"
    elif "dirty capture process" in normalized:
        code = "capture_cleanup_required"
        title = "抓包环境需要清理"
        user_message = "上次抓包未完全结束，请在运行检查中清理后重试。"
        recovery_action = "打开运行检查"
    elif "ports are occupied" in normalized:
        ports = sorted(
            {
                int(item["port"])
                for item in detail_fields.get("blocking_ports", [])
                if isinstance(item, dict) and str(item.get("port", "")).isdigit()
            }
        )
        port_text = "、".join(str(port) for port in ports)
        code = "capture_port_conflict"
        title = "抓包端口被占用"
        if port_text:
            user_message = f"抓包端口 {port_text} 正被其他程序使用，工具不会自动结束该程序。"
        else:
            user_message = "抓包端口正被其他程序使用，工具不会自动结束该程序。"
        recovery_action = "关闭占用端口的程序或更换端口"
    elif "emulator is not ready for package install" in normalized:
        code = "emulator_not_ready"
        title = "模拟器尚未启动"
        user_message = "模拟器未启动，暂时无法安装应用。"
        recovery_action = "启动模拟器"
    elif "emulator is locked" in normalized:
        code = "emulator_locked"
        title = "模拟器尚未解锁"
        user_message = "请先解锁模拟器，再安装应用。"
        recovery_action = "显示模拟器"
    elif "google login required" in normalized and state == "missing_play_store":
        code = "google_play_missing"
        title = "缺少 Google Play"
        user_message = "当前模拟器不支持 Google 登录，请先准备 Google Play 模拟器。"
        recovery_action = "准备 Google Play 模拟器"
    elif "google login required" in normalized and state == "not_logged_in":
        code = "google_login_required"
        title = "尚未登录 Google"
        user_message = "请先在模拟器中登录 Google 账号，再继续当前操作。"
        recovery_action = "打开 Google 登录"
    elif "google login required" in normalized:
        code = "google_state_unavailable"
        title = "无法确认 Google 登录状态"
        user_message = "请先检查模拟器连接和 Google 登录状态。"
        recovery_action = "打开运行检查"
    elif "jenkins" in path:
        code = "jenkins_unavailable"
        title = "无法连接 Jenkins"
        user_message = "无法连接 Jenkins，请确认已连接公司网络后重试。"
        recovery_action = "检查公司网络"
    elif "install_failed_update_incompatible" in normalized or "signature" in normalized:
        code = "signature_conflict"
        title = "应用签名不一致"
        user_message = "新安装包与现有版本签名不一致。为保护应用数据，工具不会自动卸载旧版本。"
        recovery_action = "选择签名一致的 APK"
    elif "/logcat" in path:
        code = "log_connection_failed"
        title = "日志连接中断"
        user_message = "日志连接中断，请检查模拟器连接后重试。"
        recovery_action = "检查模拟器连接"
    elif "no capture mode could start" in normalized:
        code = "capture_start_failed"
        title = "抓包启动失败"
        user_message = "抓包组件未能启动，请打开运行检查后重试。"
        recovery_action = "打开运行检查"
    elif status_code == 404:
        code = "not_found"
        title = "内容不可用"
        user_message = "请求的内容不存在或已失效，请刷新后重试。"
        recovery_action = "刷新页面"
    elif status_code == 409:
        code = "operation_conflict"
        title = "当前操作暂时无法完成"
        user_message = "当前操作与正在进行的任务冲突，请结束当前任务后重试。"
        recovery_action = "重新检查"
    elif status_code >= 500:
        code = "service_unavailable"
        title = "本机服务暂时不可用"
        user_message = "请打开运行检查，确认本机服务正常后重试。"
        recovery_action = "打开运行检查"
    else:
        code = "operation_failed"
        title = "操作未完成"
        user_message = "请稍后重试；如果问题持续，请打开运行检查。"
        recovery_action = "打开运行检查"

    if detail_fields:
        code = str(detail_fields.get("code") or code)
        title = str(detail_fields.get("title") or title)
        user_message = str(detail_fields.get("user_message") or user_message)
        recovery_action = str(
            detail_fields.get("recovery_action")
            or detail_fields.get("fix")
            or recovery_action
        )

    enriched_fields = {
        **detail_fields,
        "code": code,
        "title": title,
        "user_message": user_message,
        "recovery_action": recovery_action,
        "technical_detail": technical_detail,
    }
    return {
        "detail": enriched_fields if isinstance(detail, dict) else detail,
        "code": code,
        "title": title,
        "user_message": user_message,
        "recovery_action": recovery_action,
        "technical_detail": technical_detail,
    }
