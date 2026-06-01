package com.signway.remotecontrol;

import android.annotation.TargetApi;
import android.content.Context;
import android.hardware.ConsumerIrManager;
import android.os.Build;
import android.util.Log;

public final class ConsumerIrRemoteCommandSender implements RemoteCommandSender {
    private static final int CARRIER_FREQUENCY = 38000;
    private static final int USER_CODE_HIGH = 0x00;
    private static final int USER_CODE_LOW = 0xFF;

    private final ConsumerIrManager irManager;

    public ConsumerIrRemoteCommandSender(Context context) {
        ConsumerIrManager manager = null;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            manager = (ConsumerIrManager) context.getApplicationContext().getSystemService(Context.CONSUMER_IR_SERVICE);
        }
        irManager = manager;
    }

    public boolean isAvailable() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT && irManager != null;
    }

    @Override
    @TargetApi(Build.VERSION_CODES.KITKAT)
    public void send(RemoteKey key) {
        if (!isAvailable()) {
            Log.w("SIGNWAY_REMOTE", "IR service unavailable");
            throw new IllegalStateException("IR emitter unavailable");
        }
        int[] pattern = NecPattern.buildPattern(USER_CODE_HIGH, USER_CODE_LOW, key.code);
        irManager.transmit(CARRIER_FREQUENCY, pattern);
        Log.i("SIGNWAY_REMOTE", "ir transmit " + key.id + " " + key.hexCode());
    }
}
