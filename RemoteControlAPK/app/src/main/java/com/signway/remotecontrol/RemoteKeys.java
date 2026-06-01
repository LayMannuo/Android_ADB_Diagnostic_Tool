package com.signway.remotecontrol;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public final class RemoteKeys {
    public static final RemoteKey POWER = key("power", "电源", "Power", "电源开关", "Power on/off", 0x45, RemoteKey.Tone.POWER);
    public static final RemoteKey MENU = key("menu", "菜单", "Menu", "开启显示驱动菜单", "Open display menu", 0x51, RemoteKey.Tone.LIGHT);
    public static final RemoteKey SETUP = key("setup", "设置", "Setup", "开启 OSD 菜单设置", "Open OSD settings", 0x46, RemoteKey.Tone.LIGHT);
    public static final RemoteKey SOURCE = key("source", "信号源", "Source", "开启信号源设置菜单", "Open source menu", 0x52, RemoteKey.Tone.SOURCE);
    public static final RemoteKey F1 = key("f1", "F1", "F1", "顺序操作，退出 APK", "Function key", 0x49, RemoteKey.Tone.LIGHT);
    public static final RemoteKey F2 = key("f2", "F2", "F2", "功能键", "Function key", 0x4D, RemoteKey.Tone.LIGHT);
    public static final RemoteKey F3 = key("f3", "F3", "F3", "功能键", "Function key", 0x55, RemoteKey.Tone.LIGHT);
    public static final RemoteKey F4 = key("f4", "F4", "F4", "功能键", "Function key", 0x59, RemoteKey.Tone.LIGHT);
    public static final RemoteKey FUNC = key("func", "功能", "Func", "四个方格功能键", "Function grid", 0x4A, RemoteKey.Tone.NAV);
    public static final RemoteKey SEARCH = key("search", "搜索", "Search", "搜索", "Search", 0x5A, RemoteKey.Tone.NAV);
    public static final RemoteKey HOME = key("home", "主页", "Home", "Home 键", "Home", 0x48, RemoteKey.Tone.NAV);
    public static final RemoteKey BACK = key("back", "返回", "Back", "返回上级菜单", "Back", 0x5B, RemoteKey.Tone.NAV);
    public static final RemoteKey UP = key("up", "▲", "▲", "上移光标", "Move up", 0x19, RemoteKey.Tone.NAV);
    public static final RemoteKey DOWN = key("down", "▼", "▼", "下移光标", "Move down", 0x1C, RemoteKey.Tone.NAV);
    public static final RemoteKey LEFT = key("left", "◀", "◀", "左移光标，删除", "Move left / delete", 0x0C, RemoteKey.Tone.NAV);
    public static final RemoteKey RIGHT = key("right", "▶", "▶", "右移光标", "Move right", 0x5E, RemoteKey.Tone.NAV);
    public static final RemoteKey PLAY_PAUSE = key("play_pause", "确认", "OK", "暂停/播放；确认选择", "Play/Pause; confirm", 0x18, RemoteKey.Tone.NAV);
    public static final RemoteKey PREVIOUS = key("previous", "上一个", "Prev", "上一个节目", "Previous program", 0x44, RemoteKey.Tone.LIGHT);
    public static final RemoteKey NEXT = key("next", "下一个", "Next", "下一个节目", "Next program", 0x43, RemoteKey.Tone.LIGHT);
    public static final RemoteKey STOP = key("stop", "停止", "Stop", "停止节目播放并返回主界面", "Stop playback and return home", 0x47, RemoteKey.Tone.LIGHT);
    public static final RemoteKey MUTE = key("mute", "静音", "Mute", "静音", "Mute", 0x07, RemoteKey.Tone.LIGHT);
    public static final RemoteKey VOL_UP = key("vol_up", "音量+", "Vol+", "增大音量", "Volume up", 0x15, RemoteKey.Tone.LIGHT);
    public static final RemoteKey VOL_DOWN = key("vol_down", "音量-", "Vol-", "减小音量", "Volume down", 0x09, RemoteKey.Tone.LIGHT);
    public static final RemoteKey INFO = key("info", "信息", "Info", "信息", "Information", 0x4C, RemoteKey.Tone.LIGHT);
    public static final RemoteKey LOCK = key("lock", "锁定", "Lock", "遥控密码锁", "Remote lock", 0x0F, RemoteKey.Tone.LIGHT);
    public static final RemoteKey DISP = key("disp", "显示", "DISP", "显示", "Display", 0x0D, RemoteKey.Tone.LIGHT);
    public static final RemoteKey HDMI = key("hdmi", "HDMI", "HDMI", "选择 HDMI 信号源", "Select HDMI source", 0x40, RemoteKey.Tone.INPUT);
    public static final RemoteKey VGA = key("vga", "VGA", "VGA", "选择 VGA 信号源", "Select VGA source", 0x41, RemoteKey.Tone.INPUT);
    public static final RemoteKey YPBPR = key("ypbpr", "YPbPr", "YPbPr", "选择 YPbPr 信号源", "Select YPbPr source", 0x42, RemoteKey.Tone.INPUT);
    public static final RemoteKey AV = key("av", "AV", "AV", "选择 AV 信号源", "Select AV source", 0x01, RemoteKey.Tone.INPUT);

    public static final List<RemoteKey> ALL = Collections.unmodifiableList(Arrays.asList(
            POWER, MENU, SETUP, SOURCE, F1, F2, F3, F4, FUNC, SEARCH, HOME, BACK,
            UP, DOWN, LEFT, RIGHT, PLAY_PAUSE, PREVIOUS, NEXT, STOP, MUTE, VOL_UP, VOL_DOWN,
            digit("1", 0x04), digit("2", 0x05), digit("3", 0x06), digit("4", 0x14), digit("5", 0x16),
            digit("6", 0x17), digit("7", 0x08), digit("8", 0x0A), digit("9", 0x0B), digit("0", 0x0E),
            INFO, LOCK, DISP, HDMI, VGA, YPBPR, AV
    ));

    private RemoteKeys() {
    }

    private static RemoteKey digit(String label, int code) {
        return key("digit_" + label, label, label, "数字键", "Number key", code, RemoteKey.Tone.LIGHT);
    }

    private static RemoteKey key(String id, String zh, String en, String descZh, String descEn, int code, RemoteKey.Tone tone) {
        return new RemoteKey(id, zh, en, descZh, descEn, code, tone);
    }
}
