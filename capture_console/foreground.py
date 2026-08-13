import re
from typing import Any, Dict, Optional


SYSTEM_UI_PACKAGES = {
    "com.android.launcher",
    "com.android.launcher3",
    "com.android.systemui",
    "com.google.android.apps.nexuslauncher",
}
COMPONENT_PATTERN = re.compile(
    r"(?P<package>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)"
    r"/(?P<activity>\.?[A-Za-z0-9_.$]+)"
)


def empty_foreground_state(state: str = "no_target") -> Dict[str, str]:
    return {
        "state": state,
        "package_name": "",
        "activity": "",
        "component": "",
    }


def parse_foreground_component(output: str) -> Dict[str, str]:
    if not output:
        return empty_foreground_state()

    priority_lines = []
    for marker in ("topResumedActivity", "mResumedActivity", "mCurrentFocus"):
        priority_lines.extend(line for line in output.splitlines() if marker in line)
    candidates = priority_lines or output.splitlines()

    for line in candidates:
        match = COMPONENT_PATTERN.search(line)
        if not match:
            continue
        package_name = match.group("package")
        if package_name in SYSTEM_UI_PACKAGES:
            return empty_foreground_state()
        component = match.group(0)
        return {
            "state": "ready",
            "package_name": package_name,
            "activity": component,
            "component": component,
        }
    return empty_foreground_state()


def capture_state(
    *,
    app: Dict[str, Any],
    active_session: Optional[Dict[str, Any]],
    flow_count: int,
    readiness_state: str = "ready",
) -> str:
    if readiness_state == "blocked":
        return "blocked"
    if not active_session:
        return "ready"
    if active_session.get("package_name") != app.get("package_name"):
        return "blocked"
    return "capturable" if flow_count > 0 else "waiting_traffic"
