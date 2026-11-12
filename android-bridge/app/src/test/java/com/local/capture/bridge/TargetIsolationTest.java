package com.local.capture.bridge;

import static org.junit.Assert.*;
import org.junit.Test;

public class TargetIsolationTest {
    @Test public void onlyUnsharedPrimaryUserApplicationIsAllowed() {
        assertTrue(TargetIsolation.isAllowed(10123, null));
        assertFalse(TargetIsolation.isAllowed(10123, "com.example.shared"));
        assertFalse(TargetIsolation.isAllowed(1000, null));
        assertFalse(TargetIsolation.isAllowed(110123, null));
    }
}
