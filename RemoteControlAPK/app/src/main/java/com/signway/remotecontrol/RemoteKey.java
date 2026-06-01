package com.signway.remotecontrol;

public final class RemoteKey {
    public enum Tone {
        POWER,
        SOURCE,
        NAV,
        LIGHT,
        INPUT
    }

    public final String id;
    public final String labelZh;
    public final String labelEn;
    public final String descriptionZh;
    public final String descriptionEn;
    public final int code;
    public final Tone tone;

    public RemoteKey(String id, String labelZh, String labelEn, String descriptionZh, String descriptionEn, int code, Tone tone) {
        this.id = id;
        this.labelZh = labelZh;
        this.labelEn = labelEn;
        this.descriptionZh = descriptionZh;
        this.descriptionEn = descriptionEn;
        this.code = code;
        this.tone = tone;
    }

    public String label(LanguageMode language) {
        return language == LanguageMode.ZH ? labelZh : labelEn;
    }

    public String description(LanguageMode language) {
        return language == LanguageMode.ZH ? descriptionZh : descriptionEn;
    }

    public String hexCode() {
        return String.format("0x%02X", code);
    }
}
