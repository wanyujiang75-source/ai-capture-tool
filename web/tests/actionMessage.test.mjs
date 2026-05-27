import test from "node:test";
import assert from "node:assert/strict";

import {
  actionMessageAutoDismissMs,
  formatActionError,
  formatActionSuccess,
  formatActionPending,
} from "../src/actionMessage.js";

test("formats health-check JSON errors as compact user messages with collapsible detail", () => {
  const raw = JSON.stringify({
    detail: {
      message: "health check failed",
      health: {
        ok: false,
        checks: [
          {
            name: "frida_server",
            ok: false,
            user_message: "Frida server 未运行，无法启动 flutter-socks 抓包。",
            fix: "运行 ./scripts/start_frida_server.sh 后再启动抓包。",
          },
        ],
      },
    },
  });

  const message = formatActionError("启动抓包", new Error(raw));

  assert.equal(message.kind, "error");
  assert.equal(message.title, "启动抓包失败");
  assert.equal(message.summary, "Frida server 未运行，无法启动 flutter-socks 抓包。");
  assert.match(message.detail, /health check failed/);
  assert.ok(message.detail.length > message.summary.length);
});

test("formats simple action states consistently", () => {
  assert.deepEqual(formatActionPending("打开应用"), {
    kind: "pending",
    title: "打开应用中",
    summary: "正在执行，请稍候。",
    detail: "",
  });
  assert.deepEqual(formatActionSuccess("打开应用"), {
    kind: "success",
    title: "打开应用完成",
    summary: "操作已完成。",
    detail: "",
  });
});

test("auto dismisses completed action messages after a short visible delay", () => {
  assert.equal(actionMessageAutoDismissMs({ kind: "success" }), 3500);
  assert.equal(actionMessageAutoDismissMs({ kind: "error" }), 3500);
  assert.equal(actionMessageAutoDismissMs({ kind: "pending" }), 0);
  assert.equal(actionMessageAutoDismissMs(null), 0);
});
