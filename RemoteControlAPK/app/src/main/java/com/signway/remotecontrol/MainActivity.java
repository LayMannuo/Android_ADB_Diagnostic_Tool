package com.signway.remotecontrol;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;

import java.util.Locale;

public class MainActivity extends Activity {
    private static final int BLACK = Color.rgb(13, 15, 18);
    private static final int PANEL = Color.rgb(24, 25, 29);
    private static final int LIGHT = Color.rgb(241, 245, 249);
    private static final int LIGHT_TEXT = Color.rgb(17, 24, 39);
    private static final int NAV = Color.rgb(46, 33, 122);
    private static final int INPUT = Color.rgb(219, 234, 254);
    private static final int INPUT_TEXT = Color.rgb(30, 58, 138);
    private static final int POWER = Color.rgb(220, 38, 38);
    private static final int SOURCE = Color.rgb(22, 163, 74);

    private AppPreferences preferences;
    private ConsumerIrRemoteCommandSender sender;
    private LanguageMode activeLanguage;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        enterFullScreen();
        preferences = new AppPreferences(this);
        sender = new ConsumerIrRemoteCommandSender(this);
        refreshLanguage();
        buildRemoteUi();
        if (preferences.isFirstLaunch()) {
            showIntro(0);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterFullScreen();
        }
    }

    private void enterFullScreen() {
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        );
    }

    private void refreshLanguage() {
        activeLanguage = LanguageHelper.resolve(preferences.languageMode(), Locale.getDefault());
        setTitle(Texts.appName(activeLanguage));
    }

    private void rebuild() {
        refreshLanguage();
        buildRemoteUi();
    }

    private void buildRemoteUi() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(false);
        scrollView.setBackgroundColor(Color.rgb(235, 240, 247));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(12), dp(14), dp(12), dp(20));
        scrollView.addView(root, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout remote = new LinearLayout(this);
        remote.setOrientation(LinearLayout.VERTICAL);
        remote.setPadding(dp(16), dp(16), dp(16), dp(20));
        remote.setBackground(round(PANEL, dp(32), Color.rgb(38, 43, 50), dp(1)));
        root.addView(remote, new LinearLayout.LayoutParams(dp(330), ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout header = row();
        header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        TextView title = text(Texts.appName(activeLanguage), 18, Color.WHITE, true);
        TextView subtitle = text(Texts.subtitle(activeLanguage), 11, Color.rgb(148, 163, 184), false);
        titles.addView(title);
        titles.addView(subtitle);
        header.addView(titles, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button settings = smallButton("⚙");
        settings.setContentDescription(Texts.settings(activeLanguage));
        settings.setOnClickListener(v -> showSettings());
        header.addView(settings, new LinearLayout.LayoutParams(dp(44), dp(38)));
        remote.addView(header);

        LinearLayout top = row();
        top.setPadding(0, dp(12), 0, dp(8));
        top.addView(keyButton(RemoteKeys.POWER, dp(58), dp(58)), new LinearLayout.LayoutParams(dp(58), dp(58)));
        LinearLayout menuGroup = new LinearLayout(this);
        menuGroup.setOrientation(LinearLayout.HORIZONTAL);
        menuGroup.setGravity(Gravity.CENTER);
        menuGroup.addView(keyButton(RemoteKeys.MENU, dp(82), dp(44)));
        addGap(menuGroup, 8, false);
        menuGroup.addView(keyButton(RemoteKeys.SETUP, dp(82), dp(44)));
        top.addView(menuGroup, new LinearLayout.LayoutParams(0, dp(58), 1));
        top.addView(keyButton(RemoteKeys.SOURCE, dp(58), dp(58)), new LinearLayout.LayoutParams(dp(58), dp(58)));
        remote.addView(top);

        remote.addView(grid(new RemoteKey[]{RemoteKeys.F1, RemoteKeys.F2, RemoteKeys.F3, RemoteKeys.F4}, 4, dp(8), dp(44)));
        addGap(remote, 12, true);
        remote.addView(navigationPad());
        addGap(remote, 12, true);
        remote.addView(playbackRow());
        addGap(remote, 10, true);
        remote.addView(numberAndUtilityGrid());
        addGap(remote, 10, true);
        remote.addView(grid(new RemoteKey[]{RemoteKeys.HDMI, RemoteKeys.VGA, RemoteKeys.YPBPR, RemoteKeys.AV}, 4, dp(8), dp(42)));

        setContentView(scrollView);
    }

    private LinearLayout navigationPad() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(12), dp(12), dp(12), dp(12));
        box.setBackground(round(Color.rgb(31, 26, 74), dp(22), Color.rgb(70, 68, 130), dp(1)));

        LinearLayout r1 = row();
        r1.addView(keyButton(RemoteKeys.FUNC, dp(56), dp(50)));
        r1.addView(keyButton(RemoteKeys.UP, dp(128), dp(50)), weightParams(1, dp(50)));
        r1.addView(keyButton(RemoteKeys.SEARCH, dp(56), dp(50)));
        box.addView(r1);
        addGap(box, 8, true);

        LinearLayout r2 = row();
        r2.addView(keyButton(RemoteKeys.LEFT, dp(72), dp(72)));
        r2.addView(keyButton(RemoteKeys.PLAY_PAUSE, dp(86), dp(72)), weightParams(1, dp(72)));
        r2.addView(keyButton(RemoteKeys.RIGHT, dp(72), dp(72)));
        box.addView(r2);
        addGap(box, 8, true);

        LinearLayout r3 = row();
        r3.addView(keyButton(RemoteKeys.HOME, dp(56), dp(50)));
        r3.addView(keyButton(RemoteKeys.DOWN, dp(128), dp(50)), weightParams(1, dp(50)));
        r3.addView(keyButton(RemoteKeys.BACK, dp(56), dp(50)));
        box.addView(r3);
        return box;
    }

    private LinearLayout playbackRow() {
        LinearLayout row = row();
        row.addView(keyButton(RemoteKeys.PREVIOUS, dp(72), dp(42)));
        row.addView(keyButton(RemoteKeys.STOP, dp(116), dp(42)), weightParams(1, dp(42)));
        row.addView(keyButton(RemoteKeys.NEXT, dp(72), dp(42)));
        return row;
    }

    private LinearLayout numberAndUtilityGrid() {
        return grid(new RemoteKey[]{
                find("digit_1"), find("digit_2"), find("digit_3"), RemoteKeys.MUTE,
                find("digit_4"), find("digit_5"), find("digit_6"), RemoteKeys.VOL_UP,
                find("digit_7"), find("digit_8"), find("digit_9"), RemoteKeys.VOL_DOWN,
                RemoteKeys.INFO, find("digit_0"), RemoteKeys.LOCK, RemoteKeys.DISP
        }, 4, dp(8), dp(42));
    }

    private RemoteKey find(String id) {
        for (RemoteKey key : RemoteKeys.ALL) {
            if (key.id.equals(id)) return key;
        }
        throw new IllegalArgumentException(id);
    }

    private LinearLayout grid(RemoteKey[] keys, int columns, int gap, int height) {
        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        for (int i = 0; i < keys.length; i += columns) {
            LinearLayout row = row();
            for (int c = 0; c < columns; c++) {
                if (c > 0) addGap(row, gap, false);
                row.addView(keyButton(keys[i + c], 0, height), weightParams(1, height));
            }
            outer.addView(row);
            if (i + columns < keys.length) addGap(outer, gap, true);
        }
        return outer;
    }

    private Button keyButton(RemoteKey key, int width, int height) {
        Button button = new Button(this);
        button.setAllCaps(false);
        button.setText(buttonText(key));
        button.setTextSize(key == RemoteKeys.PLAY_PAUSE ? 16 : 12);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setTextColor(textColor(key));
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(3), 0, dp(3), 0);
        button.setMinHeight(0);
        button.setMinWidth(0);
        button.setMinimumHeight(0);
        button.setMinimumWidth(0);
        button.setBackground(round(backgroundColor(key), key == RemoteKeys.PLAY_PAUSE || key == RemoteKeys.POWER || key == RemoteKeys.SOURCE ? dp(28) : dp(9), Color.TRANSPARENT, 0));
        button.setContentDescription(key.label(activeLanguage) + " " + key.hexCode());
        button.setOnClickListener(v -> {
            try {
                sender.send(key);
                Toast.makeText(this, Texts.sent(activeLanguage, key), Toast.LENGTH_SHORT).show();
            } catch (RuntimeException error) {
                Toast.makeText(this, Texts.irUnavailable(activeLanguage), Toast.LENGTH_LONG).show();
            }
        });
        if (width > 0 && height > 0) {
            button.setLayoutParams(new LinearLayout.LayoutParams(width, height));
        }
        return button;
    }

    private String buttonText(RemoteKey key) {
        String label = key.label(activeLanguage);
        if (preferences.showKeyCodes()) {
            return label + "\n" + key.hexCode();
        }
        return label;
    }

    private int backgroundColor(RemoteKey key) {
        if (key.tone == RemoteKey.Tone.POWER) return POWER;
        if (key.tone == RemoteKey.Tone.SOURCE) return SOURCE;
        if (key.tone == RemoteKey.Tone.NAV) return NAV;
        if (key.tone == RemoteKey.Tone.INPUT) return INPUT;
        return LIGHT;
    }

    private int textColor(RemoteKey key) {
        if (key.tone == RemoteKey.Tone.POWER || key.tone == RemoteKey.Tone.SOURCE || key.tone == RemoteKey.Tone.NAV) {
            return Color.WHITE;
        }
        if (key.tone == RemoteKey.Tone.INPUT) return INPUT_TEXT;
        return LIGHT_TEXT;
    }

    private void showIntro(int page) {
        new AlertDialog.Builder(this)
                .setTitle(Texts.introTitle(activeLanguage, page))
                .setMessage(Texts.introMessage(activeLanguage, page))
                .setNegativeButton(Texts.skip(activeLanguage), (dialog, which) -> {
                    preferences.markIntroSeen();
                    dialog.dismiss();
                })
                .setPositiveButton(page == 2 ? Texts.start(activeLanguage) : Texts.next(activeLanguage), (dialog, which) -> {
                    dialog.dismiss();
                    if (page == 2) {
                        preferences.markIntroSeen();
                    } else {
                        showIntro(page + 1);
                    }
                })
                .show();
    }

    private void showSettings() {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(18), dp(8), dp(18), 0);

        CheckBox showCodes = new CheckBox(this);
        showCodes.setText(Texts.showKeyCodes(activeLanguage));
        showCodes.setTextSize(16);
        showCodes.setChecked(preferences.showKeyCodes());
        content.addView(showCodes);

        TextView languageLabel = text(Texts.language(activeLanguage), 15, Color.rgb(51, 65, 85), true);
        languageLabel.setPadding(0, dp(12), 0, dp(4));
        content.addView(languageLabel);

        RadioGroup languageGroup = new RadioGroup(this);
        languageGroup.setOrientation(RadioGroup.VERTICAL);
        RadioButton system = radio(100, Texts.followSystem(activeLanguage));
        RadioButton zh = radio(101, Texts.simplifiedChinese(activeLanguage));
        RadioButton en = radio(102, Texts.english(activeLanguage));
        languageGroup.addView(system);
        languageGroup.addView(zh);
        languageGroup.addView(en);
        LanguageMode selected = preferences.languageMode();
        languageGroup.check(selected == LanguageMode.ZH ? 101 : selected == LanguageMode.EN ? 102 : 100);
        content.addView(languageGroup);

        TextView version = text(Texts.version(activeLanguage), 13, Color.rgb(100, 116, 139), false);
        version.setPadding(0, dp(10), 0, 0);
        content.addView(version);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(Texts.settings(activeLanguage))
                .setView(content)
                .setNeutralButton(Texts.reopenGuide(activeLanguage), null)
                .setPositiveButton(Texts.close(activeLanguage), null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> {
                dialog.dismiss();
                showIntro(0);
            });
            showCodes.setOnCheckedChangeListener((CompoundButton buttonView, boolean isChecked) -> {
                preferences.setShowKeyCodes(isChecked);
                rebuild();
            });
            languageGroup.setOnCheckedChangeListener((group, checkedId) -> {
                if (checkedId == 101) preferences.setLanguageMode(LanguageMode.ZH);
                else if (checkedId == 102) preferences.setLanguageMode(LanguageMode.EN);
                else preferences.setLanguageMode(LanguageMode.SYSTEM);
                dialog.dismiss();
                rebuild();
            });
        });
        dialog.show();
    }

    private RadioButton radio(int id, String text) {
        RadioButton button = new RadioButton(this);
        button.setId(id);
        button.setText(text);
        button.setTextSize(15);
        return button;
    }

    private Button smallButton(String label) {
        Button button = new Button(this);
        button.setAllCaps(false);
        button.setText(label);
        button.setTextSize(18);
        button.setTextColor(Color.WHITE);
        button.setPadding(0, 0, 0, 0);
        button.setMinHeight(0);
        button.setMinWidth(0);
        button.setMinimumHeight(0);
        button.setMinimumWidth(0);
        button.setBackground(round(Color.rgb(39, 45, 54), dp(12), Color.rgb(72, 81, 95), dp(1)));
        return button;
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        return row;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setIncludeFontPadding(true);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private LinearLayout.LayoutParams weightParams(float weight, int height) {
        return new LinearLayout.LayoutParams(0, height, weight);
    }

    private void addGap(LinearLayout layout, int size, boolean vertical) {
        View gap = new View(this);
        layout.addView(gap, new LinearLayout.LayoutParams(vertical ? 1 : size, vertical ? size : 1));
    }

    private GradientDrawable round(int color, int radius, int strokeColor, int strokeWidth) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        if (strokeWidth > 0) drawable.setStroke(strokeWidth, strokeColor);
        return drawable;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
