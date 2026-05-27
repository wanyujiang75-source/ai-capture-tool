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

export function applyFlowClearMarker(flows, marker) {
  if (!marker?.hiddenIds?.length) {
    return flows;
  }
  const hiddenIds = new Set(marker.hiddenIds.map(String));
  return (flows || []).filter((flow) => !hiddenIds.has(flowIdentity(flow)));
}
