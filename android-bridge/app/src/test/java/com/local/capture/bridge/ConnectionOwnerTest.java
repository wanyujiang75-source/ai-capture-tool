package com.local.capture.bridge;

import static org.junit.Assert.*;
import org.junit.Test;

public class ConnectionOwnerTest {
    @Test public void authenticationMatchesPythonAndBindsDirectionAndTuple() throws Exception {
        String message = "00000000000000000000000000000000\n10.0.0.2\n45678\n1.2.3.4\n443";
        assertEquals("5ed90ecfabde62eb1e41de1cfa6459c53145825fe93fe288e33c9b1ea67d4478",
                ConnectionOwner.proof("secret", "query\n" + message));
        assertNotEquals(ConnectionOwner.proof("secret", "query\n" + message),
                ConnectionOwner.proof("secret", "reply\n" + message + "\ntarget"));
        assertNotEquals(ConnectionOwner.proof("secret", "reply\n" + message + "\nlogin"),
                ConnectionOwner.proof("secret", "reply\n" + message + "\ntarget"));
    }

    @Test public void classifiesOnlyDistinctKnownAppUids() {
        assertEquals("target", ConnectionOwner.classify(10200, 10200, 10201));
        assertEquals("login", ConnectionOwner.classify(10201, 10200, 10201));
        assertEquals("unknown", ConnectionOwner.classify(-1, 10200, 10201));
        assertEquals("unknown", ConnectionOwner.classify(1000, 10200, 10201));
        assertEquals("unknown", ConnectionOwner.classify(10202, 10200, 10201));
        assertEquals("unknown", ConnectionOwner.classify(10200, 10200, 10200));
    }
}
