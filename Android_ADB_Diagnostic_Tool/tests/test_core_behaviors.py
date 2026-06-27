import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QGroupBox

from app.core.adb_manager import AdbManager
from app.core.command_runner import CommandResult, CommandRunner
from app.core.report_generator import ReportGenerator
from app.core.single_log_collector import analyze_log_text, single_log_commands
from app.core.status_messages import status_detail
from app.core.utils import hidden_subprocess_kwargs, safe_text, sanitize_filename
from app.core.zip_exporter import ZipExporter
from app.core.remount_status import evaluate_remount_result
from app.core.screen_mirror import find_scrcpy, start_screen_mirror
from app.core.adb_debug import build_adb_debug_command, build_external_shell_command, needs_external_shell
from app.core.apk_installer import (
    ApkInfo,
    ApkInstallPlanQueue,
    BatchApkInstallQueue,
    ApkInstallOptions,
    ApkInstaller,
    TargetDeviceApkInstallQueue,
    classify_install_failure,
    normalize_apk_filename,
    parse_apk_file,
)
from app.core import apk_installer as apk_installer_module
from app.core.network_adb import DeviceRecord
from app.core.log_collector import LogCollector
from app.core.ui_text import RECORD_BUTTON_TEXT
from app.gui import main_window as main_window_module
from app.gui.apk_install_panel import ApkInstallPanel
from app.gui.live_log_window import LiveLogWorker


