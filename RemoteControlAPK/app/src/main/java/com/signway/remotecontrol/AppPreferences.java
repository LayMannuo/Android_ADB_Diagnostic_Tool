package com.signway.remotecontrol;

import android.content.Context;
import android.content.SharedPreferences;

public final class AppPreferences {
    private static final String PREFS = "signway_remote_prefs";
    private static final String FIRST_LAUNCH = "first_launch";
    private static final String SHOW_KEY_CODES = "show_key_codes";
    private static final String LANGUAGE_MODE = "language_mode";

    private final SharedPreferences prefs;

    public AppPreferences(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public boolean isFirstLaunch() {
        return prefs.getBoolean(FIRST_LAUNCH, true);
    }

    public void markIntroSeen() {
        prefs.edit().putBoolean(FIRST_LAUNCH, false).apply();
    }

    public boolean showKeyCodes() {
        return prefs.getBoolean(SHOW_KEY_CODES, false);
    }

    public void setShowKeyCodes(boolean show) {
        prefs.edit().putBoolean(SHOW_KEY_CODES, show).apply();
    }

    public LanguageMode languageMode() {
        return LanguageMode.fromStoredValue(prefs.getString(LANGUAGE_MODE, "system"));
    }

    public void setLanguageMode(LanguageMode mode) {
        prefs.edit().putString(LANGUAGE_MODE, mode.storedValue()).apply();
    }
}
