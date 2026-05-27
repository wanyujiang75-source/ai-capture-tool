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

test("missing clear marker leaves flows unchanged", () => {
  const flows = [{ id: "flow-1" }];

  assert.equal(applyFlowClearMarker(flows, null), flows);
});
