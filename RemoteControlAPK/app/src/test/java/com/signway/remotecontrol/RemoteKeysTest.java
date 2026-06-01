package com.signway.remotecontrol;

import org.junit.Test;

import java.util.HashSet;
import java.util.Set;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class RemoteKeysTest {
    @Test
    public void representativeKeyCodesMatchReference() {
        assertEquals(0x45, RemoteKeys.POWER.code);
        assertEquals(0x18, RemoteKeys.PLAY_PAUSE.code);
        assertEquals(0x01, RemoteKeys.AV.code);
    }

    @Test
    public void allKeyIdsAreUniqueAndCodesAreBytes() {
        Set<String> ids = new HashSet<>();
        for (RemoteKey key : RemoteKeys.ALL) {
            assertTrue("duplicate id " + key.id, ids.add(key.id));
            assertTrue(key.id + " code below range", key.code >= 0x00);
            assertTrue(key.id + " code above range", key.code <= 0xFF);
        }
    }
}
