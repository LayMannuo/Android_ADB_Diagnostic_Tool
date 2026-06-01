import json
import tempfile
import unittest
from pathlib import Path

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
from app.core.ui_text import RECORD_BUTTON_TEXT


class CoreBehaviorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
