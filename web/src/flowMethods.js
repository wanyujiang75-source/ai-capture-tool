const COMMON_METHOD_ORDER = ["POST", "GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];

export function normalizeFlowMethod(method) {
  const value = String(method || "").trim().toUpperCase();
  return value || "UNKNOWN";
}

export function methodCounts(flows) {
  return (flows || []).reduce(
    (accumulator, flow) => {
      const method = normalizeFlowMethod(flow?.method);
      accumulator.all += 1;
      accumulator.methods[method] = (accumulator.methods[method] || 0) + 1;
      return accumulator;
    },
    { all: 0, methods: {} },
  );
}

export function methodFilterOptions(flows) {
  const counts = methodCounts(flows);
  const present = Object.keys(counts.methods);
  const orderedMethods = [
    ...COMMON_METHOD_ORDER.filter((method) => present.includes(method)),
    ...present.filter((method) => !COMMON_METHOD_ORDER.includes(method)).sort(),
  ];

  return [
    { value: "all", label: "全部", count: counts.all },
    ...orderedMethods.map((method) => ({ value: method, label: method, count: counts.methods[method] || 0 })),
  ];
}

export function matchesMethod(flow, method) {
  const selected = normalizeFlowMethod(method === "all" ? "" : method);
  if (!method || method === "all") return true;
  return normalizeFlowMethod(flow?.method) === selected;
}
