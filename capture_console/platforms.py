from __future__ import annotations

SUPPORTED_PLATFORMS = {"android", "ios"}
CAPTURE_SUPPORTED_PLATFORMS = {"android"}


def normalize_platform(platform: str | None) -> str:
    return (platform or "android").strip().lower()


def validate_platform(platform: str | None) -> str:
    normalized = normalize_platform(platform)
    if normalized not in SUPPORTED_PLATFORMS:
        raise ValueError("platform must be android or ios")
    return normalized


def capture_supported(platform: str | None) -> bool:
    return validate_platform(platform) in CAPTURE_SUPPORTED_PLATFORMS


def unsupported_platform_detail(platform: str | None) -> dict[str, str]:
    normalized = validate_platform(platform)
    return {
        "message": f"{normalized} capture is reserved but not implemented",
        "user_message": "当前版本只支持 Android 抓包；iOS 仅预留入口，暂未实现。",
        "platform": normalized,
    }
