package com.signway.remotecontrol;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class NecPatternTest {
    @Test
    public void buildsNecPatternWithExpectedShape() {
        int[] pattern = NecPattern.buildPattern(0x00, 0xFF, 0x45);

        assertEquals(68, pattern.length);
        assertEquals(9000, pattern[0]);
        assertEquals(4500, pattern[1]);
        assertEquals(560, pattern[2]);
        assertEquals(565, pattern[3]);
        assertEquals(560, pattern[66]);
        assertEquals(20000, pattern[67]);
    }

    @Test
    public void encodesCommandLeastSignificantBitFirst() {
        int[] pattern = NecPattern.buildPattern(0x00, 0xFF, 0x45);
        int commandStart = 2 + 16 + 16;

        assertEquals(560, pattern[commandStart]);
        assertEquals(1690, pattern[commandStart + 1]);
        assertEquals(560, pattern[commandStart + 2]);
        assertEquals(565, pattern[commandStart + 3]);
    }
}
