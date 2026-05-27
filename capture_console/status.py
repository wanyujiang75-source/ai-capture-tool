from __future__ import annotations

from typing import Dict


def _after_prefix(line: str, prefix: str) -> str:
    return line[len(prefix) :].strip()


def parse_capture_status(text: str) -> Dict[str, str]:
    status = {
        "web": "",
        "outdir": "",
        "mode": "unknown",
        "package": "",
        "proxy": "unknown",
        "exporter": "missing",
        "frida_hook": "missing",
        "android_serial": "",
        "android_proxy": "",
        "foreground": "",
        "health": "stopped",
    }
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("web:"):
            status["web"] = _after_prefix(line, "web:")
        elif line.startswith("outdir:"):
            status["outdir"] = _after_prefix(line, "outdir:")
        elif line.startswith("mode:"):
            status["mode"] = _after_prefix(line, "mode:")
        elif line.startswith("package:"):
            status["package"] = _after_prefix(line, "package:")
        elif line.startswith("proxy:"):
            status["proxy"] = _after_prefix(line, "proxy:")
        elif line.startswith("exporter:"):
            value = _after_prefix(line, "exporter:")
            if value.startswith("running"):
                status["exporter"] = "running"
            elif value.startswith("stopped"):
                status["exporter"] = "stopped"
            else:
                status["exporter"] = "missing"
        elif line.startswith("frida hook:"):
            value = _after_prefix(line, "frida hook:")
            if value.startswith("running"):
                status["frida_hook"] = "running"
            elif value.startswith("stopped"):
                status["frida_hook"] = "stopped"
            else:
                status["frida_hook"] = "missing"
        elif line.startswith("android serial:"):
            status["android_serial"] = _after_prefix(line, "android serial:")
        elif line.startswith("android proxy:"):
            status["android_proxy"] = _after_prefix(line, "android proxy:")
        elif line.startswith("foreground:"):
            status["foreground"] = _after_prefix(line, "foreground:")

    exporter = status["exporter"]
    frida = status["frida_hook"]
    mode = status["mode"]
    if exporter == "running" and (mode != "flutter-socks" or frida == "running"):
        status["health"] = "running"
    elif exporter == "running" or frida == "running":
        status["health"] = "dirty"
    elif "listening" in status["proxy"]:
        status["health"] = "idle"
    return status

