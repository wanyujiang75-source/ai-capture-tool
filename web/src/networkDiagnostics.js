export function preflightSummary(preflight) {
  const ports = preflight?.ports || [];
  const blocking = ports.filter((item) => !item.ok);
  return {
    ok: blocking.length === 0,
    total: ports.length,
    blocking: blocking.length,
    label: blocking.length ? `端口冲突 ${blocking.length}` : "端口正常",
  };
}

export function networkModeLabel(network) {
  if (!network?.adb_online || !network?.boot_completed) return "模拟器未就绪";
  if (network.mode === "maintenance_proxy") return `维护代理 ${network.android_proxy || ""}`.trim();
  return "抓包直连";
}
