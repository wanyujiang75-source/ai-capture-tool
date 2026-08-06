import assert from "node:assert/strict";
import { test } from "node:test";

import {
  consolePrimaryActions,
  setupPrimaryAction,
  setupSecondaryActions,
} from "../src/uiActions.js";

test("keeps the console primary actions focused on capture work", () => {
  assert.deepEqual(consolePrimaryActions({ captureRunning: false, selectedDevice: { device_id: "device-1" } }), [
    "auto_capture",
    "preview",
  ]);

  assert.deepEqual(consolePrimaryActions({ captureRunning: true, selectedDevice: { device_id: "device-1" } }), [
    "auto_capture",
    "preview",
    "stop_capture",
  ]);
});

test("reduces setup actions to one next action plus rare secondary actions", () => {
  assert.deepEqual(setupPrimaryAction({ nextAction: { key: "frida" }, hasApp: true }), {
    key: "prepare_frida",
    label: "启动 Frida",
  });

  assert.deepEqual(setupPrimaryAction({ nextAction: { key: "smoke" }, hasApp: true }), {
    key: "validate_capture",
    label: "启动抓包测试",
  });

  assert.deepEqual(setupPrimaryAction({ nextAction: { key: "app" }, hasApp: false }), {
    key: "upload",
    label: "上传应用",
  });
});

test("only shows setup secondary actions when they are currently useful", () => {
  assert.deepEqual(setupSecondaryActions({
    selectedDevice: { emulator: { adb_online: false } },
    googleRequired: false,
  }), []);

  assert.deepEqual(setupSecondaryActions({
    selectedDevice: { emulator: { adb_online: true } },
    googleRequired: true,
    googleOk: false,
  }), ["preview", "google_login"]);

  assert.deepEqual(setupSecondaryActions({
    selectedDevice: { emulator: { adb_online: true } },
    googleRequired: true,
    googleOk: true,
  }), ["preview"]);
});
