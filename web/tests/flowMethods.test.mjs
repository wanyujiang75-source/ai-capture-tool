import assert from "node:assert/strict";
import { test } from "node:test";

import { matchesMethod, methodFilterOptions, normalizeFlowMethod } from "../src/flowMethods.js";

test("normalizes empty methods for display and matching", () => {
  assert.equal(normalizeFlowMethod(" post "), "POST");
  assert.equal(normalizeFlowMethod(""), "UNKNOWN");
});

test("builds clickable method filters ordered by common HTTP methods", () => {
  const options = methodFilterOptions([
    { method: "GET" },
    { method: "POST" },
    { method: "POST" },
    { method: "PATCH" },
    { method: "RPC" },
  ]);

  assert.deepEqual(options, [
    { value: "all", label: "全部", count: 5 },
    { value: "POST", label: "POST", count: 2 },
    { value: "GET", label: "GET", count: 1 },
    { value: "PATCH", label: "PATCH", count: 1 },
    { value: "RPC", label: "RPC", count: 1 },
  ]);
});

test("matches selected request method", () => {
  assert.equal(matchesMethod({ method: "POST" }, "all"), true);
  assert.equal(matchesMethod({ method: "POST" }, "POST"), true);
  assert.equal(matchesMethod({ method: "GET" }, "POST"), false);
});
