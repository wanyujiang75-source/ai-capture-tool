package com.local.capture.bridge;

import android.app.*;
import android.content.Intent;
import android.os.*;
import com.wireguard.android.backend.GoBackend;
import com.wireguard.android.backend.Tunnel;
import com.wireguard.config.Config;
import java.io.File;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public final class BridgeService extends Service {
    private final ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
    private GoBackend backend;
    private Lease lease;
    private boolean started;
    private final Tunnel tunnel = new Tunnel() {
        public String getName() { return "CaptureDesktop"; }
        public void onStateChange(State state) {
            BridgeFiles.state(BridgeService.this, state == State.UP ? "connected" : "stopped");
        }
    };
    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("capture", "临时抓包连接", NotificationManager.IMPORTANCE_LOW));
        Intent open = new Intent(this, MainActivity.class);
        Notification notification = new Notification.Builder(this, "capture")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("正在转发测试应用")
            .setContentText("结束后请确认原 VPN 已恢复")
            .setContentIntent(PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE))
            .setOngoing(true).build();
        startForeground(1, notification);
        lease = new Lease(SystemClock.elapsedRealtime());
    }
    @Override public int onStartCommand(Intent intent, int flags, int id) {
        if (started) return START_NOT_STICKY;
        started = true;
        executor.execute(() -> {
            try {
                if (!lease.renew(BridgeFiles.lease(this), SystemClock.elapsedRealtime())) throw new IllegalStateException();
                Config config = TargetIsolation.checkedConfig(this);
                backend = new GoBackend(this);
                backend.setState(tunnel, Tunnel.State.UP, config);
                executor.scheduleWithFixedDelay(this::checkLease, 1, 2, TimeUnit.SECONDS);
            } catch (Exception exception) { BridgeFiles.state(this, "failed"); stopSelf(); }
        });
        return START_NOT_STICKY;
    }
    private void checkLease() {
        try {
            if (!lease.renew(BridgeFiles.lease(this), SystemClock.elapsedRealtime())
                    || backend.getState(tunnel) != Tunnel.State.UP) stopSelf();
        } catch (Exception exception) { stopSelf(); }
    }
    @Override public void onDestroy() {
        executor.execute(() -> {
            try { if (backend != null) backend.setState(tunnel, Tunnel.State.DOWN, null); }
            catch (Exception ignored) { }
            // Keep the stop marker until desktop acknowledgement prevents any
            // queued activity from reopening consent during shutdown.
            for (String name : new String[]{"tunnel.conf", "lease"}) new File(getFilesDir(), name).delete();
            BridgeFiles.state(this, "stopped");
        });
        executor.shutdown();
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
