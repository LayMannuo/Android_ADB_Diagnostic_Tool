from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.adb_manager import AdbManager
from app.core.command_runner import CommandRunner
from app.core.file_transfer import FileTransfer
from app.core.log_collector import LogCollector
from app.core.screenshot_manager import ScreenshotManager
from app.core.screen_mirror import start_screen_mirror
from app.core.single_log_collector import SingleLogCollector, analyze_log_text
from app.core.remount_status import evaluate_remount_result
from app.core.status_messages import status_detail
from app.core.utils import app_base_dir, ensure_dir, open_in_explorer, quote_command, sanitize_filename, timestamp
from app.gui.connection_panel import ConnectionPanel
from app.gui.adb_debug_window import AdbDebugWindow
from app.gui.dialogs import CustomerInfoDialog, DeviceSelectDialog, show_info, show_warning
from app.gui.feature_description_panel import FeatureDescriptionPanel
from app.gui.file_transfer_panel import FileTransferPanel
from app.gui.live_log_window import LiveLogWindow, LiveLogWorker
from app.gui.screenshot_panel import ScreenshotPanel
from app.gui.single_log_panel import SingleLogPanel
from app.gui.styles import style_button


class TaskWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.done.emit(self.func(*self.args, **self.kwargs))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.root = app_base_dir()
        self.output_root = ensure_dir(self.root / "output")
        self.adb = AdbManager(self.root)
        self.current_package: Path | None = None
        self.current_zip: Path | None = None
        self.current_single_log_dir = ensure_dir(self.output_root / "single_logs")
        self.worker: TaskWorker | None = None
        self.live_log_window: LiveLogWindow | None = None
        self.adb_debug_window: AdbDebugWindow | None = None
        self.single_live_worker: LiveLogWorker | None = None
        self.single_live_file: Path | None = None
        self.setWindowTitle("Android 通用 ADB 诊断助手")
        self.resize(1080, 760)
        self.setMinimumSize(640, 420)
        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(self._scroll(self._build_diagnosis_page()), "快速诊断")
        tabs.addTab(self._scroll(self._build_single_log_page()), "单项日志 / 问题分析")
        tabs.addTab(self._scroll(self._build_feature_page()), "功能说明")
        self._connect_signals()
        self.append_log("工具已启动。请先点击“检测设备”。")

    def _scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll

    def _build_diagnosis_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Android 通用 ADB 诊断助手")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("插上设备 -> 检测设备 -> 一键生成诊断包 -> 把 zip 发给工程师")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #5f6368;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        top = QGridLayout()
        self.device_box = self._device_status_box()
        self.connection_panel = ConnectionPanel()
        top.addWidget(self.device_box, 0, 0)
        top.addWidget(self.connection_panel, 0, 1)
        layout.addLayout(top)

        action_box = QGroupBox("一键诊断")
        action_layout = QVBoxLayout(action_box)
        desc = QLabel("自动抓取通用日志并生成 zip 诊断包；单条命令失败不会中断整体流程。")
        desc.setWordWrap(True)
        self.diagnose_button = QPushButton("一键生成诊断包")
        self.diagnose_button.setMinimumHeight(48)
        self.diagnose_button.setStyleSheet("font-size: 17px; font-weight: 700; background: #1a73e8; color: white; padding: 10px;")
        self.diagnose_button.setToolTip("自动抓取完整诊断日志、截图和报告，并生成 zip。")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.run_status = QLabel("待执行")
        self.run_status.setWordWrap(True)
        action_layout.addWidget(desc)
        action_layout.addWidget(self.diagnose_button)
        action_layout.addWidget(self.progress)
        action_layout.addWidget(self.run_status)
        layout.addWidget(action_box)

        lower = QGridLayout()
        self.screenshot_panel = ScreenshotPanel()
        self.file_panel = FileTransferPanel()
        lower.addWidget(self.screenshot_panel, 0, 0)
        lower.addWidget(self.file_panel, 0, 1)
        layout.addLayout(lower)

        log_box = QGroupBox("运行提示 / 工具日志")
        log_layout = QVBoxLayout(log_box)
        buttons = QHBoxLayout()
        self.live_log_button = QPushButton("打开实时日志")
        self.open_output_button = QPushButton("打开导出目录")
        style_button(self.live_log_button, "secondary", "打开独立实时 logcat 窗口。")
        style_button(self.open_output_button, "secondary", "打开 output 导出目录。")
        buttons.addWidget(self.live_log_button)
        buttons.addWidget(self.open_output_button)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        log_layout.addLayout(buttons)
        log_layout.addWidget(self.log)
        layout.addWidget(log_box)
        return page

    def _build_single_log_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.single_log_panel = SingleLogPanel()
        layout.addWidget(self.single_log_panel)
        return page

    def _build_feature_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(FeatureDescriptionPanel())
        return page

    def _device_status_box(self) -> QGroupBox:
        box = QGroupBox("设备状态")
        layout = QGridLayout(box)
        self.status_labels = {}
        fields = [
            "ADB 状态",
            "连接状态",
            "连接方式",
            "设备序列号",
            "Android 版本",
            "SDK 版本",
            "设备型号",
            "品牌",
            "授权状态",
            "root 状态（工程师）",
            "remount 状态（工程师）",
            "IP 摘要（网络）",
        ]
        for index, field in enumerate(fields):
            layout.addWidget(QLabel(field), index, 0)
            label = QLabel("未检测")
            label.setWordWrap(True)
            label.setStyleSheet("color: #5f6368;")
            self.status_labels[field] = label
            layout.addWidget(label, index, 1)
        self.detect_button = QPushButton("检测设备")
        self.refresh_button = QPushButton("刷新设备")
        self.restart_adb_button = QPushButton("重启 ADB 服务")
        style_button(self.detect_button, "primary", "检测 ADB、设备授权、型号、root、IP 等状态。")
        style_button(self.refresh_button, "secondary", "重新刷新当前连接设备。")
        style_button(self.restart_adb_button, "warning", "重启本机 ADB 服务，适合设备 offline 或连接异常时使用。")
        row = len(fields)
        layout.addWidget(self.detect_button, row, 0)
        layout.addWidget(self.refresh_button, row, 1)
        layout.addWidget(self.restart_adb_button, row + 1, 0, 1, 2)
        hint = QLabel(
            "说明：root/remount 是工程师权限状态，普通客户看不懂也没关系；显示不支持通常是量产系统限制。"
            "IP 摘要用于判断设备是否拿到网络地址，没有 IP 时网络功能可能异常。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5f6368; background: #f8fafc; padding: 8px; border: 1px solid #dfe3ea;")
        layout.addWidget(hint, row + 2, 0, 1, 2)
        return box

    def _connect_signals(self):
        self.detect_button.clicked.connect(self.detect_device)
        self.refresh_button.clicked.connect(self.detect_device)
        self.restart_adb_button.clicked.connect(self.restart_adb)
        self.diagnose_button.clicked.connect(self.start_diagnosis)
        self.live_log_button.clicked.connect(self.open_live_log)
        self.open_output_button.clicked.connect(lambda: open_in_explorer(self.output_root))
        self.connection_panel.status_button.clicked.connect(self.detect_device)
        self.connection_panel.tcpip_button.clicked.connect(lambda: self.run_simple_adb(["tcpip", "5555"], "开启网络 ADB"))
        self.connection_panel.connect_button.clicked.connect(self.connect_remote)
        self.connection_panel.disconnect_button.clicked.connect(self.disconnect_remote)
        self.connection_panel.pair_button.clicked.connect(self.pair_remote)
        self.connection_panel.root_button.clicked.connect(lambda: self.run_simple_adb(["root"], "adb root"))
        self.connection_panel.remount_button.clicked.connect(lambda: self.run_simple_adb(["remount"], "adb remount"))
        self.connection_panel.remount_button.clicked.disconnect()
        self.connection_panel.remount_button.clicked.connect(self.run_remount)
        self.screenshot_panel.screenshot_button.clicked.connect(self.take_screenshot)
        self.screenshot_panel.open_screenshot_button.clicked.connect(lambda: open_in_explorer(self.output_root / "screenshots"))
        self.screenshot_panel.record_button.clicked.connect(self.record_screen)
        self.screenshot_panel.mirror_button.clicked.connect(self.start_screen_mirror)
        self.screenshot_panel.open_record_button.clicked.connect(lambda: open_in_explorer(self.output_root / "screenrecords"))
        self.file_panel.push_button.clicked.connect(self.push_file)
        self.file_panel.pull_button.clicked.connect(self.pull_file)
        self.single_log_panel.history_button.clicked.connect(self.capture_history_logcat)
        self.single_log_panel.start_live_button.clicked.connect(self.start_single_live_log)
        self.single_log_panel.stop_live_button.clicked.connect(self.stop_single_live_log)
        self.single_log_panel.clear_device_log_button.clicked.connect(self.clear_device_logcat)
        self.single_log_panel.open_button.clicked.connect(lambda: open_in_explorer(self.current_single_log_dir))

        self.adb_debug_button = QPushButton("打开 ADB 调试窗口")
        style_button(self.adb_debug_button, "engineer", "打开 FAE 调试窗口，直接执行 adb/shell 命令。")
        self.adb_debug_button.clicked.connect(self.open_adb_debug_window)
        self.device_box.layout().addWidget(self.adb_debug_button, self.device_box.layout().rowCount(), 0, 1, 2)

    def append_log(self, text: str):
        self.log.append(text)

    def set_running_status(self, message: str, busy: bool = True):
        self.run_status.setStyleSheet("color: #b06000;")
        self.run_status.setText(message)
        self.append_log(message)
        self._set_busy(busy)

    def set_result_status(self, title: str, status: str, error: str = "", path: Path | None = None):
        detail = status_detail(status, error)
        suffix = f"\n文件位置：{path}" if path else ""
        text = f"{detail.message}\n{detail.solution}{suffix}"
        self.run_status.setStyleSheet(f"color: {'#137333' if detail.color == 'green' else '#b3261e'};")
        self.run_status.setText(text)
        self.append_log(f"{title}：{text}")
        if detail.color == "green":
            show_info(self, title, text)
        else:
            show_warning(self, title, text)

    def set_direct_result_status(self, title: str, success: bool, message: str, solution: str = ""):
        text = message if not solution else f"{message}\n{solution}"
        color = "#137333" if success else "#b3261e"
        self.run_status.setStyleSheet(f"color: {color};")
        self.run_status.setText(text)
        self.append_log(f"{title}：{text}")
        if success:
            show_info(self, title, text)
        else:
            show_warning(self, title, text)

    def detect_device(self):
        self.set_running_status("正在运行：adb devices -l，检测设备连接状态...", busy=False)
        if not self.adb.is_available():
            self._set_status("ADB 状态", "未找到 adb", "red")
            self.set_result_status("未找到 adb", "NOT_AVAILABLE", "未找到 adb")
            return
        devices = self.adb.list_devices()
        if not devices:
            self._set_status("ADB 状态", "可用", "green")
            self._set_status("连接状态", "未检测到设备", "red")
            self.set_result_status("未检测到设备", "FAILED", "未检测到设备。请确认 USB 调试已开启。")
            return
        if len(devices) > 1:
            dialog = DeviceSelectDialog(devices, self)
            if dialog.exec():
                self.adb.set_serial(dialog.selected_serial())
            else:
                return
        else:
            self.adb.set_serial(devices[0]["serial"])
        state = next((d["state"] for d in devices if d["serial"] == self.adb.serial), "unknown")
        self._set_status("ADB 状态", "可用", "green")
        self._set_status("连接状态", state, "green" if state == "device" else "yellow")
        if state == "unauthorized":
            self.set_result_status("设备未授权", "FAILED", "unauthorized")
        elif state == "offline":
            self.set_result_status("设备离线", "FAILED", "offline")
        self._refresh_properties()
        self.set_result_status("检测完成", "SUCCESS", path=None)

    def _refresh_properties(self):
        root_raw = self.adb.quick_run(["shell", "id"], timeout=8)[1].strip()
        ip_raw = self.adb.quick_run(["shell", "ip", "addr"], timeout=10)[1]
        props = {
            "设备序列号": self.adb.serial or "",
            "Android 版本": self.adb.get_property("ro.build.version.release"),
            "SDK 版本": self.adb.get_property("ro.build.version.sdk"),
            "设备型号": self.adb.get_property("ro.product.model"),
            "品牌": self.adb.get_property("ro.product.brand"),
            "授权状态": self.adb.quick_run(["get-state"], timeout=5)[1].strip(),
            "root 状态（工程师）": self._root_summary(root_raw),
            "remount 状态（工程师）": "未执行 remount。普通客户无需关注；工程师需要写系统分区时再点 adb remount。",
            "连接方式": "网络 ADB" if self.adb.serial and ":" in self.adb.serial else "USB",
            "IP 摘要（网络）": self._ip_summary(ip_raw),
        }
        for key, value in props.items():
            self._set_status(key, str(value)[:240] or "未知", "green")

    @staticmethod
    def _root_summary(raw: str) -> str:
        if "uid=0" in raw:
            return "已 root：工程师可执行更多系统调试。普通客户无需操作。"
        if raw:
            return "普通权限：大多数客户设备都是这个状态；基础日志仍可抓取。"
        return "未检测到 root 状态：设备可能未连接或未授权。"

    @staticmethod
    def _ip_summary(raw: str) -> str:
        addresses = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("inet ") and "127.0.0.1" not in line:
                addresses.append(line.split()[1])
        if addresses:
            return "已获取 IP：" + ", ".join(addresses[:3])
        return "未看到有效 IP；如客户反馈联网问题，请抓取“网络状态”或完整诊断包。"

    def _set_status(self, key: str, value: str, color: str = "gray"):
        label = self.status_labels.get(key)
        if not label:
            return
        colors = {"green": "#137333", "yellow": "#b06000", "red": "#b3261e", "gray": "#5f6368"}
        label.setText(value)
        label.setStyleSheet(f"color: {colors.get(color, colors['gray'])};")

    def restart_adb(self):
        self.set_running_status("正在运行：adb kill-server / adb start-server，重启 ADB 服务...")
        self.adb.quick_run(["kill-server"], timeout=10, use_serial=False)
        code, output = self.adb.quick_run(["start-server"], timeout=10, use_serial=False)
        self._set_busy(False)
        self.append_log(output)
        self.set_result_status("重启 ADB 服务", "SUCCESS" if code == 0 else "FAILED", output)
        self.detect_device()

    def run_simple_adb(self, args: list[str], title: str):
        self.set_running_status(f"正在运行：adb {' '.join(args)}")

        def work():
            code, output = self.adb.quick_run(args, timeout=60, use_serial=args[0] not in {"connect", "disconnect", "pair"})
            return code, output

        self.worker = TaskWorker(work)
        self.worker.done.connect(lambda result: self.on_simple_adb_done(title, result))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def run_remount(self):
        self.set_running_status("正在运行：adb remount，并判断是否真正成功...")

        def work():
            code, output = self.adb.quick_run(["remount"], timeout=90)
            return code, output, evaluate_remount_result(code, output)

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_remount_done)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_remount_done(self, result):
        code, output, remount = result
        self._set_busy(False)
        self.append_log(output)
        color = "green" if remount.success else "red"
        self._set_status("remount 状态（工程师）", f"{remount.message} {remount.solution}", color)
        self.set_result_status("adb remount", "SUCCESS" if remount.success else "FAILED", output or remount.message)

    def on_simple_adb_done(self, title: str, result):
        code, output = result
        self._set_busy(False)
        self.append_log(output)
        self.set_result_status(title, "SUCCESS" if code == 0 else "FAILED", output)
        self.detect_device()

    def connect_remote(self):
        ip, port = self.connection_panel.endpoint()
        ok, message = ConnectionPanel.validate_endpoint(ip, port)
        if not ok:
            self.set_result_status("输入错误", "FAILED", message)
            return
        self.run_simple_adb(["connect", f"{ip}:{port}"], "ADB 远程连接")

    def disconnect_remote(self):
        ip, port = self.connection_panel.endpoint()
        if ip:
            ok, message = ConnectionPanel.validate_endpoint(ip, port)
            if not ok:
                self.set_result_status("输入错误", "FAILED", message)
                return
            args = ["disconnect", f"{ip}:{port}"]
        else:
            if QMessageBox.question(self, "确认断开", "未填写 IP，是否断开全部网络 ADB 连接？") != QMessageBox.Yes:
                return
            args = ["disconnect"]
        self.run_simple_adb(args, "ADB 远程断开")

    def pair_remote(self):
        ip, port, code = self.connection_panel.pair_endpoint()
        ok, message = ConnectionPanel.validate_endpoint(ip, port)
        if not ok or not code:
            self.set_result_status("输入错误", "FAILED", message or "配对码不能为空。")
            return
        self.run_simple_adb(["pair", f"{ip}:{port}", code], "ADB 远程配对")

    def start_diagnosis(self):
        dialog = CustomerInfoDialog(self)
        if not dialog.exec():
            return
        self.set_running_status("正在生成诊断包，请勿拔掉设备。")
        collector = LogCollector(self.adb, self.root)

        def progress(current, total, message):
            self.worker.progress.emit(current, total, message)

        self.worker = TaskWorker(collector.collect, dialog.data(), progress)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_diagnosis_done)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_progress(self, current: int, total: int, message: str):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.run_status.setStyleSheet("color: #b06000;")
        self.run_status.setText(f"正在运行：{message} ({current}/{total})")
        self.append_log(f"{current}/{total} {message}")

    def on_diagnosis_done(self, result):
        self.current_package, self.current_zip = result
        self._set_busy(False)
        self.progress.setValue(self.progress.maximum())
        self.set_result_status("诊断包生成成功", "SUCCESS", path=self.current_zip)
        open_in_explorer(self.current_zip)

    def capture_single_log(self):
        runner = CommandRunner(self.output_root / "single_log_command_status.json")
        collector = SingleLogCollector(self.adb, self.output_root)
        command_name = self.single_log_panel.selected_name()
        self.single_log_panel.set_running("正在运行：抓取历史/单项日志，请稍候...")

        def work():
            return collector.collect(command_name, runner)

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_single_log_done)
        self.worker.failed.connect(lambda msg: self.single_log_panel.set_failure("失败：工具执行异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.worker.start()

    def capture_history_logcat(self):
        self.capture_single_log()

    def on_single_log_done(self, result):
        command_result, output_path, analysis = result
        self.current_single_log_dir = output_path.parent
        analysis_text, conclusion, counts = self._format_analysis(output_path, analysis)
        detail = status_detail(command_result.status, command_result.error)
        if command_result.success:
            self.single_log_panel.set_success(f"{detail.message} 文件已保存。", analysis_text, conclusion, counts)
        else:
            self.single_log_panel.set_failure(f"{detail.message}\n{detail.solution}", analysis_text)

    def start_single_live_log(self):
        item = self.single_log_panel.selected_item()
        command = item.get("live_command")
        if not command:
            self.single_log_panel.set_failure("当前日志项不支持实时抓取。", "解决：请使用“抓取当前日志”，或切换到 Logcat、dmesg、4G 等支持实时抓取的日志项。")
            return
        name = sanitize_filename(str(item["name"]))
        self.current_single_log_dir = ensure_dir(self.output_root / "single_logs" / f"live_{name}_{timestamp()}")
        self.single_live_file = self.current_single_log_dir / f"live_{name}.txt"
        display_command = "adb " + quote_command(list(command))
        self.single_log_panel.set_live_status(f"正在运行：{display_command}\n保存到：{self.single_live_file}", True)
        self.single_live_worker = LiveLogWorker(self.adb, self.single_live_file, list(command), display_command)
        self.single_live_worker.line.connect(self.single_log_panel.append_live_line)
        self.single_live_worker.status.connect(self.single_log_panel.append_live_line)
        self.single_live_worker.start()

    def stop_single_live_log(self):
        if self.single_live_worker:
            self.single_live_worker.requestInterruption()
            self.single_live_worker.stop()
            self.single_live_worker.wait(2000)
            try:
                self.single_live_worker.line.disconnect(self.single_log_panel.append_live_line)
            except RuntimeError:
                pass
            try:
                self.single_live_worker.status.disconnect(self.single_log_panel.append_live_line)
            except RuntimeError:
                pass
            self.single_live_worker = None
        if self.single_live_file and self.single_live_file.exists():
            text = self.single_live_file.read_text(encoding="utf-8", errors="replace")
            analysis = analyze_log_text(text)
            analysis_text, conclusion, counts = self._format_analysis(self.single_live_file, analysis)
            self.single_log_panel.set_success("实时日志已暂停并完成简单分析。", analysis_text, conclusion, counts)
        else:
            self.single_log_panel.set_failure("实时抓取已暂停，但未生成日志文件。", "原因：设备可能未连接、未授权或日志命令未启动。\n解决：检测设备后重试。")

    def clear_device_logcat(self):
        item = self.single_log_panel.selected_item()
        command = item.get("clear_command")
        if not command:
            self.single_log_panel.set_failure("当前日志项不支持清除缓存。", "说明：设备属性、Activity 状态等快照型日志没有可清除缓存；请直接重新抓取。")
            return
        display_command = "adb " + quote_command(list(command))
        if QMessageBox.question(self, "确认清除日志", f"将执行 {display_command} 清除当前选中日志缓存。建议只在复现问题前使用，是否继续？") != QMessageBox.Yes:
            return
        self.single_log_panel.set_running(f"正在运行：{display_command}，清除设备日志缓存...")

        def work():
            return self.adb.quick_run(list(command), timeout=20)

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_clear_logcat_done)
        self.worker.failed.connect(lambda msg: self.single_log_panel.set_failure("清除失败：工具执行异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.worker.start()

    def on_clear_logcat_done(self, result):
        code, output = result
        if code == 0:
            self.single_log_panel.set_success("当前日志缓存已清除。现在复现问题，再抓取当前日志。", output or "清除成功。", "定位结论：等待复现后抓取", "关键字统计：暂无")
        else:
            detail = status_detail("FAILED", output)
            self.single_log_panel.set_failure(detail.message, f"{detail.solution}\n\nADB 输出：\n{output}")

    @staticmethod
    def _format_analysis(output_path: Path, analysis: dict[str, object]) -> tuple[str, str, str]:
        suggestions = "\n".join(f"- {item}" for item in analysis["suggestions"])
        evidence = "\n".join(f"- {item}" for item in analysis.get("evidence", [])) or "- 暂无明确证据。"
        analysis_text = (
            f"输出文件：{output_path}\n\n"
            f"定位结论：{analysis['conclusion']}\n"
            f"严重度：{analysis['severity']}\n\n"
            f"证据：\n{evidence}\n\n"
            f"下一步建议：\n{suggestions}"
        )
        conclusion = f"定位结论：{analysis['conclusion']}\n严重度：{analysis['severity']}"
        counts = (
            "关键字统计："
            f"Crash {analysis['crash_count']} / "
            f"ANR {analysis['anr_count']} / "
            f"权限 {analysis['permission_count']} / "
            f"超时 {analysis['timeout_count']} / "
            f"DNS {analysis.get('dns_count', 0)} / "
            f"网络 {analysis.get('network_count', 0)}"
        )
        return analysis_text, conclusion, counts

    def on_task_failed(self, message: str):
        self._set_busy(False)
        self.set_result_status("任务失败", "FAILED", message)

    def _set_busy(self, busy: bool):
        for button in [
            self.diagnose_button,
            self.detect_button,
            self.refresh_button,
            self.screenshot_panel.screenshot_button,
            self.screenshot_panel.record_button,
            self.file_panel.push_button,
            self.file_panel.pull_button,
        ]:
            button.setEnabled(not busy)

    def open_live_log(self):
        if not self.live_log_window:
            self.live_log_window = LiveLogWindow(self.adb, self.output_root)
        self.live_log_window.show()
        self.live_log_window.raise_()

    def open_adb_debug_window(self):
        if not self.adb_debug_window:
            self.adb_debug_window = AdbDebugWindow(self.adb, self.root)
        self.adb_debug_window.show()
        self.adb_debug_window.raise_()

    def start_screen_mirror(self):
        result = start_screen_mirror(self.root, self.adb.serial)
        self.set_direct_result_status("ADB 投屏", result.success, result.message, result.solution)

    def take_screenshot(self):
        self.set_running_status("正在运行：截屏 adb exec-out screencap -p")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return ScreenshotManager(self.adb, self.output_root).capture(runner)

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_screenshot_done)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_screenshot_done(self, path):
        self._set_busy(False)
        if path:
            pix = QPixmap(str(path))
            self.screenshot_panel.preview.setPixmap(pix.scaledToHeight(140))
            self.set_result_status("截屏成功", "SUCCESS", path=path)
        else:
            self.set_result_status("截屏失败", "FAILED", "设备未连接、未授权或不支持截屏命令。")

    def record_screen(self):
        seconds = self.screenshot_panel.record_seconds.value()
        self.set_running_status(f"正在运行：录制屏幕 {seconds} 秒，请勿拔掉设备。")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return ScreenshotManager(self.adb, self.output_root).record_screen(runner, seconds=seconds)

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_record_done)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_record_done(self, path):
        self._set_busy(False)
        if path:
            self.set_result_status("录屏成功", "SUCCESS", path=path)
        else:
            self.set_result_status("录屏失败", "UNSUPPORTED", "设备可能不支持 screenrecord，或当前连接/权限不足。")

    def push_file(self):
        local, target = self.file_panel.push_values()
        self.set_running_status(f"正在运行：adb push {local} {target}")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return FileTransfer(self.adb, self.output_root).push(runner, local, target)

        self.worker = TaskWorker(work)
        self.worker.done.connect(lambda result: self.on_transfer_done("推送文件", result))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def pull_file(self):
        device_path, local_dir = self.file_panel.pull_values()
        if not device_path:
            self.set_result_status("输入错误", "FAILED", "设备路径不能为空。")
            return
        self.set_running_status(f"正在运行：adb pull {device_path} {local_dir}")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return FileTransfer(self.adb, self.output_root).pull(runner, device_path, local_dir)

        self.worker = TaskWorker(work)
        self.worker.done.connect(lambda result: self.on_transfer_done("拉取文件", result))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_transfer_done(self, title: str, result):
        self._set_busy(False)
        self.set_result_status(title, result.status, result.error)

    def closeEvent(self, event):
        if self.live_log_window:
            self.live_log_window.stop()
        if self.single_live_worker:
            self.single_live_worker.requestInterruption()
            self.single_live_worker.stop()
        QApplication.closeAllWindows()
        super().closeEvent(event)
