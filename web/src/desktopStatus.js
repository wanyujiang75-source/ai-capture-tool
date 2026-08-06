export function desktopRuntimeLabel(status) {
  return status?.desktop?.enabled ? "桌面端运行" : "";
}

export function desktopRuntimeTitle(status) {
  if (!status?.desktop?.enabled) return "";
  const runtimeDir = status.desktop.runtime_dir || "未知运行目录";
  return `后端由 macOS 桌面应用管理；运行目录：${runtimeDir}`;
}
