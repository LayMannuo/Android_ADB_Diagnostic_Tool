package com.signway.remotecontrol;

public enum LanguageMode {
    SYSTEM,
    ZH,
    EN;

    public static LanguageMode fromStoredValue(String value) {
        if ("zh".equals(value)) return ZH;
        if ("en".equals(value)) return EN;
        return SYSTEM;
    }

    public String storedValue() {
        if (this == ZH) return "zh";
        if (this == EN) return "en";
        return "system";
    }
}
