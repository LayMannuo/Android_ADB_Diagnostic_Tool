package com.signway.remotecontrol;

import java.util.ArrayList;
import java.util.List;

public final class NecPattern {
    static final int START_HIGH = 9000;
    static final int START_LOW = 4500;
    static final int BIT_HIGH = 560;
    static final int BIT_LOW_0 = 565;
    static final int BIT_LOW_1 = 1690;
    static final int END_HIGH = 560;
    static final int END_LOW = 20000;

    private NecPattern() {
    }

    public static int[] buildPattern(int addressHigh, int addressLow, int command) {
        List<Integer> values = new ArrayList<>();
        values.add(START_HIGH);
        values.add(START_LOW);
        appendByte(values, addressHigh);
        appendByte(values, addressLow);
        appendByte(values, command);
        appendByte(values, ~command);
        values.add(END_HIGH);
        values.add(END_LOW);

        int[] pattern = new int[values.size()];
        for (int i = 0; i < values.size(); i++) {
            pattern[i] = values.get(i);
        }
        return pattern;
    }

    private static void appendByte(List<Integer> values, int value) {
        int byteValue = value & 0xFF;
        for (int bit = 0; bit < 8; bit++) {
            values.add(BIT_HIGH);
            if (((byteValue >> bit) & 0x01) == 0) {
                values.add(BIT_LOW_0);
            } else {
                values.add(BIT_LOW_1);
            }
        }
    }
}
