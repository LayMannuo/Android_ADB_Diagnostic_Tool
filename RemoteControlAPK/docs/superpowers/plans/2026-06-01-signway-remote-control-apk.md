# SIGNWAY Remote Control APK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small, reliable Android remote-control APK named “欣威视通遥控器” / “SIGNWAY Remote Control” for Android 7.0 through Android 16.

**Architecture:** Use a dependency-light Android project with a single platform `Activity`, programmatic native Views, Android string resources, and `SharedPreferences`. Keep command sending behind a `RemoteCommandSender` interface so future IR/serial/network/ADB protocols can replace the current logging sender without touching UI.

**Tech Stack:** Android Gradle Plugin, Java 17 build runtime, Java source code, platform Android SDK APIs only, minSdk 24, compileSdk/targetSdk 34 for local build, runtime-compatible with Android 16.

---

### Task 1: Lightweight Android Project

**Files:**
- Create: `RemoteControlAPK/settings.gradle`
- Create: `RemoteControlAPK/build.gradle`
- Create: `RemoteControlAPK/app/build.gradle`
- Create: `RemoteControlAPK/app/src/main/AndroidManifest.xml`
- Create: `RemoteControlAPK/app/src/main/res/values/strings.xml`
- Create: `RemoteControlAPK/app/src/main/res/values-en/strings.xml`

- [ ] **Step 1: Create a minimal Android application project**

Use no Compose, no AppCompat, and no Material dependencies. Configure `minSdk 24`, `compileSdk 34`, and `targetSdk 34`.

- [ ] **Step 2: Add bilingual app resources**

Chinese app name must be `欣威视通遥控器`; English app name must be `SIGNWAY Remote Control`.

- [ ] **Step 3: Verify Gradle project recognition**

Run: `./gradlew projects` or the available local Gradle equivalent.

Expected: Gradle lists root project `RemoteControlAPK` and app module `:app`.

### Task 2: Key Model And Tests

**Files:**
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/RemoteKey.java`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/RemoteKeys.java`
- Create: `RemoteControlAPK/app/src/test/java/com/signway/remotecontrol/RemoteKeysTest.java`

- [ ] **Step 1: Write failing tests for key count and representative key codes**

Tests assert that Power is `0x45`, Play/Pause is `0x18`, AV is `0x01`, every key code is in byte range, and all key IDs are unique.

- [ ] **Step 2: Run tests and verify failure**

Run: `./gradlew :app:testDebugUnitTest`.

Expected: tests fail because `RemoteKeys` does not exist.

- [ ] **Step 3: Implement `RemoteKey` and `RemoteKeys`**

Create an immutable model and a full key list from the reference PDF.

- [ ] **Step 4: Run tests and verify pass**

Run: `./gradlew :app:testDebugUnitTest`.

Expected: key model tests pass.

### Task 3: Preferences And Language Mode

**Files:**
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/AppPreferences.java`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/LanguageMode.java`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/LanguageHelper.java`
- Create: `RemoteControlAPK/app/src/test/java/com/signway/remotecontrol/LanguageHelperTest.java`

- [ ] **Step 1: Write failing tests for language resolution**

Tests assert system Chinese resolves to Chinese, non-Chinese resolves to English, manual Chinese stays Chinese, and manual English stays English.

- [ ] **Step 2: Run tests and verify failure**

Run: `./gradlew :app:testDebugUnitTest`.

Expected: tests fail because language classes do not exist.

- [ ] **Step 3: Implement language helper and preferences**

Use `SharedPreferences` for first-launch, debug-key-code display, and language mode.

- [ ] **Step 4: Run tests and verify pass**

Run: `./gradlew :app:testDebugUnitTest`.

Expected: language tests pass.

### Task 4: Native Remote UI

**Files:**
- Replace: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/MainActivity.kt`
- Replace: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/UI.kt`
- Replace: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/Settings.kt`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/MainActivity.java`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/RemoteCommandSender.java`
- Create: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/LoggingRemoteCommandSender.java`

- [ ] **Step 1: Remove the Compose prototype files**

Delete the Kotlin Compose prototype files because the final compatibility and size requirements use native platform Views.

- [ ] **Step 2: Implement `RemoteCommandSender`**

Add `send(RemoteKey key)` and a logging implementation.

- [ ] **Step 3: Implement the polished remote screen**

Use a vertical `ScrollView`, a centered dark remote panel, red Power, green Source, blue-purple navigation, light function keys, and stable button sizes.

- [ ] **Step 4: Add click feedback**

Each key press calls the sender and shows localized feedback with label and hex key code.

### Task 5: Intro And Settings

**Files:**
- Modify: `RemoteControlAPK/app/src/main/java/com/signway/remotecontrol/MainActivity.java`
- Modify: `RemoteControlAPK/app/src/main/res/values/strings.xml`
- Modify: `RemoteControlAPK/app/src/main/res/values-en/strings.xml`

- [ ] **Step 1: Add first-launch guide**

Show a three-step localized guide on first launch with Skip/Next/Start actions.

- [ ] **Step 2: Add settings dialog**

Add settings from the title area with debug key-code toggle, guide reopen action, and language selection.

- [ ] **Step 3: Add immediate language switching**

When language changes, persist the mode and rebuild the UI immediately.

### Task 6: Build And Size Verification

**Files:**
- Modify as needed: `RemoteControlAPK/app/build.gradle`

- [ ] **Step 1: Run unit tests**

Run: `./gradlew :app:testDebugUnitTest`.

Expected: all tests pass.

- [ ] **Step 2: Build debug APK**

Run: `./gradlew :app:assembleDebug`.

Expected: APK is created under `app/build/outputs/apk/debug/`.

- [ ] **Step 3: Check APK size**

Run a filesystem size check on the debug APK.

Expected: APK remains small because the app uses no external UI framework dependencies.
