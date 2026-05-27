export const SETUP_STEP_COPY = {
  env: ["服务环境检查", "检查 Python、Node、Android SDK、mitmproxy、Frida 等依赖。"],
  devices: ["设备池检查", "检查至少一台启用设备。"],
  emulator: ["启动并解锁模拟器", "启动设备、等待 Android 系统完成启动，并在模拟器内解锁屏幕。"],
  google: ["Google 登录", "在模拟器内登录 Google 账号。"],
  frida: ["Frida 准入", "启动 Frida server 并确认可连接。"],
  app: ["上传或选择 App", "上传 APK 或选择已有应用。"],
  smoke: ["抓包冒烟测试", "完成一次抓包校验并捕获接口。"],
  complete: ["完成初始化", "进入主控制台。"],
};

export function shouldShowSetupWizard(setup, forcedOpen = false) {
  if (forcedOpen) return true;
  return !setup?.completed;
}

export function setupCurrentStep(setup) {
  const key = setup?.current_step || "env";
  const [label, description] = SETUP_STEP_COPY[key] || SETUP_STEP_COPY.env;
  return { key, label, description };
}

export function setupDeviceSummary(devices) {
  const total = (devices || []).length;
  const ready = (devices || []).filter((device) => device.ready).length;
  return {
    total,
    ready,
    label: `设备 ${ready}/${total} 可抓包`,
    ok: ready > 0,
  };
}
