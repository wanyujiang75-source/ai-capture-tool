package com.local.capture.bridge;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.ApplicationInfo;
import android.os.Build;
import com.wireguard.config.Config;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

/** Reject UID sharing before consent and again immediately before creating a tunnel. */
final class TargetIsolation {
    static final String LOGIN = "com.google.android.gms";
    static boolean isAllowed(int uid, String sharedUserId) {
        return uid >= 10000 && uid < 100000 && sharedUserId == null;
    }

    static Config checkedConfig(Context context) throws Exception {
        Config config = Config.parse(new ByteArrayInputStream(
            BridgeFiles.read(context, "tunnel.conf").getBytes(StandardCharsets.UTF_8)));
        java.util.Set<String> packages = config.getInterface().getIncludedApplications();
        boolean login = packages.contains(LOGIN);
        if (packages.size() != (login ? 2 : 1)
                || !config.getInterface().getExcludedApplications().isEmpty()) throw new IllegalArgumentException();
        String target = packages.stream().filter(value -> !value.equals(LOGIN)).findFirst().orElseThrow();
        PackageInfo info = context.getPackageManager().getPackageInfo(target, 0);
        if (info.applicationInfo == null || !isAllowed(info.applicationInfo.uid, info.sharedUserId)) {
            throw new IllegalArgumentException();
        }
        if (login) {
            PackageInfo google = context.getPackageManager().getPackageInfo(LOGIN, 0);
            if (Build.VERSION.SDK_INT < 29 || google.applicationInfo == null
                    || (google.applicationInfo.flags & (ApplicationInfo.FLAG_SYSTEM | ApplicationInfo.FLAG_UPDATED_SYSTEM_APP)) == 0
                    || google.applicationInfo.uid == info.applicationInfo.uid
                    || google.applicationInfo.uid < 10000 || google.applicationInfo.uid >= 100000) throw new IllegalArgumentException();
            // GMS and Google Services Framework may intentionally share a UID.
            // That entire system-signed group is opaque, never eligible for capture.
            String[] shared = context.getPackageManager().getPackagesForUid(google.applicationInfo.uid);
            if (shared == null) throw new IllegalArgumentException();
            for (String name : shared) {
                ApplicationInfo member = context.getPackageManager().getApplicationInfo(name, 0);
                if ((member.flags & (ApplicationInfo.FLAG_SYSTEM | ApplicationInfo.FLAG_UPDATED_SYSTEM_APP)) == 0
                        || context.getPackageManager().checkSignatures(LOGIN, name) != android.content.pm.PackageManager.SIGNATURE_MATCH) {
                    throw new IllegalArgumentException();
                }
            }
            if (!BridgeFiles.read(context, "routing-token").trim().matches("[a-f0-9]{64}")) throw new IllegalArgumentException();
        }
        return config;
    }
}
