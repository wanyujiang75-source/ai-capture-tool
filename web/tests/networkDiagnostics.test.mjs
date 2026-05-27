import assert from "node:assert/strict";
import { test } from "node:test";

import { networkModeLabel, preflightSummary } from "../src/networkDiagnostics.js";

test("summarizes blocking port preflight results", () => {
  const summary = preflightSummary({
    ports: [
      { port: 9090, ok: true },
      { port: 9100, ok: false },
    ],
  });

  assert.deepEqual(summary, {
    ok: false,
    total: 2,
    blocking: 1,
    label: "端口冲突 1",
  });
});

test("labels emulator network mode for capture and maintenance", () => {
  assert.equal(networkModeLabel({ adb_online: false }), "模拟器未就绪");
  assert.equal(networkModeLabel({ adb_online: true, boot_completed: true, mode: "direct" }), "抓包直连");
  assert.equal(
    networkModeLabel({
      adb_online: true,
      boot_completed: true,
      mode: "maintenance_proxy",
      android_proxy: "127.0.0.1:7890",
    }),
    "维护代理 127.0.0.1:7890",
  );
});
