import assert from "node:assert/strict";
import { test } from "node:test";

import { desktopRuntimeLabel, desktopRuntimeTitle } from "../src/desktopStatus.js";

test("labels desktop-managed backend status", () => {
  const status = { desktop: { enabled: true, runtime_dir: "/Users/me/Library/Application Support/AI抓包工具/runtime" } };

  assert.equal(desktopRuntimeLabel(status), "桌面端运行");
  assert.match(desktopRuntimeTitle(status), /Application Support/);
});

test("keeps browser mode quiet", () => {
  assert.equal(desktopRuntimeLabel({ desktop: { enabled: false } }), "");
  assert.equal(desktopRuntimeTitle({ desktop: { enabled: false } }), "");
  assert.equal(desktopRuntimeLabel(null), "");
});
