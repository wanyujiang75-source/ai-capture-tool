export function flowIdentity(flow) {
  const directId = flow?.id ?? flow?.flow_id;
  if (directId !== undefined && directId !== null && directId !== "") {
    return String(directId);
  }
  return [flow?.time, flow?.method, flow?.status, flow?.url || flow?.path].filter(Boolean).join("|");
}

export function createFlowClearMarker(flows) {
  return {
    clearedAt: new Date().toISOString(),
    hiddenIds: Array.from(new Set((flows || []).map(flowIdentity).filter(Boolean))),
  };
}

function timestampMillis(value) {
  const time = Date.parse(value || "");
  return Number.isFinite(time) ? time : null;
}

export function applyFlowClearMarker(flows, marker) {
  if (!marker) {
    return flows;
  }
  const hiddenIds = new Set((marker.hiddenIds || []).map(String));
  const clearedAtMillis = timestampMillis(marker.clearedAt);
  return (flows || []).filter((flow) => {
    if (hiddenIds.has(flowIdentity(flow))) {
      return false;
    }
    const flowMillis = timestampMillis(flow?.time);
    if (clearedAtMillis !== null && flowMillis !== null && flowMillis <= clearedAtMillis) {
      return false;
    }
    return true;
  });
}
