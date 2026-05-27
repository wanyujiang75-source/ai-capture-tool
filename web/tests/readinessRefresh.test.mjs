import test from "node:test";
import assert from "node:assert/strict";

import { scheduleDelayedReadinessRefresh } from "../src/readinessRefresh.js";

test("schedules a second readiness refresh for the launched app after 2 seconds", () => {
  const calls = [];
  const scheduled = [];

  const cancel = scheduleDelayedReadinessRefresh({
    appId: "formal-app",
    refresh: (appId) => calls.push(appId),
    schedule: (callback, delayMs) => {
      scheduled.push({ callback, delayMs });
      return 42;
    },
    clear: (timerId) => calls.push(`clear:${timerId}`),
  });

  assert.equal(scheduled.length, 1);
  assert.equal(scheduled[0].delayMs, 2000);
  scheduled[0].callback();
  assert.deepEqual(calls, ["formal-app"]);

  cancel();
  assert.deepEqual(calls, ["formal-app", "clear:42"]);
});
