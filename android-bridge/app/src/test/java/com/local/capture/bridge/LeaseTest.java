package com.local.capture.bridge;

import static org.junit.Assert.*;
import org.junit.Test;

public class LeaseTest {
    @Test public void doesNotExtendForRepeatedHeartbeat() {
        Lease lease = new Lease(0);
        assertTrue(lease.renew("a", 1000));
        assertTrue(lease.renew("a", 19000));
        assertFalse(lease.renew("a", 22000));
    }
    @Test public void durationIsBoundedEvenWithFreshHeartbeat() {
        Lease lease = new Lease(0);
        for (long now = 0; now < 900000; now += 1000) assertTrue(lease.renew("a" + now, now));
        assertFalse(lease.renew("last", 900000));
    }
    @Test public void emptyLeaseDoesNotStartOrExtendTunnel() {
        assertFalse(new Lease(0).renew("", 0));
    }
    @Test public void staleOrFutureFileCannotStartANewTunnel() {
        assertTrue(Lease.freshFile(10000, 15000));
        assertFalse(Lease.freshFile(10000, 30000));
        assertFalse(Lease.freshFile(30000, 10000));
    }
}
