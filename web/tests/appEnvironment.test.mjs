import assert from "node:assert/strict";
import { test } from "node:test";

import { appEnvironmentLabel, groupAppsByEnvironment } from "../src/appEnvironment.js";

test("labels production and test app environments", () => {
  assert.equal(appEnvironmentLabel("production"), "生产包");
  assert.equal(appEnvironmentLabel("test"), "测试包");
  assert.equal(appEnvironmentLabel(""), "生产包");
});

test("groups apps by environment and defaults unknown apps to production", () => {
  const apps = [
    { id: 1, name: "MelodyCraft 正式包", environment: "production" },
    { id: 8, name: "MelodyCraft 测试包", environment: "test" },
    { id: 9, name: "PokeHub" },
  ];

  const grouped = groupAppsByEnvironment(apps);

  assert.deepEqual(grouped.production.map((app) => app.id), [1, 9]);
  assert.deepEqual(grouped.test.map((app) => app.id), [8]);
});
