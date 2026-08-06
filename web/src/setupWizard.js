export const SETUP_STEP_COPY = {
  env: ["服务环境检查", "检查 Python、Node、Android SDK、mitmproxy、Frida 等依赖。"],
  devices: ["设备发现", "发现至少一台在线 Android 设备。"],
  emulator: ["设备就绪", "确认设备在线、Android 系统启动完成，并完成解锁。"],
  google: ["Google 状态", "按目标 App 需要确认 Google Play 或账号状态。"],
  frida: ["Frida 准入", "启动 Frida server 并确认可连接。"],
  app: ["上传或选择 App", "上传 APK 或选择已有应用。"],
  smoke: ["抓包冒烟测试", "完成一次抓包校验并捕获接口。"],
  complete: ["完成初始化", "进入主控制台。"],
};

export const SETUP_STAGE_DEFS = [
  { key: "env", label: "环境", stepKeys: ["env", "devices"] },
  { key: "device", label: "设备", stepKeys: ["emulator", "google"] },
  { key: "frida", label: "Frida", stepKeys: ["frida"] },
  { key: "capture", label: "抓包", stepKeys: ["app", "smoke", "complete"] },
];

export function shouldShowSetupWizard(setup, forcedOpen = false, consoleAvailable = false) {
  if (forcedOpen) return true;
  if (consoleAvailable) return false;
  return !setup?.completed;
}

export function shouldAutoCompleteSetup(setup) {
  return Boolean(setup?.ready_to_complete && !setup?.completed);
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

export function setupStageSummary(setup) {
  const steps = setup?.steps || [];
  const currentKey = setup?.current_step || "env";
  return SETUP_STAGE_DEFS.map((stage) => {
    const stageSteps = steps.filter((step) => stage.stepKeys.includes(step.key));
    const ok = stageSteps.length > 0 && stageSteps.every((step) => step.ok);
    const current = stage.stepKeys.includes(currentKey);
    const failed = stageSteps.find((step) => !step.ok);
    return {
      ...stage,
      ok,
      current,
      description: ok ? "已通过" : failed?.label || "待检测",
    };
  });
}

export function setupNextAction(setup, selectedDevice, apps = []) {
  const current = setupCurrentStep(setup);
  const emulator = selectedDevice?.emulator || {};
  const googleRequired = Boolean(setup?.google_login_required);
  const googleOk = Boolean(selectedDevice?.google_state?.ok) || !googleRequired;

  if (setup?.completed) {
    return {
      key: "done",
      title: "初始化已完成",
      description: "可以进入控制台选择设备、添加应用并开始抓包。",
      primary: "进入控制台",
    };
  }

  if (current.key === "env" || current.key === "devices") {
    return {
      key: current.key,
      title: "自动检测运行环境",
      description: "系统会自动检查依赖、端口和已连接设备；失败项只在完整诊断中展示。",
      primary: "自动检测",
    };
  }

  if (current.key === "emulator") {
    const title = emulator.adb_online ? "解锁设备" : "连接设备";
    const description = emulator.adb_online
      ? "设备已在线，请在画面中完成解锁，页面会自动识别。"
      : "连接 Android 真机或启动本机模拟器后，等待系统完成启动并解锁。";
    return { key: "emulator", title, description, primary: emulator.adb_online ? "查看设备" : "启动设备" };
  }

  if (current.key === "google" && !googleOk) {
    return {
      key: "google",
      title: "完成 Google 登录",
      description: selectedDevice?.google_state?.user_message || "当前设备需要登录 Google 后才能继续。",
      primary: "去登录 Google",
    };
  }

  if (current.key === "frida") {
    return {
      key: "frida",
      title: "启动 Frida",
      description: "Frida 用于把 App 的 Flutter/native 网络连接导流到抓包代理。",
      primary: "启动 Frida",
    };
  }

  if (current.key === "app") {
    return {
      key: "app",
      title: apps.length ? "选择或更新应用" : "上传应用安装包",
      description: apps.length ? `已存在 ${apps.length} 个应用，可直接选择或上传新版本。` : "上传生产包或测试包 APK 后才能进行抓包验证。",
      primary: apps.length ? "继续校验" : "上传 APK",
    };
  }

  if (current.key === "smoke") {
    return {
      key: "smoke",
      title: "进行抓包验证",
      description: "启动短时间抓包后，操作 App 并捕获到业务接口即可完成初始化。",
      primary: "启动抓包测试",
    };
  }

  return {
    key: "complete",
    title: "完成初始化",
    description: "至少一台设备已通过准入，并且已有一次抓包校验记录。",
    primary: "完成初始化",
  };
}

export function setupCaptureValidationAction({
  hasApp,
  validationPassed,
  captureRunning,
  loading,
  selectedApp,
}) {
  if (!hasApp || validationPassed) {
    return {
      visible: false,
      disabled: true,
      label: "启动抓包测试",
      title: "",
    };
  }

  if (captureRunning) {
    return {
      visible: true,
      disabled: true,
      label: "抓包运行中",
      title: "当前已有抓包任务运行中；如需重新校验，请先停止抓包。",
    };
  }

  return {
    visible: true,
    disabled: Boolean(loading || !selectedApp),
    label: "启动抓包测试",
    title: "",
  };
}
