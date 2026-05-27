import assert from "node:assert/strict";
import { test } from "node:test";

import { buildUploadInstallPath } from "../src/uploadPackage.js";

test("builds generic package upload path with selected environment and filename", () => {
  const path = buildUploadInstallPath("test", "Poke Hub 测试.apk");

  assert.equal(path, "/api/apps/install?environment=test&filename=Poke+Hub+%E6%B5%8B%E8%AF%95.apk");
});

test("defaults invalid upload environment to production", () => {
  const path = buildUploadInstallPath("beta", "pokehub.apk");

  assert.equal(path, "/api/apps/install?environment=production&filename=pokehub.apk");
});

test("includes selected capture device in package upload path", () => {
  const path = buildUploadInstallPath("production", "pokehub.apk", "device-2");

  assert.equal(path, "/api/apps/install?environment=production&filename=pokehub.apk&device_id=device-2");
});
