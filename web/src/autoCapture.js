export function deviceBootReady(device) {
  return Boolean(device?.emulator?.adb_online && device?.emulator?.boot_completed);
}

export function deviceUnlocked(device) {
  return Boolean(deviceBootReady(device) && device?.emulator?.unlocked);
}

export function autoCaptureRequirement({ app, device, captureRunning = false, googleRequired = false }) {
  if (captureRunning) {
    return { ok: false, stage: "capture_running", label: "抓包已在运行", action: "stop_or_view" };
  }
  if (!app) {
    return { ok: false, stage: "select_app", label: "请选择应用", action: "select_app" };
  }
  if ((app.platform || "android") !== "android") {
    return { ok: false, stage: "unsupported_platform", label: "当前仅支持 Android", action: "select_android_app" };
  }
  if (!device) {
    return { ok: true, stage: "discover_device", label: "需要发现设备", action: "discover_device" };
  }
  if (!deviceBootReady(device)) {
    return { ok: true, stage: "start_device", label: "需要启动设备", action: "start_device" };
  }
  if (!deviceUnlocked(device)) {
    return { ok: true, stage: "unlock_device", label: "等待解锁设备", action: "wait_unlock" };
  }
  if (googleRequired && !device?.google_state?.ok) {
    return { ok: true, stage: "google_login", label: "需要 Google 登录", action: "open_google_login" };
  }
  if (!device?.frida_state?.ok) {
    return { ok: true, stage: "prepare_frida", label: "需要启动 Frida", action: "prepare_frida" };
  }
  return { ok: true, stage: "ready", label: "可启动抓包", action: "start_capture" };
}

export function autoCaptureButtonLabel({ loading = false, captureRunning = false }) {
  if (captureRunning) return "抓包运行中";
  if (loading) return "自动处理中";
  return "一键开始抓包";
}
