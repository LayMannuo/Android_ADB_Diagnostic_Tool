package com.signway.remotecontrol;

public final class Texts {
    private Texts() {
    }

    public static String appName(LanguageMode language) {
        return language == LanguageMode.ZH ? "遥控器" : "Remote Control";
    }

    public static String subtitle(LanguageMode language) {
        return language == LanguageMode.ZH ? "用户码 00FF · 标准键码" : "User Code 00FF · Standard Keys";
    }

    public static String settings(LanguageMode language) {
        return language == LanguageMode.ZH ? "设置" : "Settings";
    }

    public static String sent(LanguageMode language, RemoteKey key) {
        return (language == LanguageMode.ZH ? "已发送：" : "Sent: ") + key.label(language) + " " + key.hexCode();
    }

    public static String irUnavailable(LanguageMode language) {
        return language == LanguageMode.ZH ? "未检测到可用红外发射器" : "No available IR emitter detected";
    }

    public static String introTitle(LanguageMode language, int page) {
        if (language == LanguageMode.ZH) {
            String[] titles = {"基础控制", "菜单与信号源", "调试与反馈"};
            return titles[page];
        }
        String[] titles = {"Basic Controls", "Menus & Sources", "Debug & Feedback"};
        return titles[page];
    }

    public static String introMessage(LanguageMode language, int page) {
        if (language == LanguageMode.ZH) {
            String[] messages = {
                    "电源、方向、确认、返回、主页和播放/暂停是最常用的控制。主界面按真实遥控器位置排列，照着实体遥控器就能找。",
                    "MENU 打开显示驱动菜单，SETUP 打开 OSD 设置，SOURCE 和 HDMI/VGA/YPbPr/AV 用于切换信号源。",
                    "每次点击都会显示发送反馈。需要排查时，可在设置中开启“显示键码”，例如 0x45、0x18。"
            };
            return messages[page];
        }
        String[] messages = {
                "Power, navigation, OK, Back, Home, and Play/Pause are the most common controls. The layout follows the physical remote.",
                "MENU opens the display menu, SETUP opens OSD settings, and SOURCE plus HDMI/VGA/YPbPr/AV switch input sources.",
                "Every tap shows feedback. Enable key-code display in Settings when troubleshooting, such as 0x45 or 0x18."
        };
        return messages[page];
    }

    public static String next(LanguageMode language) {
        return language == LanguageMode.ZH ? "下一步" : "Next";
    }

    public static String start(LanguageMode language) {
        return language == LanguageMode.ZH ? "开始使用" : "Start";
    }

    public static String skip(LanguageMode language) {
        return language == LanguageMode.ZH ? "跳过" : "Skip";
    }

    public static String showKeyCodes(LanguageMode language) {
        return language == LanguageMode.ZH ? "显示键码" : "Show key codes";
    }

    public static String reopenGuide(LanguageMode language) {
        return language == LanguageMode.ZH ? "重新查看功能说明" : "Reopen guide";
    }

    public static String language(LanguageMode language) {
        return language == LanguageMode.ZH ? "语言" : "Language";
    }

    public static String followSystem(LanguageMode language) {
        return language == LanguageMode.ZH ? "跟随系统" : "Follow system";
    }

    public static String simplifiedChinese(LanguageMode language) {
        return language == LanguageMode.ZH ? "简体中文" : "Simplified Chinese";
    }

    public static String english(LanguageMode language) {
        return "English";
    }

    public static String version(LanguageMode language) {
        return language == LanguageMode.ZH ? "版本 1.0.2" : "Version 1.0.2";
    }

    public static String cancel(LanguageMode language) {
        return language == LanguageMode.ZH ? "取消" : "Cancel";
    }

    public static String close(LanguageMode language) {
        return language == LanguageMode.ZH ? "关闭" : "Close";
    }
}
