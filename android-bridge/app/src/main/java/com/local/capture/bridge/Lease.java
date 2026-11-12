package com.local.capture.bridge;

final class Lease {
    private final long started;
    private long renewed;
    private String token = "";
    Lease(long now) { started = renewed = now; }
    static boolean freshFile(long modified, long now) { return modified > 0 && now >= modified && now - modified < 20000; }
    boolean renew(String value, long now) {
        if (value.isEmpty() || now - started >= 900000 || now - renewed >= 20000) return false;
        if (!value.equals(token)) { token = value; renewed = now; }
        return true;
    }
}
