#!/usr/bin/env bash
set -euo pipefail

ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
export ANDROID_SDK_ROOT

if [[ -z "${JAVA_HOME:-}" ]]; then
  for candidate in \
    /opt/homebrew/opt/openjdk@21 \
    /opt/homebrew/opt/openjdk@17 \
    /opt/homebrew/opt/openjdk \
    /Library/Java/JavaVirtualMachines/*/Contents/Home; do
    if [[ -x "$candidate/bin/java" ]]; then
      export JAVA_HOME="$candidate"
      break
    fi
  done
fi

export PATH="${JAVA_HOME:+$JAVA_HOME/bin:}$HOME/.local/bin:$HOME/Library/Python/3.12/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.10/bin:$HOME/Library/Python/3.9/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:/opt/homebrew/bin:/usr/local/bin:$PATH"

SYSTEM_IMAGE="${SYSTEM_IMAGE:-system-images;android-36;google_apis_playstore;arm64-v8a}"
DEVICE_PROFILE="${DEVICE_PROFILE:-pixel_6}"
AVDS=(Capture_AVD_01 Capture_AVD_02 Capture_AVD_03)

command -v sdkmanager >/dev/null 2>&1 || { echo "sdkmanager not found; install Android command line tools first" >&2; exit 1; }
command -v avdmanager >/dev/null 2>&1 || { echo "avdmanager not found; install Android command line tools first" >&2; exit 1; }

yes | sdkmanager --licenses >/dev/null || true
sdkmanager "platform-tools" "emulator" "$SYSTEM_IMAGE"

existing="$(emulator -list-avds 2>/dev/null || true)"
for avd in "${AVDS[@]}"; do
  if grep -qx "$avd" <<<"$existing"; then
    echo "exists: $avd"
    continue
  fi
  echo "creating: $avd"
  echo "no" | avdmanager create avd --force --name "$avd" --package "$SYSTEM_IMAGE" --device "$DEVICE_PROFILE"
done

echo "AVD 创建完成。下一步启动 Web 页面，在初始化向导中逐台登录 Google。"
