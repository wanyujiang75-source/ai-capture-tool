import test from "node:test";
import assert from "node:assert/strict";

import {
  compactTimestamp,
  flowTimingInfo,
  flowTimingRows,
  flowTimingSummary,
  formatDurationMs,
} from "../src/flowTiming.js";

test("formats request and response durations for flow rows", () => {
  assert.equal(formatDurationMs(0.5), "<1ms");
  assert.equal(formatDurationMs(280), "280ms");
  assert.equal(formatDurationMs(1250), "1.25s");
  assert.equal(formatDurationMs(null), "-");
});

test("builds compact timing summary from total duration", () => {
  assert.equal(flowTimingSummary({ total_duration_ms: 280, wait_duration_ms: 230 }), "总 280ms");
  assert.equal(flowTimingSummary({ wait_duration_ms: 230 }), "等待 230ms");
  assert.equal(flowTimingSummary({}), "-");
});

test("returns timing detail fields for request and response panels", () => {
  const info = flowTimingInfo({
    request_started_at: "2026-05-20T10:15:00.100+08:00",
    request_finished_at: "2026-05-20T10:15:00.120+08:00",
    response_started_at: "2026-05-20T10:15:00.350+08:00",
    response_finished_at: "2026-05-20T10:15:00.380+08:00",
    request_duration_ms: 20,
    wait_duration_ms: 230,
    response_duration_ms: 30,
    total_duration_ms: 280,
  });

  assert.equal(info.request_duration, "20ms");
  assert.equal(info.wait_duration, "230ms");
  assert.equal(info.response_duration, "30ms");
  assert.equal(info.total_duration, "280ms");
  assert.equal(compactTimestamp("2026-05-20T10:15:00.380+08:00"), "05-20 10:15:00");
});

test("builds per-interface timing rows for expanded details", () => {
  const rows = flowTimingRows({
    request_started_at: "2026-05-20T10:15:00.100+08:00",
    response_finished_at: "2026-05-20T10:15:00.380+08:00",
    request_duration_ms: 20,
    wait_duration_ms: 230,
    response_duration_ms: 30,
    total_duration_ms: 280,
  });

  assert.deepEqual(rows.slice(0, 2), [["请求开始", "05-20 10:15:00"], ["请求结束", "-"]]);
  assert.deepEqual(rows.slice(-4), [
    ["请求耗时", "20ms"],
    ["等待响应", "230ms"],
    ["响应耗时", "30ms"],
    ["总耗时", "280ms"],
  ]);
});
