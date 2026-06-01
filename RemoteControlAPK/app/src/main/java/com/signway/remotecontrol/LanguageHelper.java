package com.signway.remotecontrol;

import java.util.Locale;

public final class LanguageHelper {
    private LanguageHelper() {
    }

    public static LanguageMode resolve(LanguageMode selectedMode, Locale systemLocale) {
        if (selectedMode == LanguageMode.ZH || selectedMode == LanguageMode.EN) {
            return selectedMode;
        }
        if (systemLocale != null && "zh".equalsIgnoreCase(systemLocale.getLanguage())) {
            return LanguageMode.ZH;
        }
        return LanguageMode.EN;
    }
}
