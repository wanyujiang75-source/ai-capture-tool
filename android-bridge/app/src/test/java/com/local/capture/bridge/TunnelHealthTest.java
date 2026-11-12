package com.local.capture.bridge;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public final class TunnelHealthTest {
    @Test public void serviceUpWithoutHandshakeIsNotConnected() {
        assertEquals("connecting", TunnelHealth.phase(true, 0, 200000));
    }
    @Test public void onlyRecentRealHandshakeIsConnected() {
        assertEquals("connected", TunnelHealth.phase(true, 190000, 200000));
        assertEquals("disconnected", TunnelHealth.phase(true, 1000, 200000));
        assertEquals("connecting", TunnelHealth.phase(true, 210000, 200000));
        assertEquals("stopped", TunnelHealth.phase(false, 190000, 200000));
    }
}
