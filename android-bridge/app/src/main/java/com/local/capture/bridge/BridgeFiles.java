package com.local.capture.bridge;

import android.content.Context;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;

final class BridgeFiles {
    static String lease(Context context) throws Exception {
        File file = new File(context.getFilesDir(), "lease");
        if (new File(context.getFilesDir(), "stop").exists() || !Lease.freshFile(file.lastModified(), System.currentTimeMillis())) return "";
        return read(context, "lease");
    }
    static String read(Context context, String name) throws Exception {
        File file = new File(context.getFilesDir(), name);
        if (file.length() > 16384) throw new IllegalArgumentException("Oversized configuration");
        return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
    }
    static void state(Context context, String phase) {
        try {
            File file = new File(context.getFilesDir(), "status.tmp");
            Files.write(file.toPath(), ("{\"phase\":\"" + phase + "\"}").getBytes(StandardCharsets.UTF_8));
            Files.move(file.toPath(), new File(context.getFilesDir(), "status.json").toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception ignored) { }
    }
}
