package com.local.capture.bridge;

import android.content.Context;
import android.content.pm.PackageInfo;
import com.wireguard.config.Config;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

/** Reject UID sharing before consent and again immediately before creating a tunnel. */
final class TargetIsolation {
    static boolean isAllowed(int uid, String sharedUserId) {
        return uid >= 10000 && uid < 100000 && sharedUserId == null;
    }

    static Config checkedConfig(Context context) throws Exception {
        Config config = Config.parse(new ByteArrayInputStream(
            BridgeFiles.read(context, "tunnel.conf").getBytes(StandardCharsets.UTF_8)));
        if (config.getInterface().getIncludedApplications().size() != 1
                || !config.getInterface().getExcludedApplications().isEmpty()) throw new IllegalArgumentException();
        String target = config.getInterface().getIncludedApplications().iterator().next();
        PackageInfo info = context.getPackageManager().getPackageInfo(target, 0);
        if (info.applicationInfo == null || !isAllowed(info.applicationInfo.uid, info.sharedUserId)) {
            throw new IllegalArgumentException();
        }
        return config;
    }
}
