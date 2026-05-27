function tryParseJson(text) {
  if (!text || typeof text !== "string") return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function firstFailedCheck(payload) {
  const checks = payload?.detail?.health?.checks || payload?.health?.checks || [];
  return checks.find((check) => check && check.ok === false) || null;
}

function payloadMessage(payload) {
  return payload?.detail?.message || payload?.message || "";
}

function compactSummary(payload, fallback) {
  const failed = firstFailedCheck(payload);
  if (failed?.user_message) return failed.user_message;
  if (failed?.fix) return failed.fix;
  if (payload?.detail === "another capture session is active; stop or cleanup first") {
    return "当前已有抓包任务运行中。如需重新开始，请先停止抓包。";
  }
  if (payload?.detail === "dirty capture process state; run cleanup first") {
    return "检测到抓包进程残留，请先执行一键清理脏状态。";
  }
  if (payloadMessage(payload) === "health check failed") return "启动前健康检查未通过，请展开查看具体原因。";
  if (payloadMessage(payload)) return payloadMessage(payload);
  return fallback || "操作失败，请查看详细诊断。";
}

function errorDetail(error, payload) {
  if (payload) return JSON.stringify(payload, null, 2);
  return error?.message || String(error);
}

export function formatActionPending(label) {
  return {
    kind: "pending",
    title: `${label}中`,
    summary: "正在执行，请稍候。",
    detail: "",
  };
}

export function formatActionSuccess(label) {
  return {
    kind: "success",
    title: `${label}完成`,
    summary: "操作已完成。",
    detail: "",
  };
}

export function formatActionError(label, error) {
  const payload = error?.payload || tryParseJson(error?.message);
  return {
    kind: "error",
    title: `${label}失败`,
    summary: compactSummary(payload, error?.message || String(error)),
    detail: errorDetail(error, payload),
  };
}

export function actionMessageAutoDismissMs(message) {
  if (!message || message.kind === "pending") return 0;
  return 3500;
}
