package com.signway.remotecontrol;

import org.junit.Test;

import java.util.Locale;

import static org.junit.Assert.assertEquals;

public class LanguageHelperTest {
    @Test
    public void systemChineseResolvesToChinese() {
        assertEquals(LanguageMode.ZH, LanguageHelper.resolve(LanguageMode.SYSTEM, Locale.SIMPLIFIED_CHINESE));
    }

    @Test
    public void systemNonChineseResolvesToEnglish() {
        assertEquals(LanguageMode.EN, LanguageHelper.resolve(LanguageMode.SYSTEM, Locale.US));
    }

    @Test
    public void manualSelectionOverridesSystem() {
        assertEquals(LanguageMode.EN, LanguageHelper.resolve(LanguageMode.EN, Locale.SIMPLIFIED_CHINESE));
        assertEquals(LanguageMode.ZH, LanguageHelper.resolve(LanguageMode.ZH, Locale.US));
    }
}
