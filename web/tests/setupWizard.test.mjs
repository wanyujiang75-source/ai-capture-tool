import assert from "node:assert/strict";
import { test } from "node:test";

import {
  setupCurrentStep,
  setupDeviceSummary,
  setupNextAction,
  setupStageSummary,
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

test("summarizes setup steps into four compact stages", () => {
  const stages = setupStageSummary({
    current_step: "frida",
    steps: [
      { key: "env", label: "服务环境检查", ok: true },
      { key: "devices", label: "设备池检查", ok: true },
      { key: "emulator", label: "启动并解锁模拟器", ok: true },
      { key: "google", label: "Google 登录", ok: true },
      { key: "frida", label: "Frida 准入", ok: false },
      { key: "app", label: "上传或选择 App", ok: false },
      { key: "smoke", label: "抓包冒烟测试", ok: false },
      { key: "complete", label: "完成初始化", ok: false },
    ],
  });

  assert.deepEqual(stages.map((stage) => [stage.key, stage.ok, stage.current, stage.description]), [
    ["env", true, false, "已通过"],
    ["device", true, false, "已通过"],
    ["frida", false, true, "Frida 准入"],
    ["capture", false, false, "上传或选择 App"],
  ]);
});

test("returns focused next action for automatic setup guidance", () => {
  assert.equal(
    setupNextAction({ current_step: "emulator" }, { emulator: { adb_online: false } }, []).primary,
    "启动模拟器",
  );
  assert.equal(
    setupNextAction({ current_step: "emulator" }, { emulator: { adb_online: true } }, []).primary,
    "查看模拟器",
  );
  assert.equal(
    setupNextAction({ current_step: "smoke" }, { emulator: { adb_online: true } }, [{ id: 1 }]).primary,
    "启动抓包测试",
  );
});