class CoreBehaviorTests(unittest.TestCase):
    _qt_app = None

    @classmethod
    def setUpClass(cls):
        cls._qt_app = QApplication.instance() or QApplication([])

    def test_sanitize_filename_replaces_windows_reserved_characters(self):
        self.assertEqual(sanitize_filename('A/B:C*D?E"F<G>H|I '), "A_B_C_D_E_F_G_H_I")

    def test_safe_text_replaces_invalid_bytes(self):
        self.assertEqual(safe_text(b"ok\xfftext"), "ok\ufffdtext")

    def test_adb_manager_builds_serial_command_with_configured_adb(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adb = root / "tools" / "adb" / "adb.exe"
            adb.parent.mkdir(parents=True)
            adb.write_text("", encoding="utf-8")
            manager = AdbManager(project_root=root, serial="SERIAL 123")

            command = manager.build_command(["shell", "getprop"])

            self.assertEqual(command, [str(adb), "-s", "SERIAL 123", "shell", "getprop"])

    def test_command_runner_records_timeout_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = CommandRunner(status_file=root / "command_status.json")
            result = CommandResult(
                category="device_info",
                name="slow",
                command="adb shell sleep 99",
                output_file="01_device_info/slow.txt",
                start_time="2026-06-01T00:00:00",
                end_time="2026-06-01T00:00:05",
                duration_seconds=5.0,
                success=False,
                exit_code=None,
                status="TIMEOUT",
                error="命令执行超时",
            )

            runner.record_result(result)

            data = json.loads((root / "command_status.json").read_text(encoding="utf-8"))
            self.assertEqual(data[0]["status"], "TIMEOUT")
            self.assertEqual(data[0]["error"], "命令执行超时")

    def test_report_generator_writes_summary_html(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "command_status.json").write_text(
                json.dumps(
                    [
                        {"status": "SUCCESS", "name": "ok", "category": "device_info", "error": ""},
                        {
                            "status": "PERMISSION_DENIED",
                            "name": "dmesg",
                            "category": "logcat",
                            "error": "denied",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ReportGenerator().generate(root, {"model": "Demo", "serial": "ABC", "android": "14"})

            html = report.read_text(encoding="utf-8")
            self.assertIn("Android ADB 诊断报告", html)
            self.assertIn("PERMISSION_DENIED", html)

    def test_zip_exporter_creates_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "diagnostic"
            source.mkdir()
            (source / "summary_report.html").write_text("ok", encoding="utf-8")

            archive = ZipExporter().export(source)

            self.assertTrue(archive.exists())
            self.assertEqual(archive.suffix, ".zip")

    def test_hidden_subprocess_kwargs_prevents_console_windows(self):
        kwargs = hidden_subprocess_kwargs()
        self.assertIn("creationflags", kwargs)

    def test_status_detail_contains_reason_and_solution_for_failure(self):
        detail = status_detail("PERMISSION_DENIED", "permission denied")
        self.assertEqual(detail.color, "red")
        self.assertIn("权限不足", detail.message)
        self.assertIn("解决", detail.solution)

    def test_single_log_analysis_finds_crash_keywords_and_conclusion(self):
        analysis = analyze_log_text("06-01 FATAL EXCEPTION: main\njava.lang.RuntimeException: boom")
        self.assertGreaterEqual(analysis["crash_count"], 1)
        self.assertEqual(analysis["severity"], "高")
        self.assertIn("疑似应用崩溃", analysis["conclusion"])
        self.assertIn("优先分析 crash", analysis["suggestions"][0])

    def test_single_log_analysis_detects_network_dns_problem(self):
        analysis = analyze_log_text("ping: unknown host www.baidu.com\nnet.dns1=\n")
        self.assertIn("网络/DNS", analysis["conclusion"])
        self.assertIn("DNS", " ".join(analysis["suggestions"]))

    def test_single_log_commands_exposes_complete_customer_friendly_items(self):
        commands = single_log_commands()
        names = {item["name"] for item in commands}
        self.assertIn("logcat_history", names)
        self.assertIn("crash_logcat", names)
        self.assertIn("dmesg", names)
        self.assertIn("cellular_4g", names)
        self.assertIn("network", names)
        self.assertIn("device_props", names)
        self.assertTrue(all("description" in item for item in commands))

    def test_single_log_items_define_capture_live_and_clear_capabilities(self):
        commands = {item["name"]: item for item in single_log_commands()}

        self.assertEqual(commands["logcat_history"]["live_command"], ["logcat", "-v", "time"])
        self.assertEqual(commands["logcat_history"]["live_preview_title"], "实时预览：Logcat 全量日志")
        self.assertEqual(commands["logcat_history"]["clear_command"], ["logcat", "-c"])
        self.assertEqual(commands["dmesg"]["live_command"], ["shell", "dmesg", "-w"])
        self.assertEqual(commands["dmesg"]["live_preview_title"], "实时预览：内核 dmesg 日志")
        self.assertEqual(commands["dmesg"]["clear_command"], ["shell", "dmesg", "-C"])
        self.assertEqual(commands["cellular_4g"]["live_command"], ["logcat", "-b", "radio", "-v", "time"])
        self.assertEqual(commands["cellular_4g"]["live_preview_title"], "实时预览：4G/radio 蜂窝日志")
        self.assertEqual(commands["cellular_4g"]["clear_command"], ["logcat", "-b", "radio", "-c"])
        self.assertTrue(all("customer_hint" in item for item in commands.values()))
        self.assertTrue(all("fae_hint" in item for item in commands.values()))

    def test_single_log_items_have_explicit_product_capabilities(self):
        commands = {item["name"]: item for item in single_log_commands()}

        self.assertEqual(commands["logcat_history"]["analyzer"], "logcat")
        self.assertTrue(commands["logcat_history"]["supports_snapshot"])
        self.assertTrue(commands["logcat_history"]["supports_live"])
        self.assertTrue(commands["logcat_history"]["supports_clear"])

        self.assertEqual(commands["dmesg"]["analyzer"], "dmesg")
        self.assertTrue(commands["dmesg"]["supports_snapshot"])
        self.assertTrue(commands["dmesg"]["supports_live"])
        self.assertTrue(commands["dmesg"]["supports_clear"])

        self.assertEqual(commands["cellular_4g"]["analyzer"], "radio")
        self.assertTrue(commands["cellular_4g"]["supports_snapshot"])
        self.assertTrue(commands["cellular_4g"]["supports_live"])
        self.assertTrue(commands["cellular_4g"]["supports_clear"])

        self.assertEqual(commands["device_props"]["analyzer"], "props")
        self.assertTrue(commands["device_props"]["supports_snapshot"])
        self.assertFalse(commands["device_props"]["supports_live"])
        self.assertFalse(commands["device_props"]["supports_clear"])

    def test_single_log_dmesg_analysis_has_kernel_specific_conclusion(self):
        analysis = analyze_log_text("watchdog bite\nKernel panic - not syncing\nusb 1-1: device descriptor read error", "dmesg")

        self.assertIn("内核", analysis["conclusion"])
        self.assertGreaterEqual(analysis["kernel_count"], 1)
        self.assertIn("dmesg", " ".join(analysis["suggestions"]))

    def test_single_log_radio_analysis_has_4g_specific_conclusion(self):
        analysis = analyze_log_text("RIL_REQUEST_SETUP_DATA_CALL failed\nSIM absent\nAPN invalid\nregistration denied", "radio")

        self.assertIn("4G", analysis["conclusion"])
        self.assertGreaterEqual(analysis["radio_count"], 1)
        self.assertIn("SIM", " ".join(analysis["suggestions"]))

    def test_adb_debug_parses_quoted_adb_commands(self):
        command, use_serial, display = build_adb_debug_command('pull "/sdcard/My Logs/a.txt" "D:/case logs"', shell_mode=False)

        self.assertEqual(command, ["pull", "/sdcard/My Logs/a.txt", "D:/case logs"])
        self.assertTrue(use_serial)
        self.assertEqual(display, 'adb pull "/sdcard/My Logs/a.txt" "D:/case logs"')

    def test_adb_debug_shell_mode_keeps_command_as_single_shell_payload(self):
        command, use_serial, display = build_adb_debug_command("cd /sdcard/Download && ls -l", shell_mode=True)

        self.assertEqual(command, ["shell", "cd /sdcard/Download && ls -l"])
        self.assertTrue(use_serial)
        self.assertEqual(display, "$ cd /sdcard/Download && ls -l")

    def test_adb_debug_builds_external_cmd_shell_fallback(self):
        command = build_external_shell_command(Path("C:/tool/tools/adb/adb.exe"), "ABC 123")

        self.assertEqual(command[0], "cmd")
        self.assertIn("/k", command)
        self.assertIn('"C:\\tool\\tools\\adb\\adb.exe" -s "ABC 123" shell', command[-1])

    def test_adb_debug_marks_interactive_commands_for_external_shell(self):
        self.assertTrue(needs_external_shell("logcat -v time"))
        self.assertTrue(needs_external_shell("su"))
        self.assertFalse(needs_external_shell("getprop ro.product.model"))

    def test_record_screen_button_text_does_not_hardcode_seconds(self):
        self.assertEqual(RECORD_BUTTON_TEXT, "录制屏幕")

    def test_remount_status_detects_success_and_failure(self):
        ok = evaluate_remount_result(0, "remount succeeded")
        bad = evaluate_remount_result(1, "remount failed: not root")

        self.assertTrue(ok.success)
        self.assertIn("成功", ok.message)
        self.assertFalse(bad.success)
        self.assertIn("root", bad.solution)

    def test_screen_mirror_missing_scrcpy_has_specific_solution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = start_screen_mirror(
                Path(temp_dir),
                serial=None,
                include_resource=False,
                include_path=False,
            )

        self.assertFalse(result.success)
        self.assertIn("scrcpy", result.message)
        self.assertIn("tools/scrcpy", result.solution)

    def test_screen_mirror_finds_bundled_scrcpy(self):
        self.assertIsNotNone(find_scrcpy(Path.cwd(), include_path=False))

    def test_apk_filename_normalization_accepts_extra_suffix_after_apk(self):
        self.assertEqual(normalize_apk_filename("客户测试包.apk(1).1"), "客户测试包.apk")
        self.assertEqual(normalize_apk_filename("demo.apk.bak"), "demo.apk")
        self.assertEqual(normalize_apk_filename("not_apk.txt"), "not_apk.apk")

    def test_apk_parser_reports_size_md5_and_normalized_install_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo App.apk(1).1"
            source.write_bytes(b"fake apk payload")

            info = parse_apk_file(source, root / "temp")

            self.assertEqual(info.original_path, source)
            self.assertEqual(info.install_path.name, "Demo_App.apk")
            self.assertEqual(info.size_bytes, len(b"fake apk payload"))
            self.assertEqual(len(info.md5), 32)
            self.assertTrue(info.normalized)

    def test_apk_parser_does_not_mark_standard_apk_filename_as_abnormal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo App.apk"
            source.write_bytes(b"fake apk payload")

            info = parse_apk_file(source, root / "temp")

            self.assertEqual(info.install_path.name, "Demo_App.apk")
            self.assertFalse(info.normalized)

    def test_apkutils_parser_keeps_manifest_metadata_when_icon_lookup_fails(self):
        class FakeResources:
            def get_resolved_res_configs(self, rid):
                if rid == int("7F0E001C", 16):
                    return [((0, 0, 0, 0, 0, 0, 0, 0), "FAE 远程 ADB")]
                return []

        class FakeApk:
            def __init__(self, path):
                self.path = path

            def get_manifest(self):
                return {
                    "@package": "com.signway.remoteadb",
                    "@android:versionName": "1.0.17-20260626.173414",
                    "@android:versionCode": "29707774",
                    "application": {"@android:label": "@7F0E001C"},
                }

            def get_app_icon(self):
                raise AttributeError("'NoneType' object has no attribute 'groups'")

            def get_arsc(self):
                return FakeResources()

        old_module = sys.modules.get("apkutils2")
        sys.modules["apkutils2"] = types.SimpleNamespace(APK=FakeApk)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                metadata = apk_installer_module._parse_with_apkutils(Path(temp_dir) / "demo.apk", Path(temp_dir))
        finally:
            if old_module is None:
                sys.modules.pop("apkutils2", None)
            else:
                sys.modules["apkutils2"] = old_module

        self.assertEqual(metadata["parse_status"], "SUCCESS")
        self.assertEqual(metadata["package_name"], "com.signway.remoteadb")
        self.assertEqual(metadata["version_name"], "1.0.17-20260626.173414")
        self.assertEqual(metadata["version_code"], "29707774")
        self.assertEqual(metadata["display_name"], "FAE 远程 ADB")
        self.assertIsNone(metadata["icon_path"])
        self.assertIn("未解析到图标", metadata["parse_message"])
        self.assertNotIn("NoneType", metadata["parse_message"])

    def test_apk_panel_shows_standard_apk_without_abnormal_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo App.apk"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            panel = ApkInstallPanel()

            panel.set_apk_info(info)

            status_text = panel.fields["识别状态"].text()
            self.assertIn("标准 APK", status_text)
            self.assertNotIn("文件名异常", status_text)
            self.assertIn("确认包名、版本和 MD5", panel.result.text())

    def test_apk_panel_exposes_three_step_flow(self):
        panel = ApkInstallPanel()

        label_texts = [child.text() for child in panel.findChildren(type(panel.drop_hint)) if hasattr(child, "text")]
        joined = "\n".join(label_texts)
        self.assertIn("1 选择 APK", joined)
        self.assertIn("2 选择安装目标", joined)
        self.assertIn("3 确认 APK 信息与安装选项", joined)
        self.assertIn("待安装 APK", joined)
        self.assertIn("4 安装结果", joined)

    def test_apk_panel_defaults_debuggable_devices_as_install_targets(self):
        panel = ApkInstallPanel()
        records = [
            DeviceRecord(serial="USB123", status="已可调试", connection="数据线连接", model="AIoT3568", android="11"),
            DeviceRecord(serial="192.168.1.70:5566", status="已可调试", connection="同一网络连接", model="DS950", android="14"),
            DeviceRecord(serial="USB999", status="未授权", connection="数据线连接", model="Locked", android="11"),
        ]

        panel.set_target_devices(records)

        self.assertEqual(panel.target_device_table.rowCount(), 3)
        self.assertEqual(panel.selected_target_serials(), ["USB123", "192.168.1.70:5566"])
        self.assertEqual(panel.install_targets_button.text(), "安装到选中设备")
        self.assertIn("已选择 2 台", panel.target_summary.text())

    def test_apk_panel_exposes_one_start_install_button_for_single_or_multiple_apks(self):
        panel = ApkInstallPanel()

        self.assertEqual(panel.start_install_button.text(), "开始安装")
        self.assertTrue(panel.install_button.isHidden())
        self.assertTrue(panel.install_targets_button.isHidden())
        self.assertTrue(panel.start_batch_button.isHidden())
        self.assertTrue(panel.retry_failed_targets_button.isHidden())
        self.assertTrue(panel.retry_failed_button.isHidden())
        self.assertTrue(panel.export_result_button.isHidden())

        panel.set_target_devices([DeviceRecord(serial="USB123", status="已可调试", connection="数据线连接")])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.apk"
            second = root / "second.apk"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            first_info = parse_apk_file(first, root / "temp")
            second_info = parse_apk_file(second, root / "temp")

            panel.set_apk_info(first_info)
            self.assertTrue(panel.start_install_button.isEnabled())
            self.assertEqual(panel.start_install_button.text(), "开始安装")
            panel.add_apk_info(second_info)

            self.assertTrue(panel.start_install_button.isEnabled())
            self.assertEqual(panel.start_install_button.text(), "开始安装")
            self.assertEqual(panel.queue_table.rowCount(), 2)

    def test_feature_description_documents_one_click_diagnostic_scope(self):
        from PySide6.QtWidgets import QTextEdit

        from app.gui.feature_description_panel import FeatureDescriptionPanel

        panel = FeatureDescriptionPanel()
        description = "\n".join(child.toPlainText() for child in panel.findChildren(QTextEdit))

        self.assertIn("62 项 ADB 采集命令", description)
        self.assertIn("设备信息 12 项", description)
        self.assertIn("logcat/dmesg 7 项", description)
        self.assertIn("bugreport 1 项", description)
        self.assertIn("dumpsys 16 项", description)
        self.assertIn("网络 10 项", description)
        self.assertIn("自动截图", description)
        self.assertIn("summary_report.html", description)
        self.assertIn("command_status.json", description)
        self.assertIn("压缩为 zip", description)
        self.assertIn("流程继续执行", description)

    def test_single_log_panel_exposes_capability_summary(self):
        from app.gui.single_log_panel import SingleLogPanel

        panel = SingleLogPanel()

        self.assertIn("支持当前快照抓取", panel.capability.text())
        self.assertIn("支持实时抓取", panel.capability.text())

    def test_single_log_panel_labels_preserve_cached_logs_as_default_flow(self):
        from app.gui.single_log_panel import SingleLogPanel

        panel = SingleLogPanel()

        self.assertEqual(panel.history_button.text(), "导出已缓存日志")
        self.assertIn("含缓存", panel.start_live_button.text())
        self.assertEqual(panel.stop_live_button.text(), "停止抓取并分析")
        self.assertIn("高级", panel.clear_device_log_button.text())
        self.assertFalse(panel.stop_live_button.isEnabled())
        self.assertIn("默认保留设备已缓存日志", panel.result.text())

    def test_single_log_live_preview_keeps_recent_lines_only(self):
        from app.gui.single_log_panel import SingleLogPanel

        panel = SingleLogPanel()
        panel.set_live_status("running", True)

        for index in range(1005):
            panel.append_live_line(f"line-{index}")
        panel.flush_live_preview()

        visible_lines = panel.live_preview.toPlainText().splitlines()
        self.assertEqual(len(visible_lines), 1000)
        self.assertEqual(visible_lines[0], "line-5")
        self.assertEqual(visible_lines[-1], "line-1004")
        self.assertIn("完整日志", panel.result.text())

    def test_live_log_worker_writes_cache_preserving_marker_before_output(self):
        from app.gui import live_log_window

        class FakeStdout:
            def __init__(self):
                self.lines = [b"cached line\n", b"new line\n", b""]

            def readline(self):
                return self.lines.pop(0)

        class FakeProcess:
            pid = 0

            def __init__(self):
                self.stdout = FakeStdout()

            def poll(self):
                return 0

        class FakeAdb:
            def build_command(self, command):
                return ["adb", *command]

        old_popen = live_log_window.subprocess.Popen
        live_log_window.subprocess.Popen = lambda *args, **kwargs: FakeProcess()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                save_file = Path(temp_dir) / "live_logcat.txt"
                worker = LiveLogWorker(FakeAdb(), save_file, ["logcat", "-v", "time"])

                worker.run()

                text = save_file.read_text(encoding="utf-8")
                self.assertIn("以下输出包含设备已缓存日志", text)
                self.assertLess(text.index("以下输出包含设备已缓存日志"), text.index("cached line"))
                self.assertIn("new line", text)
        finally:
            live_log_window.subprocess.Popen = old_popen

    def test_single_log_analysis_text_warns_cached_logs_may_be_historical(self):
        analysis = analyze_log_text("FATAL EXCEPTION: main")
        analysis_text, _, _ = main_window_module.MainWindow._format_analysis(Path("live_logcat_history.txt"), analysis)

        self.assertIn("设备已缓存日志", analysis_text)
        self.assertIn("问题发生时间", analysis_text)

    def test_apk_install_success_deletes_temporary_normalized_file(self):
        class FakeAdb:
            def __init__(self):
                self.calls = []

            def quick_run(self, args, timeout=10, use_serial=True):
                self.calls.append(args)
                if args[:3] == ["shell", "pm", "path"]:
                    return 0, "package:/data/app/demo/base.apk"
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk(1).1"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            info = ApkInfo(**{**info.__dict__, "package_name": "com.demo.app"})

            result = ApkInstaller(FakeAdb(), root).install(info, ApkInstallOptions(replace=True))

            self.assertTrue(result.success)
            self.assertFalse(info.install_path.exists())
            self.assertEqual(result.status, "SUCCESS")

    def test_apk_install_success_verifies_package_exists_before_deleting_temp_file(self):
        class FakeAdb:
            def quick_run(self, args, timeout=10, use_serial=True):
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            info = info.__class__(**{**info.__dict__, "package_name": "com.demo.missing"})

            result = ApkInstaller(FakeAdb(), root).install(info, ApkInstallOptions(replace=True))

            self.assertFalse(result.success)
            self.assertTrue(info.install_path.exists())
            self.assertIn("未确认", result.message)

    def test_apk_install_success_without_package_name_is_unconfirmed_and_keeps_temp_file(self):
        class FakeAdb:
            def quick_run(self, args, timeout=10, use_serial=True):
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            info = ApkInfo(**{**info.__dict__, "package_name": ""})

            result = ApkInstaller(FakeAdb(), root).install(info, ApkInstallOptions(replace=True))

            self.assertFalse(result.success)
            self.assertTrue(info.install_path.exists())
            self.assertIn("未解析到包名", result.message)

    def test_apk_install_failure_keeps_temporary_file_for_retry_and_explains_reason(self):
        class FakeAdb:
            def quick_run(self, args, timeout=10, use_serial=True):
                return 1, "Failure [INSTALL_FAILED_VERSION_DOWNGRADE]"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk.1"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")

            result = ApkInstaller(FakeAdb(), root).install(info, ApkInstallOptions(replace=True))

            self.assertFalse(result.success)
            self.assertTrue(info.install_path.exists())
            self.assertIn("允许降级", result.solution)

    def test_apk_install_options_build_expected_adb_args(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            apk = Path(temp_dir) / "a.apk"
            args = ApkInstallOptions(replace=True, downgrade=True, grant_permissions=True).build_args(apk)

            self.assertEqual(args, ["install", "-r", "-d", "-g", str(apk)])

    def test_apk_install_failure_classifier_handles_signature_mismatch(self):
        message, solution = classify_install_failure("Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]")

        self.assertIn("签名不一致", message)
        self.assertIn("卸载旧版本", solution)

    def test_batch_apk_install_queue_runs_serially_and_continues_after_failure(self):
        class FakeAdb:
            def __init__(self):
                self.calls = []

            def quick_run(self, args, timeout=10, use_serial=True):
                self.calls.append(args)
                apk_name = Path(args[-1]).name
                if args[:3] == ["shell", "pm", "path"]:
                    return 0, "package:/data/app/demo/base.apk"
                if apk_name == "bad.apk":
                    return 1, "Failure [INSTALL_FAILED_VERSION_DOWNGRADE]"
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "good.apk"
            second = root / "bad.apk"
            third = root / "next.apk"
            for path in [first, second, third]:
                path.write_bytes(b"fake apk payload")
            infos = []
            for path, package_name in [(first, "com.demo.good"), (second, "com.demo.bad"), (third, "com.demo.next")]:
                info = parse_apk_file(path, root / "temp")
                infos.append(ApkInfo(**{**info.__dict__, "package_name": package_name}))

            queue = BatchApkInstallQueue(FakeAdb(), root)
            summary = queue.install_all(infos, ApkInstallOptions(replace=True), stop_on_failure=False)

            self.assertEqual(summary.total, 3)
            self.assertEqual(summary.success_count, 2)
            self.assertEqual(summary.failure_count, 1)
            self.assertEqual([item.apk_info.install_path.name for item in summary.results], ["good.apk", "bad.apk", "next.apk"])
            self.assertIn("允许降级", summary.results[1].result.solution)

    def test_batch_apk_install_queue_can_stop_after_first_failure(self):
        class FakeAdb:
            def quick_run(self, args, timeout=10, use_serial=True):
                if Path(args[-1]).name == "bad.apk":
                    return 1, "Failure [INSTALL_FAILED_VERSION_DOWNGRADE]"
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bad = root / "bad.apk"
            skipped = root / "skipped.apk"
            for path in [bad, skipped]:
                path.write_bytes(b"fake apk payload")
            infos = [parse_apk_file(path, root / "temp") for path in [bad, skipped]]

            summary = BatchApkInstallQueue(FakeAdb(), root).install_all(infos, ApkInstallOptions(replace=True), stop_on_failure=True)

            self.assertEqual(summary.total, 2)
            self.assertEqual(len(summary.results), 1)
            self.assertEqual(summary.failure_count, 1)

    def test_target_device_apk_queue_installs_one_apk_to_each_selected_device(self):
        class FakeAdb:
            def __init__(self):
                self.serial = "ORIGINAL"
                self.calls = []

            def set_serial(self, serial):
                self.calls.append(("set_serial", serial))
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                self.calls.append((self.serial, tuple(args), use_serial))
                if args[:3] == ["shell", "pm", "path"]:
                    return 0, "package:/data/app/demo/base.apk"
                if not Path(args[-1]).exists():
                    raise AssertionError("target install should keep the APK file until all devices finish")
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            info = ApkInfo(**{**info.__dict__, "package_name": "com.demo.app"})
            targets = [
                DeviceRecord(serial="USB123", status="已可调试", connection="数据线连接"),
                DeviceRecord(serial="192.168.1.70:5566", status="已可调试", connection="同一网络连接"),
            ]
            adb = FakeAdb()

            summary = TargetDeviceApkInstallQueue(adb, root).install_to_targets(info, targets, ApkInstallOptions(replace=True))

            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.success_count, 2)
            self.assertEqual(summary.failure_count, 0)
            self.assertEqual([record.target.serial for record in summary.results], ["USB123", "192.168.1.70:5566"])
            self.assertIn(("set_serial", "USB123"), adb.calls)
            self.assertIn(("set_serial", "192.168.1.70:5566"), adb.calls)
            self.assertEqual(adb.serial, "ORIGINAL")
            self.assertFalse(info.install_path.exists())

    def test_target_device_apk_queue_stops_after_first_target_failure(self):
        class FakeAdb:
            def __init__(self):
                self.serial = "ORIGINAL"

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                if self.serial == "USB_BAD" and args[:3] != ["shell", "pm", "path"]:
                    return 1, "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]"
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Demo.apk"
            source.write_bytes(b"fake apk payload")
            info = parse_apk_file(source, root / "temp")
            targets = [
                DeviceRecord(serial="USB_BAD", status="已可调试", connection="数据线连接"),
                DeviceRecord(serial="USB_SKIPPED", status="已可调试", connection="数据线连接"),
            ]

            summary = TargetDeviceApkInstallQueue(FakeAdb(), root).install_to_targets(info, targets, ApkInstallOptions(replace=True), stop_on_failure=True)

            self.assertEqual(summary.total, 2)
            self.assertEqual(len(summary.results), 1)
            self.assertEqual(summary.failure_count, 1)
            self.assertTrue(info.install_path.exists())

    def test_apk_install_plan_queue_runs_all_apk_device_combinations_serially(self):
        class FakeAdb:
            def __init__(self):
                self.serial = "ORIGINAL"
                self.calls = []

            def set_serial(self, serial):
                self.calls.append(("set_serial", serial))
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                self.calls.append((self.serial, tuple(args), use_serial))
                if args[:3] == ["shell", "pm", "path"]:
                    return 0, "package:/data/app/demo/base.apk"
                if not Path(args[-1]).exists():
                    raise AssertionError("matrix install should keep each APK until all targets finish")
                return 0, "Success"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.apk"
            second = root / "second.apk"
            first.write_bytes(b"first apk")
            second.write_bytes(b"second apk")
            infos = []
            for path, package_name in [(first, "com.demo.first"), (second, "com.demo.second")]:
                info = parse_apk_file(path, root / "temp")
                infos.append(ApkInfo(**{**info.__dict__, "package_name": package_name}))
            targets = [
                DeviceRecord(serial="USB123", status="已可调试", connection="数据线连接"),
                DeviceRecord(serial="192.168.1.70:5566", status="已可调试", connection="同一网络连接"),
            ]
            adb = FakeAdb()

            summary = ApkInstallPlanQueue(adb, root).install_all(infos, targets, ApkInstallOptions(replace=True))

            self.assertEqual(summary.total, 4)
            self.assertEqual(summary.success_count, 4)
            self.assertEqual(summary.failure_count, 0)
            install_calls = [
                (call[0], Path(call[1][-1]).name)
                for call in adb.calls
                if len(call) == 3 and call[1] and call[1][0] == "install"
            ]
            self.assertEqual(
                install_calls,
                [
                    ("USB123", "first.apk"),
                    ("192.168.1.70:5566", "first.apk"),
                    ("USB123", "second.apk"),
                    ("192.168.1.70:5566", "second.apk"),
                ],
            )
            self.assertEqual(adb.serial, "ORIGINAL")
            self.assertFalse(infos[0].install_path.exists())
            self.assertFalse(infos[1].install_path.exists())

    def test_apk_install_plan_queue_stops_and_keeps_temp_file_after_failure(self):
        class FakeAdb:
            def __init__(self):
                self.serial = "ORIGINAL"

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                if args[:3] != ["shell", "pm", "path"]:
                    return 1, "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]"
                return 0, ""

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.apk"
            second = root / "second.apk"
            first.write_bytes(b"first apk")
            second.write_bytes(b"second apk")
            infos = [parse_apk_file(path, root / "temp") for path in [first, second]]
            targets = [
                DeviceRecord(serial="USB_BAD", status="已可调试", connection="数据线连接"),
                DeviceRecord(serial="USB_SKIPPED", status="已可调试", connection="数据线连接"),
            ]

            summary = ApkInstallPlanQueue(FakeAdb(), root).install_all(infos, targets, ApkInstallOptions(replace=True), stop_on_failure=True)

            self.assertEqual(summary.total, 4)
            self.assertEqual(len(summary.results), 1)
            self.assertEqual(summary.failure_count, 1)
            self.assertTrue(infos[0].install_path.exists())
            self.assertTrue(infos[1].install_path.exists())

    def test_detect_device_stops_on_unauthorized_without_success_override(self):
        class FakeAdb:
            serial = None

            def is_available(self):
                return True

            def list_devices(self):
                return [{"serial": "ABC123", "state": "unauthorized", "raw": "ABC123 unauthorized"}]

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, *args, **kwargs):
                raise AssertionError("unauthorized devices should not refresh properties")

        old_info = main_window_module.show_info
        old_warning = main_window_module.show_warning
        main_window_module.show_info = lambda *args, **kwargs: None
        main_window_module.show_warning = lambda *args, **kwargs: None
        window = main_window_module.MainWindow()
        try:
            window.adb = FakeAdb()

            window.on_device_detection_done(window._detect_device_snapshot())

            self.assertEqual(window.status_labels["连接状态"].text(), "unauthorized")
            self.assertIn("设备未授权", window.run_status.text())
            self.assertNotIn("成功", window.run_status.text())
        finally:
            window.close()
            main_window_module.show_info = old_info
            main_window_module.show_warning = old_warning

    def test_log_collector_preserves_quoted_shell_payload_from_yaml_command(self):
        class FakeAdb:
            def __init__(self):
                self.command = None

            def run(self, command, runner, output_path, category, name, timeout):
                self.command = command

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            adb = FakeAdb()
            collector = LogCollector(adb, root)
            runner = CommandRunner(root / "command_status.json")

            collector._run_command(
                {
                    "category": "network",
                    "name": "quoted_shell",
                    "command": 'shell sh -c "echo one two"',
                    "output": "quoted.txt",
                    "timeout": 5,
                },
                root,
                runner,
            )

            self.assertEqual(adb.command, ["shell", "sh", "-c", "echo one two"])

    def test_log_collector_reports_clear_connection_type(self):
        class FakeAdb:
            def __init__(self, serial):
                self.serial = serial

            def get_property(self, prop):
                values = {
                    "ro.product.model": "DemoModel",
                    "ro.product.brand": "DemoBrand",
                    "ro.build.version.release": "11",
                    "ro.build.version.sdk": "30",
                }
                return values.get(prop, "")

        with tempfile.TemporaryDirectory() as temp_dir:
            usb = LogCollector(FakeAdb("ABC123"), Path(temp_dir)).device_info_summary()
            network = LogCollector(FakeAdb("192.168.1.2:5555"), Path(temp_dir)).device_info_summary()

            self.assertEqual(usb["connection"], "USB")
            self.assertEqual(network["connection"], "网络 ADB")

    def test_screen_mirror_starts_visible_process_without_hidden_startup_flags(self):
        from app.core import screen_mirror

        captured = {}
        old_popen = screen_mirror.subprocess.Popen

        def fake_popen(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs

            class FakeProcess:
                pass

            return FakeProcess()

        screen_mirror.subprocess.Popen = fake_popen
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                scrcpy = root / "tools" / "scrcpy" / "scrcpy.exe"
                scrcpy.parent.mkdir(parents=True)
                scrcpy.write_text("", encoding="utf-8")

                result = screen_mirror.start_screen_mirror(root, serial="ABC123", include_resource=False, include_path=False)

                self.assertTrue(result.success)
                self.assertIn("-s", captured["command"])
                self.assertNotIn("startupinfo", captured["kwargs"])
                self.assertNotIn("creationflags", captured["kwargs"])
        finally:
            screen_mirror.subprocess.Popen = old_popen

    def test_network_range_defaults_to_editable_5566_and_formats_label(self):
        from app.core.network_adb import DEFAULT_NETWORK_ADB_PORT, NetworkRange

        scan_range = NetworkRange("192.168.28.20", "192.168.28.22")

        self.assertEqual(DEFAULT_NETWORK_ADB_PORT, "5566")
        self.assertEqual(scan_range.port, "5566")
        self.assertEqual(scan_range.label(), "192.168.28.20 - 192.168.28.22 : 5566")
        self.assertEqual(list(scan_range.iter_addresses()), ["192.168.28.20", "192.168.28.21", "192.168.28.22"])

    def test_network_range_validation_rejects_bad_inputs(self):
        from app.core.network_adb import validate_network_range

        ok, message, scan_range = validate_network_range("192.168.28.20", "192.168.28.30", "5566")
        self.assertTrue(ok)
        self.assertEqual(message, "")
        self.assertIsNotNone(scan_range)

        ok, message, scan_range = validate_network_range("192.168.28.30", "192.168.28.20", "5566")
        self.assertFalse(ok)
        self.assertIn("结束 IP", message)
        self.assertIsNone(scan_range)

        ok, message, scan_range = validate_network_range("192.168.28.20", "192.168.28.30", "abc")
        self.assertFalse(ok)
        self.assertIn("端口", message)
        self.assertIsNone(scan_range)

    def test_network_adb_scanner_only_marks_adb_verified_device_debuggable(self):
        from app.core.network_adb import NetworkAdbScanner

        class FakeAdb:
            def __init__(self):
                self.serial = "USB123"
                self.calls = []

            def set_serial(self, serial):
                self.calls.append(("set_serial", serial))
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                self.calls.append((self.serial, tuple(args), use_serial))
                if args == ["connect", "192.168.28.20:5566"]:
                    return 0, "connected to 192.168.28.20:5566"
                if args == ["get-state"]:
                    return 0, "device"
                if args == ["shell", "getprop", "ro.product.model"]:
                    return 0, "RK3568"
                if args == ["shell", "getprop", "ro.product.brand"]:
                    return 0, "DemoBrand"
                if args == ["shell", "getprop", "ro.build.version.release"]:
                    return 0, "12"
                return 1, "unexpected"

        adb = FakeAdb()
        scanner = NetworkAdbScanner(adb, port_checker=lambda ip, port, timeout=0.2: True)

        result = scanner.probe_endpoint("192.168.28.20", "5566")

        self.assertEqual(result.status, "已可调试")
        self.assertEqual(result.endpoint, "192.168.28.20:5566")
        self.assertEqual(result.model, "RK3568")
        self.assertEqual(adb.serial, "USB123")
        self.assertIn(("set_serial", "USB123"), adb.calls)

    def test_network_adb_scanner_keeps_open_port_as_candidate_when_adb_fails(self):
        from app.core.network_adb import NetworkAdbScanner

        class FakeAdb:
            serial = None

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                if args == ["connect", "192.168.28.21:5566"]:
                    return 1, "unable to connect"
                return 1, "unexpected"

        scanner = NetworkAdbScanner(FakeAdb(), port_checker=lambda ip, port, timeout=0.2: True)

        result = scanner.probe_endpoint("192.168.28.21", "5566")

        self.assertEqual(result.status, "发现候选设备")
        self.assertIn("端口已响应", result.message)
        self.assertFalse(result.adb_verified)

    def test_connection_panel_exposes_beginner_friendly_network_scan_defaults(self):
        from app.core.network_adb import DEFAULT_NETWORK_ADB_PORT
        from app.gui.connection_panel import ConnectionPanel

        panel = ConnectionPanel()

        self.assertEqual(panel.port.text(), DEFAULT_NETWORK_ADB_PORT)
        self.assertEqual(panel.scan_port.text(), DEFAULT_NETWORK_ADB_PORT)
        self.assertIn("设备连接中心", panel.title())
        self.assertEqual(panel.quick_scan_button.text(), "扫描当前网络")
        self.assertEqual(panel.scan_range_button.text(), "扫描指定范围")
        self.assertEqual(panel.device_table.columnCount(), 6)
        self.assertIn("同一网络", panel.note.toPlainText())

    def test_connection_panel_prioritizes_device_list_and_segmented_connection_modes(self):
        from app.gui.connection_panel import ConnectionPanel

        panel = ConnectionPanel()

        self.assertNotIsInstance(panel, QGroupBox)
        self.assertGreaterEqual(panel.device_table.minimumHeight(), 150)
        self.assertEqual(panel.mode_tabs.count(), 4)
        self.assertEqual([panel.mode_tabs.tabText(index) for index in range(panel.mode_tabs.count())], ["数据线", "同一网络", "无线配对", "高级"])
        self.assertLess(panel.layout().indexOf(panel.device_list_frame), panel.layout().indexOf(panel.mode_tabs))
        self.assertFalse(panel.root_button.isVisible())
        self.assertIn("当前没有设备", panel.empty_device_hint.text())

    def test_fast_device_records_do_not_query_every_device_property(self):
        class FakeAdb:
            serial = None

            def set_serial(self, serial):
                self.serial = serial

            def get_property(self, prop):
                raise AssertionError("fast device list should not run getprop per device")

        window = main_window_module.MainWindow()
        try:
            window.adb = FakeAdb()
            devices = [
                {"serial": "USB123", "state": "device", "raw": "USB123 device product:demo model:AIoT3568 device:rk3568"},
                {"serial": "192.168.1.70:5566", "state": "device", "raw": "192.168.1.70:5566 device product:demo model:DS950"},
            ]

            records = window._fast_device_records_from_adb(devices)

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].model, "AIoT3568")
            self.assertEqual(records[1].connection, "同一网络连接")
        finally:
            window.close()

    def test_diagnosis_page_exposes_compact_current_device_summary_and_quick_actions(self):
        window = main_window_module.MainWindow()
        try:
            self.assertEqual(window.current_device_name.text(), "未选择设备")
            self.assertIn("先连接或扫描设备", window.current_device_detail.text())
            self.assertEqual(len(window.device_status_cards), 4)
            self.assertEqual(window.quick_mirror_button.text(), "投屏")
            self.assertEqual(window.quick_log_button.text(), "日志")
            self.assertFalse(window.engineer_detail_frame.isVisible())
            self.assertEqual(window.detail_toggle_button.text(), "显示工程师详情")
            self.assertLess(window.layout_priority["current_device"], window.layout_priority["connection_center"])
            self.assertLess(window.layout_priority["connection_center"], window.layout_priority["support_tools"])
        finally:
            window.close()

    def test_detect_device_updates_compact_current_device_summary(self):
        class FakeAdb:
            serial = None

            def is_available(self):
                return True

            def list_devices(self):
                return [{"serial": "USB123", "state": "device", "raw": "USB123 device product:demo"}]

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                if args == ["shell", "id"]:
                    return 0, "uid=2000(shell)"
                if args == ["shell", "ip", "addr"]:
                    return 0, "inet 192.168.28.20/24"
                if args == ["get-state"]:
                    return 0, "device"
                return 0, ""

            def get_property(self, prop):
                return {
                    "ro.build.version.release": "11",
                    "ro.build.version.sdk": "30",
                    "ro.product.model": "AIoT3568",
                    "ro.product.brand": "rockchip",
                }.get(prop, "")

        old_info = main_window_module.show_info
        old_warning = main_window_module.show_warning
        main_window_module.show_info = lambda *args, **kwargs: None
        main_window_module.show_warning = lambda *args, **kwargs: None
        window = main_window_module.MainWindow()
        try:
            window.adb = FakeAdb()
            window.start_selected_device_detail_refresh = lambda serial: None

            window.on_device_detection_done(window._detect_device_snapshot())
            window._apply_device_properties(window._read_device_properties(window.adb, "USB123"))

            self.assertEqual(window.current_device_name.text(), "AIoT3568")
            self.assertIn("USB123", window.current_device_detail.text())
            self.assertIn("Android 11", window.current_device_detail.text())
            self.assertIn("已可调试", window.current_device_state.text())
        finally:
            window.close()
            main_window_module.show_info = old_info
            main_window_module.show_warning = old_warning

    def test_busy_state_disables_connection_and_apk_actions(self):
        window = main_window_module.MainWindow()
        try:
            window._set_busy(True)

            self.assertFalse(window.connection_panel.connect_button.isEnabled())
            self.assertFalse(window.connection_panel.tcpip_button.isEnabled())
            self.assertFalse(window.connection_panel.quick_scan_button.isEnabled())
            self.assertFalse(window.connection_panel.scan_range_button.isEnabled())
            self.assertFalse(window.apk_install_panel.choose_button.isEnabled())
            self.assertFalse(window.apk_install_panel.open_button.isEnabled())
            self.assertFalse(window.apk_install_panel.start_batch_button.isEnabled())
        finally:
            window.close()

    def test_apk_install_panel_exposes_batch_queue_controls(self):
        panel = ApkInstallPanel()

        self.assertNotIsInstance(panel, QGroupBox)
        self.assertEqual(panel.queue_table.columnCount(), 7)
        self.assertEqual(panel.start_batch_button.text(), "开始安装队列")
        self.assertEqual(panel.retry_failed_button.text(), "重试失败")
        self.assertIn("失败后停止队列", panel.stop_on_failure_check.text())

    def test_detect_device_populates_connection_center_with_current_device(self):
        class FakeAdb:
            serial = None

            def is_available(self):
                return True

            def list_devices(self):
                return [{"serial": "USB123", "state": "device", "raw": "USB123 device product:demo"}]

            def set_serial(self, serial):
                self.serial = serial

            def quick_run(self, args, timeout=10, use_serial=True):
                if args == ["shell", "id"]:
                    return 0, "uid=2000(shell)"
                if args == ["shell", "ip", "addr"]:
                    return 0, "inet 192.168.28.20/24"
                if args == ["get-state"]:
                    return 0, "device"
                return 0, ""

            def get_property(self, prop):
                return {
                    "ro.build.version.release": "12",
                    "ro.build.version.sdk": "31",
                    "ro.product.model": "RK3568",
                    "ro.product.brand": "DemoBrand",
                }.get(prop, "")

        old_info = main_window_module.show_info
        old_warning = main_window_module.show_warning
        main_window_module.show_info = lambda *args, **kwargs: None
        main_window_module.show_warning = lambda *args, **kwargs: None
        window = main_window_module.MainWindow()
        try:
            window.adb = FakeAdb()
            window.start_selected_device_detail_refresh = lambda serial: None

            window.on_device_detection_done(window._detect_device_snapshot())

            self.assertEqual(window.adb.serial, "USB123")
            self.assertEqual(window.connection_panel.device_table.rowCount(), 1)
            self.assertEqual(window.connection_panel.records[0].status, "已可调试")
            self.assertEqual(window.connection_panel.records[0].connection, "数据线连接")
            self.assertEqual(window.connection_panel.selected_serial(), "USB123")
            self.assertEqual(window.apk_install_panel.selected_target_serials(), ["USB123"])
        finally:
            window.close()
            main_window_module.show_info = old_info
            main_window_module.show_warning = old_warning

    def test_enable_network_debugging_uses_editable_default_5566_port(self):
        window = main_window_module.MainWindow()
        captured = {}
        try:
            window.connection_panel.port.setText("5566")
            window.run_simple_adb = lambda args, title: captured.update({"args": args, "title": title})

            window.connection_panel.tcpip_button.click()

            self.assertEqual(captured["args"], ["tcpip", "5566"])
            self.assertIn("同一网络调试", captured["title"])
        finally:
            window.close()

    def test_packaging_configuration_documents_onefile_exe_and_version_resource(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        build_script = (root / "build_exe.bat").read_text(encoding="utf-8")
        spec = (root / "Android_ADB_Diagnostic_Tool.spec").read_text(encoding="utf-8")

        self.assertIn(r"dist\Android_ADB_Diagnostic_Tool.exe", readme)
        self.assertNotIn(r"dist\Android_ADB_Diagnostic_Tool\Android_ADB_Diagnostic_Tool.exe", readme)
        self.assertIn("python.exe -m PyInstaller", build_script)
        self.assertIn("--version-file version_info.txt", build_script)
        self.assertIn("version='version_info.txt'", spec)
        self.assertTrue((root / "version_info.txt").exists())


if __name__ == "__main__":
    unittest.main()
