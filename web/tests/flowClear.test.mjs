import assert from "node:assert/strict";
import { test } from "node:test";

import { applyFlowClearMarker, createFlowClearMarker } from "../src/flowClear.js";

test("clear marker hides flows that already existed in the current session", () => {
  const marker = createFlowClearMarker([
    { id: "flow-1" },
    { id: "flow-2" },
  ]);

  assert.deepEqual(applyFlowClearMarker([
    { id: "flow-1" },
    { id: "flow-2" },
  ], marker), []);
});

test("clear marker keeps newly captured flows visible", () => {
  const marker = createFlowClearMarker([{ id: "old-flow" }]);

  assert.deepEqual(applyFlowClearMarker([
    { id: "new-flow" },
    { id: "old-flow" },
  ], marker), [{ id: "new-flow" }]);
});

test("clear marker hides flows whose request time is before the clear point", () => {
  const marker = {
    clearedAt: "2026-08-06T15:15:53+08:00",
    hiddenIds: [],
  };

  assert.deepEqual(applyFlowClearMarker([
    { id: "late-backend-flow", time: "2026-08-06T15:15:51+08:00" },
    { id: "new-flow", time: "2026-08-06T15:16:01+08:00" },
  ], marker), [{ id: "new-flow", time: "2026-08-06T15:16:01+08:00" }]);
});

test("missing clear marker leaves flows unchanged", () => {
  const flows = [{ id: "flow-1" }];

  assert.equal(applyFlowClearMarker(flows, null), flows);
});
