import test from "node:test";
import assert from "node:assert/strict";

import {
  autoCaptureButtonLabel,
  autoCaptureRequirement,
  deviceBootReady,
  deviceUnlocked,
} from "../src/autoCapture.js";

const androidApp = { id: 1, platform: "android", name: "MelodyCraft" };
const readyDevice = {
  device_id: "device-1",
  emulator: { adb_online: true, boot_completed: true, unlocked: true },
  google_state: { ok: true },
  frida_state: { ok: true },
};

test("detects device boot and unlock readiness", () => {
  assert.equal(deviceBootReady({ emulator: { adb_online: true, boot_completed: true } }), true);
  assert.equal(deviceBootReady({ emulator: { adb_online: true, boot_completed: false } }), false);
  assert.equal(deviceUnlocked({ emulator: { adb_online: true, boot_completed: true, unlocked: true } }), true);
  assert.equal(deviceUnlocked({ emulator: { adb_online: true, boot_completed: true, unlocked: false } }), false);
});

test("requires an Android app and a selected device before auto capture", () => {
  assert.deepEqual(autoCaptureRequirement({ app: null, device: readyDevice }), {
    ok: false,
    stage: "select_app",
    label: "请选择应用",
    action: "select_app",
  });
  assert.equal(autoCaptureRequirement({ app: { platform: "ios" }, device: readyDevice }).stage, "unsupported_platform");
  assert.deepEqual(autoCaptureRequirement({ app: androidApp, device: null }), {
    ok: true,
    stage: "discover_device",
    label: "需要发现设备",
    action: "discover_device",
  });
});

test("orders auto capture preparation checks by actionable sequence", () => {
  assert.equal(autoCaptureRequirement({ app: androidApp, device: { emulator: { adb_online: false } } }).stage, "start_device");
  assert.equal(autoCaptureRequirement({
    app: androidApp,
    device: { emulator: { adb_online: true, boot_completed: true, unlocked: false } },
  }).stage, "unlock_device");
  assert.equal(autoCaptureRequirement({
    app: androidApp,
    device: { ...readyDevice, google_state: { ok: false } },
    googleRequired: true,
  }).stage, "google_login");
  assert.equal(autoCaptureRequirement({
    app: androidApp,
    device: { ...readyDevice, frida_state: { ok: false } },
  }).stage, "prepare_frida");
  assert.equal(autoCaptureRequirement({ app: androidApp, device: readyDevice }).stage, "ready");
});

test("labels auto capture button by current state", () => {
  assert.equal(autoCaptureButtonLabel({}), "一键开始抓包");
  assert.equal(autoCaptureButtonLabel({ loading: true }), "自动处理中");
  assert.equal(autoCaptureButtonLabel({ captureRunning: true }), "抓包运行中");
});
