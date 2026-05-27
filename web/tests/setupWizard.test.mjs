import assert from "node:assert/strict";
import { test } from "node:test";

import {
  setupCurrentStep,
  setupDeviceSummary,
  shouldShowSetupWizard,
} from "../src/setupWizard.js";

test("shows setup wizard until initialization is complete", () => {
  assert.equal(shouldShowSetupWizard({ completed: false }, false), true);
  assert.equal(shouldShowSetupWizard({ completed: true }, false), false);
  assert.equal(shouldShowSetupWizard({ completed: true }, true), true);
});

test("returns readable current setup step copy", () => {
  assert.deepEqual(setupCurrentStep({ current_step: "google" }), {
    key: "google",
    label: "Google 登录",
    description: "在模拟器内登录 Google 账号。",
  });
});

test("summarizes ready setup devices", () => {
  assert.deepEqual(setupDeviceSummary([
    { ready: true },
    { ready: false },
    { ready: true },
  ]), {
    total: 3,
    ready: 2,
    label: "设备 2/3 可抓包",
    ok: true,
  });
});
