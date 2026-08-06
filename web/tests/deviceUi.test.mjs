import test from "node:test";
import assert from "node:assert/strict";

import {
  deviceInstallReady,
  deviceState,
  releaseActionHint,
  releaseActionLabel,
  residentSummary,
  selectPreferredDevice,
} from "../src/deviceUi.js";

test("labels resident devices separately from on-demand devices", () => {
  assert.deepEqual(
    deviceState({
      resident: 1,
      emulator: { adb_online: true, boot_completed: true },
      capture: { health: "idle" },
      lease_status: "idle",
      sleep_state: "awake",
    }),
    { label: "常驻在线", className: "ok" },
  );
  assert.deepEqual(
    deviceState({
      resident: 0,
      emulator: { adb_online: false, boot_completed: false },
      capture: { health: "idle" },
      lease_status: "idle",
      sleep_state: "awake",
    }),
    { label: "按需空闲", className: "neutral" },
  );
});

test("uses different release copy for resident and on-demand devices", () => {
  assert.equal(releaseActionLabel({ resident: 1 }), "结束使用");
  assert.equal(releaseActionHint({ resident: 1 }), "常驻设备会停止抓包并清理代理，但不会关闭模拟器。");
  assert.equal(releaseActionLabel({ resident: 0 }), "释放设备");
  assert.equal(releaseActionHint({ resident: 0 }), "按需设备会停止抓包并关闭模拟器以释放内存。");
});

test("summarizes resident readiness for the top bar", () => {
  const summary = residentSummary([
    { resident: 1, emulator: { adb_online: true, boot_completed: true } },
    { resident: 1, emulator: { adb_online: false, boot_completed: false } },
    { resident: 0, emulator: { adb_online: true, boot_completed: true } },
  ]);

  assert.equal(summary.label, "常驻 1/2 在线");
  assert.equal(summary.ready, false);
});

test("selects an unlocked online device when the previous selection is offline", () => {
  const devices = [
    {
      device_id: "device-1",
      emulator: { adb_online: false, boot_completed: false, unlocked: false },
    },
    {
      device_id: "device-2",
      emulator: { adb_online: true, boot_completed: true, unlocked: true },
    },
  ];

  assert.equal(deviceInstallReady(devices[1]), true);
  assert.equal(selectPreferredDevice(devices, "device-1").device_id, "device-2");
});

test("keeps the selected device when it has an active capture", () => {
  const devices = [
    {
      device_id: "device-1",
      active_session: { id: 1 },
      emulator: { adb_online: false, boot_completed: false, unlocked: false },
    },
    {
      device_id: "device-2",
      emulator: { adb_online: true, boot_completed: true, unlocked: true },
    },
  ];

  assert.equal(selectPreferredDevice(devices, "device-1").device_id, "device-1");
});
