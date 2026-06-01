package com.signway.remotecontrol;

import android.util.Log;

public final class LoggingRemoteCommandSender implements RemoteCommandSender {
    @Override
    public void send(RemoteKey key) {
        Log.i("SIGNWAY_REMOTE", "send " + key.id + " " + key.hexCode());
    }
}
