export function isResidentDevice(device) {
  return Boolean(Number(device?.resident || 0));
}

export function deviceState(device) {
  if (!device) return { label: "未选择", className: "warn" };
  if (device.active_session || device.capture?.health === "running") return { label: "抓包中", className: "ok" };
  if (device.sleep_state === "sleeping") return { label: "休眠", className: "warn" };
  if (device.emulator?.adb_online && device.emulator?.boot_completed) {
    return { label: isResidentDevice(device) ? "常驻在线" : "按需启动", className: "ok" };
  }
  if (device.lease_status === "leased") return { label: "已占用", className: "neutral" };
  if (isResidentDevice(device)) return { label: "常驻空闲", className: "neutral" };
  return { label: "按需空闲", className: "neutral" };
}

export function releaseActionLabel(device) {
  return isResidentDevice(device) ? "结束使用" : "释放设备";
}

export function releaseActionHint(device) {
  return isResidentDevice(device)
    ? "常驻设备会停止抓包并清理代理，但不会关闭模拟器。"
    : "按需设备会停止抓包并关闭模拟器以释放内存。";
}

export function residentSummary(devices) {
  const residentDevices = (devices || []).filter(isResidentDevice);
  const online = residentDevices.filter((device) => device.emulator?.adb_online && device.emulator?.boot_completed);
  return {
    label: `常驻 ${online.length}/${residentDevices.length} 在线`,
    ready: residentDevices.length > 0 && online.length === residentDevices.length,
  };
}

export function deviceInstallReady(device) {
  return Boolean(device?.emulator?.adb_online && device?.emulator?.boot_completed && device?.emulator?.unlocked);
}

export function deviceBootReady(device) {
  return Boolean(device?.emulator?.adb_online && device?.emulator?.boot_completed);
}

export function selectPreferredDevice(devices, previousDeviceId = "") {
  const items = devices || [];
  if (!items.length) return null;

  const previous = items.find((device) => device.device_id === previousDeviceId);
  if (previous?.active_session || previous?.capture?.health === "running") return previous;
  if (deviceInstallReady(previous)) return previous;

  const installReady = items.find(deviceInstallReady);
  if (installReady) return installReady;

  if (deviceBootReady(previous)) return previous;
  const bootReady = items.find(deviceBootReady);
  if (bootReady) return bootReady;

  return previous || items[0];
}
