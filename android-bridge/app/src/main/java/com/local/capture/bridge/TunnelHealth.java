package com.local.capture.bridge;

final class TunnelHealth {
    static String phase(boolean up, long handshake, long now) {
        if (!up) return "stopped";
        if (handshake <= 0 || handshake > now) return "connecting";
        return now - handshake <= 180000 ? "connected" : "disconnected";
    }
}
