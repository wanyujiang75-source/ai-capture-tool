export function consolePrimaryActions({ captureRunning = false, selectedDevice = null } = {}) {
  const actions = ["auto_capture"];
  if (selectedDevice) actions.push("preview");
  if (captureRunning) actions.push("stop_capture");
  return actions;
}

export function autoCaptureStatusText({
  autoCaptureStep = "",
  captureRunning = false,
  loading = false,
  fallbackLabel = "",
} = {}) {
  if ((loading || captureRunning) && autoCaptureStep) return autoCaptureStep;
  return fallbackLabel;
}

export function setupPrimaryAction({ nextAction = {}, hasApp = false, selectedDevice = null } = {}) {
  switch (nextAction.key) {
    case "done":
      return { key: "close_setup", label: "进入控制台" };
    case "env":
    case "devices":
      return { key: "check", label: "自动检测" };
    case "emulator":
      return selectedDevice?.emulator?.adb_online
        ? { key: "preview", label: "查看设备" }
        : { key: "start_device", label: "启动设备" };
    case "google":
      return { key: "google_login", label: "去登录 Google" };
    case "frida":
      return { key: "prepare_frida", label: "启动 Frida" };
    case "app":
      return hasApp
        ? { key: "validate_capture", label: "启动抓包测试" }
        : { key: "upload", label: "上传应用" };
    case "smoke":
      return { key: "validate_capture", label: "启动抓包测试" };
    case "complete":
      return { key: "complete_setup", label: "完成初始化" };
    default:
      return { key: "check", label: "自动检测" };
  }
}

export function setupSecondaryActions({ selectedDevice = null, googleRequired = false, googleOk = false } = {}) {
  if (!selectedDevice?.emulator?.adb_online) return [];
  const actions = ["preview"];
  if (googleRequired && !googleOk) actions.push("google_login");
  return actions;
}
