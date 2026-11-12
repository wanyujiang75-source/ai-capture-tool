package com.local.capture.bridge;

import android.app.Activity;
import android.content.Intent;
import android.net.VpnService;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;
import android.widget.Button;
import android.widget.LinearLayout;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean permissionPending;
    private boolean cancelled;
    private final Runnable checkConsent = new Runnable() {
        @Override public void run() {
            if (!permissionPending) return;
            try {
                if (!BridgeFiles.lease(MainActivity.this).isBlank()) {
                    handler.postDelayed(this, 500);
                    return;
                }
            } catch (Exception ignored) { }
            cancelConsent();
        }
    };

    private void cancelConsent() {
        cancelled = true;
        finishActivity(1);
        permissionPending = false;
        handler.removeCallbacks(checkConsent);
        stopService(new Intent(this, BridgeService.class));
        try {
            // This token is supplied only through the helper's private USB files.
            String token = BridgeFiles.read(this, "stop");
            Files.write(new File(getFilesDir(), "stop_ack").toPath(), token.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) { }
        BridgeFiles.state(this, "cancelled");
        finishAndRemoveTask();
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (new File(getFilesDir(), "stop").exists()) { cancelConsent(); return; }
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(32, 64, 32, 32);
        TextView title = new TextView(this);
        title.setText("抓包连接助手\n\n仅转发桌面端指定的测试应用。\n临时替换当前 VPN，原节点和配置不会修改。\n结束后请确认原 VPN 已恢复。\n\nUSB 断开或电脑停止响应时，20 秒内释放临时连接。\n请保持 USB 连接并返回桌面端操作。");
        title.setTextSize(19);
        layout.addView(title);
        Button stop = new Button(this);
        stop.setText("停止临时连接");
        stop.setOnClickListener(view -> { stopService(new Intent(this, BridgeService.class)); BridgeFiles.state(this, "stopped"); });
        layout.addView(stop);
        setContentView(layout);
        if (state != null) {
            permissionPending = state.getBoolean("permissionPending");
            if (permissionPending) handler.post(checkConsent);
            return;
        }
        try {
            if (BridgeFiles.lease(this).isBlank()) return;
            // The private file is supplied over authorized USB, never from an exported Intent.
            TargetIsolation.checkedConfig(this);
            Intent permission = VpnService.prepare(this);
            if (permission != null) {
                BridgeFiles.state(this, "waiting_vpn");
                permissionPending = true;
                startActivityForResult(permission, 1);
                handler.post(checkConsent);
            } else startBridge();
        } catch (Exception exception) { BridgeFiles.state(this, "failed"); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        permissionPending = false;
        handler.removeCallbacks(checkConsent);
        if (cancelled) return;
        if (request == 1 && result == RESULT_OK) startBridge();
        else BridgeFiles.state(this, "denied");
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (new File(getFilesDir(), "stop").exists()) cancelConsent();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("permissionPending", permissionPending);
        super.onSaveInstanceState(state);
    }
    @Override protected void onDestroy() {
        handler.removeCallbacks(checkConsent);
        if (isFinishing() && permissionPending) {
            finishActivity(1);
            BridgeFiles.state(this, "cancelled");
        }
        super.onDestroy();
    }
    private void startBridge() {
        try {
            if (BridgeFiles.lease(this).isBlank()) { cancelConsent(); return; }
            startForegroundService(new Intent(this, BridgeService.class));
        } catch (Exception exception) { BridgeFiles.state(this, "failed"); }
    }
}
