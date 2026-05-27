export function scheduleDelayedReadinessRefresh({
  appId,
  refresh,
  delayMs = 2000,
  schedule = setTimeout,
  clear = clearTimeout,
}) {
  if (!appId || typeof refresh !== "function") {
    return () => {};
  }

  const timerId = schedule(() => {
    refresh(appId);
  }, delayMs);

  return () => clear(timerId);
}
