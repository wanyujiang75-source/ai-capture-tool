export function formatDurationMs(value) {
  if (value === null || value === undefined || value === "") return "-";
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "-";
  if (numberValue > 0 && numberValue < 1) return "<1ms";
  if (numberValue < 1000) return `${Math.round(numberValue)}ms`;
  if (numberValue < 10000) return `${(numberValue / 1000).toFixed(2)}s`;
  return `${(numberValue / 1000).toFixed(1)}s`;
}

export function compactTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ");
  const pad = (part, size = 2) => String(part).padStart(size, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function flowTimingSummary(flow) {
  const total = flow?.total_duration_ms;
  if (total !== null && total !== undefined && total !== "") return `总 ${formatDurationMs(total)}`;
  const wait = flow?.wait_duration_ms;
  if (wait !== null && wait !== undefined && wait !== "") return `等待 ${formatDurationMs(wait)}`;
  return "-";
}

export function flowTimingInfo(flow) {
  return {
    request_started_at: flow?.request_started_at || "",
    request_finished_at: flow?.request_finished_at || "",
    response_started_at: flow?.response_started_at || "",
    response_finished_at: flow?.response_finished_at || "",
    request_duration: formatDurationMs(flow?.request_duration_ms),
    wait_duration: formatDurationMs(flow?.wait_duration_ms),
    response_duration: formatDurationMs(flow?.response_duration_ms),
    total_duration: formatDurationMs(flow?.total_duration_ms),
  };
}

export function flowTimingRows(flow) {
  const info = flowTimingInfo(flow);
  return [
    ["请求开始", compactTimestamp(info.request_started_at)],
    ["请求结束", compactTimestamp(info.request_finished_at)],
    ["响应开始", compactTimestamp(info.response_started_at)],
    ["响应结束", compactTimestamp(info.response_finished_at)],
    ["请求耗时", info.request_duration],
    ["等待响应", info.wait_duration],
    ["响应耗时", info.response_duration],
    ["总耗时", info.total_duration],
  ];
}
