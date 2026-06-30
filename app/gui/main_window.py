from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
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
from app.core.apk_installer import ApkInstallPlanQueue, BatchApkInstallQueue, ApkInstaller, TargetDeviceApkInstallQueue, parse_apk_file
from app.core.command_runner import CommandRunner
from app.core.file_transfer import FileTransfer
from app.core.log_collector import LogCollector
from app.core.network_adb import (
    DEFAULT_NETWORK_ADB_PORT,
    DeviceRecord,
    NetworkAdbScanner,
    NetworkRange,
    NetworkRangeStore,
    status_from_adb_state,
    suggested_current_network_ranges,
)
from app.core.screenshot_manager import ScreenshotManager
from app.core.screen_mirror import start_screen_mirror
from app.core.single_log_collector import SingleLogCollector, analyze_log_text
from app.core.remount_status import evaluate_remount_result
from app.core.status_messages import status_detail
from app.core.utils import app_base_dir, ensure_dir, open_file_default, open_in_explorer, quote_command, sanitize_filename, timestamp
from app.core.version import APP_WINDOW_TITLE
from app.gui.connection_panel import ConnectionPanel
from app.gui.adb_debug_window import AdbDebugWindow
from app.gui.apk_install_panel import ApkInstallPanel
from app.gui.dialogs import CustomerInfoDialog, DeviceSelectDialog, show_info, show_warning
from app.gui.feature_description_panel import FeatureDescriptionPanel
from app.gui.file_transfer_panel import FileTransferPanel
from app.gui.live_log_window import LiveLogWindow, LiveLogWorker
from app.gui.screenshot_panel import ScreenshotPanel
from app.gui.single_log_panel import SingleLogPanel
from app.gui.styles import (
    APP_PAGE_STYLE,
    MUTED_TEXT_STYLE,
    NAV_TABS_STYLE,
    PANEL_HINT_STYLE,
    RESULT_IDLE_STYLE,
    RESULT_SUCCESS_STYLE,
    STATUS_PILL_STYLE,
    app_icon,
    make_step_header,
    style_button,
    style_card,
)


class TaskWorker(QThread):
    _live_workers: set["TaskWorker"] = set()
    _sequence = 0

    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        type(self)._sequence += 1
        self.setObjectName(f"TaskWorker-{type(self)._sequence}:{getattr(func, '__name__', 'work')}")
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.finished.connect(self._release_self_reference)

    def start(self, priority=QThread.InheritPriority):
        type(self)._live_workers.add(self)
        super().start(priority)

    def _release_self_reference(self):
        type(self)._live_workers.discard(self)

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
        self.range_store = NetworkRangeStore(self.output_root / "network_ranges.json")
        self.current_package: Path | None = None
        self.current_zip: Path | None = None
        self.latest_apk_batch_log: Path | None = None
        self.current_single_log_dir = ensure_dir(self.output_root / "single_logs")
        self.worker: TaskWorker | None = None
        self.detect_worker: TaskWorker | None = None
        self.device_detail_worker: TaskWorker | None = None
        self.apk_batch_worker: TaskWorker | None = None
        self.live_log_window: LiveLogWindow | None = None
        self.live_log_windows: dict[str, LiveLogWindow] = {}
        self.adb_debug_windows: dict[str, AdbDebugWindow] = {}
        self.single_live_worker: LiveLogWorker | None = None
        self.single_live_file: Path | None = None
        self._auto_detail_refreshed_serials: set[str] = set()
        self._device_detail_show_result = True
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setWindowIcon(app_icon("adb", "#2563eb"))
        self.resize(1080, 760)
        self.setMinimumSize(640, 420)
        self._build_ui()
        self.connection_panel.set_recent_ranges(self.range_store.load())

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.setObjectName("mainTabs")
        tabs.setDocumentMode(True)
        tabs.tabBar().setMinimumHeight(48)
        tabs.tabBar().setIconSize(QSize(18, 18))
        tabs.setStyleSheet(NAV_TABS_STYLE)
        self.setCentralWidget(tabs)
        tab_specs = [
            (self._build_connection_page(), "device", "设备连接"),
            (self._build_diagnosis_page(), "diagnosis", "快速诊断"),
            (self._build_single_log_page(), "log", "单项日志 / 问题分析"),
            (self._build_apk_install_page(), "apk", "APK 安装"),
            (self._build_feature_page(), "info", "功能说明"),
        ]
        for widget, icon_name, label in tab_specs:
            index = tabs.addTab(self._scroll(widget), app_icon(icon_name, "#334155"), label)
            tabs.tabBar().setTabData(index, icon_name)
        self._connect_signals()
        self.append_log("工具已启动。请先在“设备连接”页选择：数据线连接、网络连接或网段扫描。")
        self._sync_target_action_enabled()

    def _scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll

    def _build_connection_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appPage")
        page.setStyleSheet(APP_PAGE_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)
        self.connection_panel = ConnectionPanel()
        layout.addWidget(self.connection_panel)
        return page

    def _build_diagnosis_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appPage")
        page.setStyleSheet(APP_PAGE_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)
        self.layout_priority = {}

        self.device_box = self._device_status_box()
        layout.addWidget(self.device_box)
        self.layout_priority["current_device"] = layout.indexOf(self.device_box)

        support = QWidget()
        support_layout = QVBoxLayout(support)
        support_layout.setContentsMargins(0, 0, 0, 0)
        support_layout.setSpacing(8)
        self.support_tools_section_title = make_step_header("3 辅助工具")
        support_layout.addWidget(self.support_tools_section_title)
        lower = QGridLayout()
        lower.setHorizontalSpacing(12)
        lower.setVerticalSpacing(12)
        self.screenshot_panel = ScreenshotPanel()
        self.file_panel = FileTransferPanel()
        lower.addWidget(self.screenshot_panel, 0, 0)
        lower.addWidget(self.file_panel, 0, 1)
        support_layout.addLayout(lower)
        layout.addWidget(support)
        self.layout_priority["support_tools"] = layout.indexOf(support)

        log_box = QFrame()
        style_card(log_box)
        log_layout = QVBoxLayout(log_box)
        self.runtime_log_section_title = make_step_header("4 运行提示 / 工具日志")
        buttons = QHBoxLayout()
        self.live_log_button = QPushButton("打开实时日志")
        self.open_output_button = QPushButton("打开导出目录")
        style_button(self.live_log_button, "secondary", "打开独立实时 logcat 窗口。", "log")
        style_button(self.open_output_button, "secondary", "打开 output 导出目录。", "folder")
        buttons.addWidget(self.runtime_log_section_title)
        buttons.addStretch(1)
        buttons.addWidget(self.live_log_button)
        buttons.addWidget(self.open_output_button)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        log_layout.addLayout(buttons)
        log_layout.addWidget(self.log)
        layout.addWidget(log_box)
        return page

    def _build_single_log_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appPage")
        page.setStyleSheet(APP_PAGE_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        self.single_log_target_combo = QComboBox()
        layout.addWidget(self._build_target_switcher("单项日志目标设备", self.single_log_target_combo))
        self.single_log_panel = SingleLogPanel()
        layout.addWidget(self.single_log_panel)
        return page

    def _build_apk_install_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appPage")
        page.setStyleSheet(APP_PAGE_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 18)
        self.apk_install_panel = ApkInstallPanel()
        layout.addWidget(self.apk_install_panel)
        return page

    def _build_feature_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("appPage")
        page.setStyleSheet(APP_PAGE_STYLE)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.addWidget(FeatureDescriptionPanel(), 0, Qt.AlignTop)
        return page

    def _build_target_switcher(self, title: str, combo: QComboBox) -> QFrame:
        box = QFrame()
        style_card(box)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(14, 10, 14, 10)
        label = QLabel(title)
        label.setStyleSheet("font-size: 14px; font-weight: 500; color: #111827;")
        hint = QLabel("切换后，本页操作会绑定到该设备。")
        hint.setStyleSheet(MUTED_TEXT_STYLE)
        combo.setMinimumWidth(320)
        combo.setToolTip("选择本页要操作的设备；只有“已可调试”设备可以执行操作。")
        layout.addWidget(label)
        layout.addWidget(combo)
        layout.addWidget(hint)
        layout.addStretch(1)
        return box

    def _device_status_box(self) -> QFrame:
        box = QFrame()
        style_card(box)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.status_labels = {}

        self.current_device_section_title = make_step_header("1 当前操作设备")
        layout.addWidget(self.current_device_section_title)

        top = QHBoxLayout()
        heading = QVBoxLayout()
        self.current_device_name = QLabel("当前未选择操作设备")
        self.current_device_name.setStyleSheet("font-size: 16px; font-weight: 500; color: #111827;")
        self.current_device_detail = QLabel("请先连接或扫描设备。")
        self.current_device_detail.setWordWrap(True)
        self.current_device_detail.setStyleSheet(MUTED_TEXT_STYLE)
        heading.addWidget(self.current_device_name)
        heading.addWidget(self.current_device_detail)
        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 4, 0, 0)
        target_label = QLabel("切换操作设备")
        target_label.setStyleSheet("color: #475569;")
        self.diagnosis_target_combo = QComboBox()
        self.diagnosis_target_combo.setMinimumWidth(320)
        self.diagnosis_target_combo.setToolTip("选择快速诊断页要操作的设备；只有“已可调试”设备可以执行操作。")
        target_row.addWidget(target_label)
        target_row.addWidget(self.diagnosis_target_combo)
        target_row.addStretch(1)
        heading.addLayout(target_row)
        self.current_device_state = QLabel("待连接")
        self.current_device_state.setStyleSheet(STATUS_PILL_STYLE)
        self.current_device_state.setMinimumHeight(30)
        top.addLayout(heading, 1)
        top.addWidget(self.current_device_state)
        layout.addLayout(top)

        self.quick_actions_section_title = make_step_header("2 常用操作")
        layout.addWidget(self.quick_actions_section_title)

        actions = QHBoxLayout()
        self.diagnose_button = QPushButton("一键生成诊断包")
        self.quick_mirror_button = QPushButton("ADB 投屏")
        self.quick_log_button = QPushButton("日志")
        self.detail_toggle_button = QPushButton("显示工程师详情")
        style_button(self.diagnose_button, "primary", "自动抓取完整诊断日志、截图和报告，并生成 zip。", "package")
        style_button(self.quick_mirror_button, "success", "对当前选中设备启动 scrcpy 实时投屏窗口。", "mirror")
        style_button(self.quick_log_button, "secondary", "打开独立实时 logcat 窗口。", "log")
        style_button(self.detail_toggle_button, "secondary", "展开 SDK、root、remount、IP 等工程师详情。", "list")
        actions.addWidget(self.detail_toggle_button)
        actions.addStretch(1)
        actions.addWidget(self.quick_log_button)
        actions.addWidget(self.quick_mirror_button)
        actions.addWidget(self.diagnose_button)
        layout.addLayout(actions)

        self.device_status_cards = []
        cards = QGridLayout()
        card_specs = [
            ("ADB 状态", "未检测"),
            ("连接状态", "未检测"),
            ("连接方式", "未检测"),
            ("设备型号", "未检测"),
        ]
        for index, (field, value) in enumerate(card_specs):
            card, label = self._summary_card(field, value)
            self.status_labels[field] = label
            self.device_status_cards.append(card)
            cards.addWidget(card, 0, index)
        layout.addLayout(cards)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.run_status = QLabel("待执行：请先检测或选择设备。")
        self.run_status.setWordWrap(True)
        self.run_status.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addWidget(self.progress)
        layout.addWidget(self.run_status)

        self.engineer_detail_frame = QFrame()
        self.engineer_detail_frame.setObjectName("engineerDetail")
        self.engineer_detail_frame.setStyleSheet("QFrame#engineerDetail { background: #fbfcfe; border: 1px solid #e1e7f0; border-radius: 7px; }")
        engineer_layout = QVBoxLayout(self.engineer_detail_frame)
        engineer_layout.setContentsMargins(12, 10, 12, 10)
        details = QGridLayout()
        fields = [
            "设备序列号",
            "Android 版本",
            "SDK 版本",
            "品牌",
            "授权状态",
            "root 状态（工程师）",
            "remount 状态（工程师）",
            "IP 摘要（网络）",
        ]
        for index, field in enumerate(fields):
            row = index // 2
            col = (index % 2) * 2
            name = QLabel(field)
            name.setStyleSheet("color: #5f6b7a;")
            details.addWidget(name, row, col)
            label = QLabel("未检测")
            label.setWordWrap(True)
            label.setStyleSheet("color: #1f2937;")
            self.status_labels[field] = label
            details.addWidget(label, row, col + 1)
        hint = QLabel(
            "说明：检测设备或切换到“已可调试”设备时会自动读取工程师详情。"
            "Android/SDK/型号/品牌来自 getprop，授权来自 adb get-state，root 来自 shell id，IP 摘要来自 shell ip addr。"
            "remount 只有工程师主动执行 adb remount 后才会更新；量产设备不支持通常是系统限制。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(PANEL_HINT_STYLE)
        engineer_layout.addLayout(details)
        engineer_layout.addWidget(hint)
        self.engineer_detail_frame.setVisible(False)
        layout.addWidget(self.engineer_detail_frame)
        return box

    @staticmethod
    def _summary_card(title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("summaryCard")
        card.setStyleSheet("QFrame#summaryCard { background: #f8fafc; border: 1px solid #e1e7f0; border-radius: 7px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #5f6b7a; font-size: 12px;")
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setStyleSheet("color: #111827; font-size: 14px; font-weight: 500;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def _connect_signals(self):
        self.diagnose_button.clicked.connect(self.start_diagnosis)
        self.quick_mirror_button.clicked.connect(self.start_screen_mirror)
        self.quick_log_button.clicked.connect(self.open_live_log)
        self.detail_toggle_button.clicked.connect(self.toggle_engineer_details)
        self.live_log_button.clicked.connect(self.open_live_log)
        self.open_output_button.clicked.connect(lambda: open_in_explorer(self.output_root))
        self.connection_panel.status_button.clicked.connect(self.detect_device)
        self.connection_panel.usb_refresh_button.clicked.connect(self.detect_device)
        self.connection_panel.restart_adb_button.clicked.connect(self.restart_adb)
        self.connection_panel.quick_scan_button.clicked.connect(self.scan_current_network)
        self.connection_panel.scan_range_button.clicked.connect(self.scan_configured_range)
        self.connection_panel.save_range_button.clicked.connect(self.save_scan_range)
        self.connection_panel.saved_ranges.currentIndexChanged.connect(self.connection_panel.apply_selected_range)
        self.connection_panel.device_table.itemSelectionChanged.connect(self.on_connection_device_selected)
        self.connection_panel.disconnect_device_requested.connect(self.disconnect_single_network_device)
        self.connection_panel.connect_button.clicked.connect(self.connect_remote)
        self.connection_panel.disconnect_button.clicked.connect(self.disconnect_remote)
        self.connection_panel.pair_button.clicked.connect(self.pair_remote)
        self.connection_panel.root_button.clicked.connect(lambda: self.run_simple_adb(["root"], "adb root"))
        self.connection_panel.remount_button.clicked.connect(lambda: self.run_simple_adb(["remount"], "adb remount"))
        self.connection_panel.remount_button.clicked.disconnect()
        self.connection_panel.remount_button.clicked.connect(self.run_remount)
        self.screenshot_panel.screenshot_button.clicked.connect(self.take_screenshot)
        self.screenshot_panel.view_screenshot_button.clicked.connect(self.open_latest_screenshot)
        self.screenshot_panel.preview.clicked.connect(self.open_latest_screenshot)
        self.screenshot_panel.open_screenshot_button.clicked.connect(lambda: open_in_explorer(self.output_root / "screenshots"))
        self.screenshot_panel.record_button.clicked.connect(self.record_screen)
        self.screenshot_panel.open_record_button.clicked.connect(lambda: open_in_explorer(self.output_root / "screenrecords"))
        self.file_panel.push_button.clicked.connect(self.push_file)
        self.file_panel.pull_button.clicked.connect(self.pull_file)
        self.single_log_panel.history_button.clicked.connect(self.capture_history_logcat)
        self.single_log_panel.start_live_button.clicked.connect(self.start_single_live_log)
        self.single_log_panel.stop_live_button.clicked.connect(self.stop_single_live_log)
        self.single_log_panel.clear_device_log_button.clicked.connect(self.clear_device_logcat)
        self.single_log_panel.open_button.clicked.connect(lambda: open_in_explorer(self.current_single_log_dir))
        self.diagnosis_target_combo.currentIndexChanged.connect(self.on_target_device_combo_changed)
        self.single_log_target_combo.currentIndexChanged.connect(self.on_target_device_combo_changed)
        self.apk_install_panel.file_selected.connect(self.prepare_apk_install)
        self.apk_install_panel.files_selected.connect(self.prepare_apk_install_batch)
        self.apk_install_panel.install_button.clicked.connect(self.install_apk)
        self.apk_install_panel.start_install_button.clicked.connect(self.install_apk_plan)
        self.apk_install_panel.install_targets_button.clicked.connect(self.install_apk_to_targets)
        self.apk_install_panel.retry_failed_targets_button.clicked.connect(self.retry_failed_apk_targets)
        self.apk_install_panel.start_batch_button.clicked.connect(self.install_apk_queue)
        self.apk_install_panel.retry_failed_button.clicked.connect(self.retry_failed_apk_queue)
        self.apk_install_panel.export_result_button.clicked.connect(self.export_apk_batch_result)
        self.apk_install_panel.open_button.clicked.connect(lambda: open_in_explorer(self.output_root / "apk_install"))

        self.adb_debug_button = QPushButton("打开 ADB 调试窗口")
        style_button(
            self.adb_debug_button,
            "engineer",
            "打开 FAE 调试窗口，直接执行 adb/shell 命令。",
            "terminal",
        )
        self.adb_debug_button.clicked.connect(self.open_adb_debug_window)
        self.device_box.layout().addWidget(self.adb_debug_button)

    def append_log(self, text: str):
        self.log.append(text)

    def _set_connection_devices(self, records: list[DeviceRecord]) -> None:
        self.connection_panel.set_devices(records)
        self.apk_install_panel.set_target_devices(records)
        self._sync_target_device_combos()
        self._sync_target_action_enabled()

    def _sync_apk_targets_from_connection_center(self) -> None:
        self.apk_install_panel.set_target_devices(self.connection_panel.records)

    def _target_device_combos(self) -> list[QComboBox]:
        combos: list[QComboBox] = []
        for name in ("diagnosis_target_combo", "single_log_target_combo"):
            combo = getattr(self, name, None)
            if combo is not None:
                combos.append(combo)
        return combos

    def _sync_target_device_combos(self) -> None:
        combos = self._target_device_combos()
        if not combos:
            return
        records = self.connection_panel.records
        current_serial = self.connection_panel.selected_serial() or self.adb.serial
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            if not records:
                combo.addItem("未选择设备", "")
                combo.setEnabled(False)
                combo.blockSignals(False)
                continue
            combo.setEnabled(True)
            for record in records:
                name = record.model or record.display_name() or "未知设备"
                combo.addItem(f"{name} / {record.serial} / {record.status}", record.serial)
            index = combo.findData(current_serial) if current_serial else -1
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def on_target_device_combo_changed(self) -> None:
        combo = self.sender()
        if not isinstance(combo, QComboBox):
            return
        serial = combo.currentData()
        if isinstance(serial, str) and serial:
            self._select_connection_row(serial)

    def _current_connection_record(self) -> DeviceRecord | None:
        serial = self.connection_panel.selected_serial() or self.adb.serial
        if not serial:
            return None
        return next((item for item in self.connection_panel.records if item.serial == serial), None)

    def _device_label(self, record: DeviceRecord) -> str:
        return f"{record.display_name()} / {record.serial}"

    def _target_action_buttons(self) -> list[QPushButton]:
        buttons = [
            self.diagnose_button,
            self.quick_mirror_button,
            self.quick_log_button,
            self.live_log_button,
            self.screenshot_panel.screenshot_button,
            self.screenshot_panel.record_button,
            self.file_panel.push_button,
            self.file_panel.pull_button,
        ]
        if hasattr(self, "adb_debug_button"):
            buttons.append(self.adb_debug_button)
        return buttons

    def _sync_target_action_enabled(self) -> None:
        if getattr(self, "_busy", False):
            return
        record = self._current_connection_record()
        enabled = bool(record and record.status == "已可调试")
        for button in self._target_action_buttons():
            button.setEnabled(enabled)

    def _require_debuggable_target(self, title: str) -> DeviceRecord | None:
        record = self._current_connection_record()
        if not record:
            self.set_result_status(title, "FAILED", "请先在“设备连接”页选择数据线连接、网络连接或网段扫描，并选中一台已可调试设备。")
            return None
        if record.status != "已可调试":
            self.set_result_status(title, "FAILED", f"当前选中设备状态为“{record.status}”，请先完成授权或重新检测后再操作。")
            return None
        self.adb.set_serial(record.serial)
        return record

    def toggle_engineer_details(self):
        visible = not self.engineer_detail_frame.isVisible()
        self.engineer_detail_frame.setVisible(visible)
        self.detail_toggle_button.setText("隐藏工程师详情" if visible else "显示工程师详情")

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
        self.set_running_status("正在运行：adb devices -l，快速检测设备连接状态...")
        self.detect_worker = TaskWorker(self._detect_device_snapshot)
        self.detect_worker.done.connect(self.on_device_detection_done)
        self.detect_worker.failed.connect(self.on_task_failed)
        self.detect_worker.start()

    def _detect_device_snapshot(self) -> dict[str, object]:
        if not self.adb.is_available():
            return {"adb_available": False, "devices": [], "records": [], "selected": None, "state": ""}
        devices = self.adb.list_devices()
        records = self._fast_device_records_from_adb(devices)
        selected = self._preferred_device(devices) if devices else None
        state = selected.get("state", "unknown") if selected else ""
        return {"adb_available": True, "devices": devices, "records": records, "selected": selected, "state": state}

    def on_device_detection_done(self, snapshot: dict[str, object]):
        self._set_busy(False)
        if not snapshot.get("adb_available"):
            self._set_status("ADB 状态", "未找到 adb", "red")
            self._set_connection_devices([])
            self.set_result_status("未找到 adb", "NOT_AVAILABLE", "未找到 adb")
            return

        devices = list(snapshot.get("devices") or [])
        records = list(snapshot.get("records") or [])
        self._set_connection_devices(records)
        if not devices:
            self._set_status("ADB 状态", "可用", "green")
            self._set_status("连接状态", "未检测到设备", "red")
            self.set_result_status("未检测到设备", "FAILED", "未检测到设备。请确认 USB 调试已开启。")
            return

        selected = snapshot.get("selected")
        if not isinstance(selected, dict):
            return
        self.adb.set_serial(selected.get("serial"))
        self._select_connection_row(self.adb.serial)
        state = str(snapshot.get("state") or "unknown")
        record = next((item for item in records if item.serial == self.adb.serial), None)
        self._set_status("ADB 状态", "可用", "green")
        self._set_status("连接状态", state, "green" if state == "device" else "yellow")
        self._set_status("设备序列号", self.adb.serial or "", "green" if state == "device" else "yellow")
        if record:
            self._set_status("连接方式", record.connection, "green")
            self.update_current_device_summary(record)

        if state != "device":
            if state == "unauthorized":
                self.set_result_status("设备未授权", "FAILED", "unauthorized")
            elif state == "offline":
                self.set_result_status("设备离线", "FAILED", "offline")
            else:
                self.set_result_status("设备不可用", "FAILED", state)
            return

        self.run_status.setStyleSheet("color: #b06000;")
        self.run_status.setText("已找到可调试设备，正在读取选中设备详情...")
        self._device_detail_show_result = True
        self.start_selected_device_detail_refresh(self.adb.serial)

    def _preferred_device(self, devices: list[dict[str, str]]) -> dict[str, str]:
        current = next((device for device in devices if device["serial"] == self.adb.serial), None)
        if current:
            return current
        ready = next((device for device in devices if device.get("state") == "device"), None)
        return ready or devices[0]

    def _fast_device_records_from_adb(self, devices: list[dict[str, str]]) -> list[DeviceRecord]:
        records: list[DeviceRecord] = []
        for device in devices:
            serial = device.get("serial", "")
            state = device.get("state", "unknown")
            connection = "网络 ADB 连接" if ":" in serial else "数据线连接"
            endpoint = serial if ":" in serial else ""
            raw = device.get("raw", "")
            model = self._raw_adb_field(raw, "model")
            brand = self._raw_adb_field(raw, "brand")
            records.append(
                DeviceRecord(
                    serial=serial,
                    status=status_from_adb_state(state),
                    connection=connection,
                    endpoint=endpoint,
                    model=model,
                    brand=brand,
                    raw=device.get("raw", ""),
                )
            )
        return records

    def _device_records_from_adb(self, devices: list[dict[str, str]]) -> list[DeviceRecord]:
        return self._fast_device_records_from_adb(devices)

    @staticmethod
    def _raw_adb_field(raw: str, key: str) -> str:
        prefix = f"{key}:"
        for part in raw.split():
            if part.startswith(prefix):
                return part[len(prefix) :]
        return ""

    def _select_connection_row(self, serial: str | None) -> None:
        if not serial:
            return
        for row, record in enumerate(self.connection_panel.records):
            if record.serial == serial:
                self.connection_panel.device_table.selectRow(row)
                return

    def on_connection_device_selected(self):
        serial = self.connection_panel.selected_serial()
        if not serial:
            return
        self.adb.set_serial(serial)
        record = next((item for item in self.connection_panel.records if item.serial == serial), None)
        if not record:
            return
        self._set_status("ADB 状态", "可用" if record.status == "已可调试" else "待验证", "green" if record.status == "已可调试" else "yellow")
        self._set_status("设备序列号", record.serial, "green" if record.status == "已可调试" else "yellow")
        self._set_status("连接状态", record.status, "green" if record.status == "已可调试" else "yellow")
        self._set_status("连接方式", record.connection, "green")
        if record.model:
            self._set_status("设备型号", record.model, "green")
        if record.brand:
            self._set_status("品牌", record.brand, "green")
        if record.android:
            self._set_status("Android 版本", record.android, "green")
        self.update_current_device_summary(record)
        self._sync_target_device_combos()
        self._sync_target_action_enabled()
        if self._needs_device_detail_refresh(record):
            self._auto_detail_refreshed_serials.add(record.serial)
            self._device_detail_show_result = False
            self.run_status.setStyleSheet("color: #b06000;")
            self.run_status.setText(f"正在自动读取 {record.display_name()} 的工程师详情...")
            self.start_selected_device_detail_refresh(record.serial)

    def _needs_device_detail_refresh(self, record: DeviceRecord) -> bool:
        if record.status != "已可调试":
            return False
        if record.serial in self._auto_detail_refreshed_serials:
            return False
        if not (record.model and record.brand and record.android):
            return True
        detail_keys = ("SDK 版本", "授权状态", "root 状态（工程师）", "IP 摘要（网络）")
        for key in detail_keys:
            label = self.status_labels.get(key)
            if label and label.text() in {"未检测", "未知"}:
                return True
        return False

    def start_selected_device_detail_refresh(self, serial: str | None):
        if not serial:
            return
        show_result = self._device_detail_show_result

        def work():
            adb = AdbManager(self.root, serial=serial)
            return self._read_device_properties(adb, serial)

        self.device_detail_worker = TaskWorker(work)
        self.device_detail_worker.done.connect(lambda props, show_result=show_result: self.on_device_detail_done(props, show_result))
        self.device_detail_worker.failed.connect(lambda msg: self.set_result_status("读取设备详情失败", "FAILED", msg))
        self.device_detail_worker.start()

    def _read_device_properties(self, adb: AdbManager, serial: str | None = None) -> dict[str, str]:
        root_raw = adb.quick_run(["shell", "id"], timeout=8)[1].strip()
        ip_raw = adb.quick_run(["shell", "ip", "addr"], timeout=10)[1]
        return {
            "设备序列号": serial or adb.serial or "",
            "Android 版本": adb.get_property("ro.build.version.release"),
            "SDK 版本": adb.get_property("ro.build.version.sdk"),
            "设备型号": adb.get_property("ro.product.model"),
            "品牌": adb.get_property("ro.product.brand"),
            "授权状态": adb.quick_run(["get-state"], timeout=5)[1].strip(),
            "root 状态（工程师）": self._root_summary(root_raw),
            "remount 状态（工程师）": "未执行 remount。普通客户无需关注；工程师需要写系统分区时再点 adb remount。",
            "连接方式": "网络 ADB 连接" if (serial or adb.serial or "").find(":") >= 0 else "数据线连接",
            "IP 摘要（网络）": self._ip_summary(ip_raw),
        }

    def on_device_detail_done(self, props: dict[str, str], show_result: bool = True):
        self._apply_device_properties(props)
        self._device_detail_show_result = True
        if show_result:
            self.set_result_status("检测完成", "SUCCESS", path=None)
        else:
            self.run_status.setStyleSheet("color: #137333;")
            self.run_status.setText("设备详情已自动更新。后续投屏、日志、截图、文件传输和 ADB 调试窗口会使用当前操作设备。")

    def _apply_device_properties(self, props: dict[str, str]):
        serial = props.get("设备序列号", self.adb.serial or "")
        if serial:
            self.adb.set_serial(serial)
        props = {
            **props,
        }
        for key, value in props.items():
            self._set_status(key, str(value)[:240] or "未知", "green")
        self._update_connection_record_from_props(props)
        self.update_current_device_summary()

    def _refresh_properties(self):
        self._apply_device_properties(self._read_device_properties(self.adb, self.adb.serial))

    def _update_connection_record_from_props(self, props: dict[str, str]):
        serial = props.get("设备序列号", "")
        if not serial:
            return
        updated: list[DeviceRecord] = []
        found = False
        for record in self.connection_panel.records:
            if record.serial == serial:
                found = True
                updated.append(
                    DeviceRecord(
                        serial=serial,
                        status=record.status,
                        connection=props.get("连接方式", record.connection) or record.connection,
                        endpoint=record.endpoint,
                        model=props.get("设备型号", record.model),
                        brand=props.get("品牌", record.brand),
                        android=props.get("Android 版本", record.android),
                        message=record.message,
                        raw=record.raw,
                    )
                )
            else:
                updated.append(record)
        if found:
            self._set_connection_devices(updated)
            self._select_connection_row(serial)

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

    def update_current_device_summary(self, record: DeviceRecord | None = None):
        if record:
            name = record.model or record.display_name()
            state = record.status
            detail_parts = [record.serial, record.connection]
            if record.android:
                detail_parts.append(f"Android {record.android}")
            self.current_device_name.setText(f"当前操作设备：{name or '未知设备'}")
            self.current_device_state.setText(state)
            self.current_device_detail.setText(" · ".join(part for part in detail_parts if part))
            return
        serial = self.status_labels.get("设备序列号").text() if self.status_labels.get("设备序列号") else ""
        model = self.status_labels.get("设备型号").text() if self.status_labels.get("设备型号") else ""
        android = self.status_labels.get("Android 版本").text() if self.status_labels.get("Android 版本") else ""
        state = self.status_labels.get("连接状态").text() if self.status_labels.get("连接状态") else ""
        connection = self.status_labels.get("连接方式").text() if self.status_labels.get("连接方式") else ""
        self.current_device_name.setText(f"当前操作设备：{model}" if model and model != "未检测" else "当前未选择操作设备")
        self.current_device_state.setText("已可调试" if state == "device" else (state or "待连接"))
        detail = " · ".join(part for part in [serial, connection, f"Android {android}" if android and android != "未检测" else ""] if part and part != "未检测")
        self.current_device_detail.setText(detail or "请先连接或扫描设备。")

    def restart_adb(self):
        self.set_running_status("正在运行：adb kill-server / adb start-server，重启 ADB 服务...")
        def work():
            _, kill_output = self.adb.quick_run(["kill-server"], timeout=15, use_serial=False)
            code, start_output = self.adb.quick_run(["start-server"], timeout=20, use_serial=False)
            return code, (kill_output + "\n" + start_output).strip()

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_restart_adb_done)
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_restart_adb_done(self, result):
        code, output = result
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

    def enable_network_debugging(self):
        self.set_result_status(
            "功能已调整",
            "FAILED",
            "本阶段已取消单独的网络调试端口入口。请在“设备连接”页使用“数据线连接”确认 USB 授权；需要网络连接时使用“网络连接”或“网段扫描”。",
        )

    def save_scan_range(self):
        ok, message, scan_range = self.connection_panel.scan_range_values()
        if not ok or scan_range is None:
            self.connection_panel.set_scan_status(message, "red")
            self.set_result_status("保存网段失败", "FAILED", message)
            return
        ranges = self.range_store.save_recent(scan_range)
        self.connection_panel.set_recent_ranges(ranges)
        self.connection_panel.set_scan_status(f"已保存常用网段：{scan_range.label()}", "green")

    def scan_current_network(self):
        port = self.connection_panel.scan_port.text().strip() or self.connection_panel.connect_port.text().strip() or DEFAULT_NETWORK_ADB_PORT
        ranges = suggested_current_network_ranges(port)
        if not ranges:
            self.connection_panel.set_scan_status("未识别到当前电脑的有效 IPv4 网段，请手动填写 IP 范围。", "red")
            self.set_result_status("扫描失败", "FAILED", "未识别到当前电脑的有效 IPv4 网段。")
            return
        scan_range = ranges[0]
        self.connection_panel.start_ip.setText(scan_range.start_ip)
        self.connection_panel.end_ip.setText(scan_range.end_ip)
        self.connection_panel.scan_port.setText(scan_range.port)
        self.start_network_scan(scan_range)

    def scan_configured_range(self):
        ok, message, scan_range = self.connection_panel.scan_range_values()
        if not ok or scan_range is None:
            self.connection_panel.set_scan_status(message, "red")
            self.set_result_status("扫描失败", "FAILED", message)
            return
        self.start_network_scan(scan_range)

    def start_network_scan(self, scan_range: NetworkRange):
        self.set_running_status(f"正在执行网段扫描：{scan_range.label()}")
        self.connection_panel.set_scan_status(f"正在扫描 {scan_range.label()}，可继续查看进度提示。", "yellow")

        def work():
            scanner = NetworkAdbScanner(self.adb)

            def progress(current, total, message):
                self.worker.progress.emit(current, total, message)

            return scanner.scan_range(scan_range, progress=progress)

        self.worker = TaskWorker(work)
        self.worker.progress.connect(self.on_network_scan_progress)
        self.worker.done.connect(lambda results: self.on_network_scan_done(scan_range, results))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_network_scan_progress(self, current: int, total: int, message: str):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.connection_panel.set_scan_status(f"{message} ({current}/{total})", "yellow")
        self.run_status.setStyleSheet("color: #b06000;")
        self.run_status.setText(f"{message} ({current}/{total})")

    def on_network_scan_done(self, scan_range: NetworkRange, results):
        self._set_busy(False)
        verified = [result.as_device_record() for result in results if result.adb_verified]
        candidates = [result.as_device_record() for result in results if not result.adb_verified]
        self.connection_panel.add_or_update_devices([*verified, *candidates])
        self._sync_apk_targets_from_connection_center()
        self.range_store.save_recent(scan_range)
        self.connection_panel.set_recent_ranges(self.range_store.load())
        if verified:
            self.adb.set_serial(verified[0].serial)
            self._select_connection_row(verified[0].serial)
            self.connection_panel.set_scan_status(f"扫描完成：已确认 {len(verified)} 台可调试设备。", "green")
            self.set_direct_result_status("网段扫描完成", True, f"已确认 {len(verified)} 台网络 ADB 设备可调试。", "请选择设备后执行投屏、日志、APK 安装或诊断。")
        elif candidates:
            self.connection_panel.set_scan_status(f"扫描完成：发现 {len(candidates)} 个候选地址，但未确认可调试。", "yellow")
            self.set_direct_result_status("网段扫描完成", False, "发现候选地址，但未确认可调试。", "请确认设备网络 ADB 端口可访问，并在设备屏幕允许 USB 调试。")
        else:
            self.connection_panel.set_scan_status("扫描完成：未发现可连接设备。", "red")
            self.set_direct_result_status("网段扫描完成", False, "未发现可连接设备。", "请确认设备和电脑在同一局域网，或使用无线配对后再连接。")

    def connect_remote(self):
        ip, port = self.connection_panel.endpoint()
        ok, message = ConnectionPanel.validate_endpoint(ip, port)
        if not ok:
            self.set_result_status("输入错误", "FAILED", message)
            return
        self.run_simple_adb(["connect", f"{ip}:{port}"], "连接网络 ADB 设备")

    def disconnect_remote(self):
        network_count = sum(1 for record in self.connection_panel.records if self._is_network_device(record))
        message = "将断开全部网络 ADB 连接。单台网络设备请在设备列表行内点击“断开”。"
        if network_count:
            message = f"将断开 {network_count} 台已记录的网络 ADB 设备，以及 adb server 中可能存在的其他网络连接。是否继续？"
        if QMessageBox.question(self, "确认断开全部网络设备", message) != QMessageBox.Yes:
            return
        self.run_simple_adb(["disconnect"], "断开全部网络 ADB 设备")

    def disconnect_single_network_device(self, serial: str):
        record = next((item for item in self.connection_panel.records if item.serial == serial), None)
        if not record or not self._is_network_device(record):
            self.set_result_status("无法断开数据线设备", "FAILED", "数据线设备不能通过 adb disconnect 断开；请拔掉数据线、关闭 USB 调试或在设备上撤销授权。")
            return
        self.run_simple_adb(["disconnect", serial], "断开单台网络 ADB 设备")

    @staticmethod
    def _is_network_device(record: DeviceRecord) -> bool:
        return record.connection == "网络 ADB 连接"

    def pair_remote(self):
        ip, port, code = self.connection_panel.pair_endpoint()
        ok, message = ConnectionPanel.validate_endpoint(ip, port)
        if not ok or not code:
            self.set_result_status("输入错误", "FAILED", message or "配对码不能为空。")
            return
        self.run_simple_adb(["pair", f"{ip}:{port}", code], "ADB 远程配对")

    def start_diagnosis(self):
        record = self._require_debuggable_target("无法生成诊断包")
        if not record:
            return
        dialog = CustomerInfoDialog(self)
        if not dialog.exec():
            return
        self.set_running_status(f"正在为 {self._device_label(record)} 生成诊断包，请勿拔掉设备。")
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
        self.single_log_panel.set_running("正在运行：导出已缓存/单项日志，请稍候...")

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
            self.single_log_panel.set_failure("当前日志项不支持实时抓取。", "解决：请使用“导出已缓存日志”，或切换到 Logcat、dmesg、4G 等支持实时抓取的日志项。")
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
        self.single_log_panel.set_running("正在停止抓取并分析日志，请稍候...")
        log_file = self.single_live_file

        def work():
            if not log_file or not log_file.exists():
                return None
            text = log_file.read_text(encoding="utf-8", errors="replace")
            analysis = analyze_log_text(text)
            analysis_text, conclusion, counts = self._format_analysis(log_file, analysis)
            return analysis_text, conclusion, counts

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_single_live_analysis_done)
        self.worker.failed.connect(lambda msg: self.single_log_panel.set_failure("分析失败：工具执行异常。", f"原因：{msg}\n解决：确认日志文件可读取后重试。"))
        self.worker.start()

    def on_single_live_analysis_done(self, payload):
        if payload:
            analysis_text, conclusion, counts = payload
            self.single_log_panel.set_success("持续抓取已停止，并已完成简单分析。", analysis_text, conclusion, counts)
        else:
            self.single_log_panel.set_failure("持续抓取已停止，但未生成日志文件。", "原因：设备可能未连接、未授权或日志命令未启动。\n解决：检测设备后重试。")

    def clear_device_logcat(self):
        item = self.single_log_panel.selected_item()
        command = item.get("clear_command")
        if not command:
            self.single_log_panel.set_failure("当前日志项不支持清除缓存。", "说明：设备属性、Activity 状态等快照型日志没有可清除缓存；请直接重新抓取。")
            return
        display_command = "adb " + quote_command(list(command))
        if QMessageBox.question(
            self,
            "确认清除设备日志缓存",
            f"将执行 {display_command}。\n\n该操作会清空设备当前日志缓存，旧日志清空后无法再导出。只有明确要丢弃旧日志并重新采集时才建议继续。\n\n是否继续？",
        ) != QMessageBox.Yes:
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
            self.single_log_panel.set_success("当前日志缓存已清除。现在复现问题，再导出已缓存日志或开始持续抓取。", output or "清除成功。", "定位结论：等待复现后抓取", "关键字统计：暂无")
        else:
            detail = status_detail("FAILED", output)
            self.single_log_panel.set_failure(detail.message, f"{detail.solution}\n\nADB 输出：\n{output}")

    def prepare_apk_install(self, path_text: str):
        source = Path(path_text)
        if not source.exists() or not source.is_file():
            self.apk_install_panel.set_failure("失败：文件不存在。", "解决：重新选择 APK 文件，或确认拖拽的是本地文件。")
            return
        if ".apk" not in source.name.lower():
            self.apk_install_panel.set_failure(
                "失败：未识别到 APK 文件名。",
                "解决：请选择包含 .apk 的文件；如果客户文件名异常，例如 1.apk(1).1，软件会自动识别。",
            )
            return
        self.apk_install_panel.set_running("正在解析 APK 信息，请稍候...")

        def work():
            return parse_apk_file(source, self.output_root / "apk_install" / "temp")

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_apk_prepared)
        self.worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("失败：APK 解析异常。", f"原因：{msg}\n解决：重新获取 APK 后重试。"))
        self.worker.start()

    def on_apk_prepared(self, apk_info):
        self.apk_install_panel.set_apk_info(apk_info)

    def prepare_apk_install_batch(self, path_texts: list[str]):
        sources = [Path(path) for path in path_texts]
        valid_sources = [path for path in sources if path.exists() and path.is_file() and ".apk" in path.name.lower()]
        if not valid_sources:
            self.apk_install_panel.set_failure("失败：未找到可用 APK。", "解决：请选择 APK 文件，或选择包含 APK 的文件夹。")
            return
        self.apk_install_panel.set_running(f"正在解析 {len(valid_sources)} 个 APK，请稍候...")

        def work():
            return [parse_apk_file(source, self.output_root / "apk_install" / "temp") for source in valid_sources]

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_apk_batch_prepared)
        self.worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("失败：批量 APK 解析异常。", f"原因：{msg}\n解决：重新获取 APK 后重试。"))
        self.worker.start()

    def on_apk_batch_prepared(self, apk_infos):
        if not apk_infos:
            self.apk_install_panel.set_failure("失败：未解析到 APK。", "解决：重新选择 APK 文件后重试。")
            return
        self.apk_install_panel.set_apk_info(apk_infos[0])
        for apk_info in apk_infos[1:]:
            self.apk_install_panel.add_apk_info(apk_info)
        self.apk_install_panel.result.setStyleSheet(RESULT_SUCCESS_STYLE)
        self.apk_install_panel.result.setText(f"已加入待安装列表：{len(self.apk_install_panel.apk_queue)} 个 APK。确认目标设备后点击“开始安装”。")

    def install_apk(self):
        apk_info = self.apk_install_panel.current_apk
        if not apk_info:
            self.apk_install_panel.set_failure("失败：未选择 APK。", "解决：请先选择或拖拽 APK 文件。")
            return
        self.apk_install_panel.set_running("正在运行：adb install，请勿拔掉设备...")

        def work():
            result = ApkInstaller(self.adb, self.output_root).install(apk_info, self.apk_install_panel.options())
            log_dir = ensure_dir(self.output_root / "apk_install")
            log_path = log_dir / "apk_install_output.txt"
            log_path.write_text(
                f"APK: {apk_info.original_path}\n安装文件: {apk_info.install_path}\n包名: {apk_info.package_name}\n"
                f"版本: {apk_info.version_name} ({apk_info.version_code})\n\n{result.output}",
                encoding="utf-8",
                errors="replace",
            )
            return result

        self.worker = TaskWorker(work)
        self.worker.done.connect(self.on_apk_install_done)
        self.worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("安装失败：工具执行异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.worker.start()

    def on_apk_install_done(self, result):
        self.apk_install_panel.set_result(result.success, result.message, result.solution, result.output)

    def install_apk_plan(self):
        apk_infos = list(self.apk_install_panel.apk_queue)
        if not apk_infos:
            self.apk_install_panel.set_failure("失败：未选择 APK。", "解决：请先选择、拖拽 APK，或选择包含 APK 的文件夹。")
            return
        targets = self.apk_install_panel.selected_target_records()
        if not targets:
            self.apk_install_panel.set_failure("失败：未选择安装目标。", "解决：请先勾选一台或多台已可调试设备。")
            return
        not_ready = [target for target in targets if target.status != "已可调试"]
        if not_ready:
            names = "、".join(target.serial for target in not_ready[:3])
            self.apk_install_panel.set_failure(
                "失败：存在未就绪目标设备。",
                f"解决：请先检测设备并确认状态为“已可调试”。未就绪设备：{names}",
            )
            return
        options = self.apk_install_panel.options()
        stop_on_failure = self.apk_install_panel.stop_on_failure_check.isChecked()
        total = len(apk_infos) * len(targets)
        self.apk_install_panel.set_running(f"正在执行安装任务：共 {total} 项，请勿拔掉数据线或断开网络 ADB 连接...")

        def work():
            summary = ApkInstallPlanQueue(self.adb, self.output_root).install_all(
                apk_infos,
                targets,
                options,
                stop_on_failure=stop_on_failure,
            )
            log_dir = ensure_dir(self.output_root / "apk_install")
            log_path = log_dir / f"apk_install_plan_{timestamp()}.txt"
            lines = [
                f"APK 安装任务：{len(apk_infos)} 个 APK x {len(targets)} 台设备 = {total} 项",
                "",
            ]
            for record in summary.results:
                lines.extend(
                    [
                        f"[{record.index}/{summary.total}] {record.apk_info.original_path.name} -> {record.target.display_name()}",
                        f"APK: {record.apk_info.original_path}",
                        f"包名: {record.apk_info.package_name or '未解析'}",
                        f"设备: {record.target.serial}",
                        f"连接方式: {record.target.connection}",
                        f"结果: {'成功' if record.result.success else '失败'}",
                        f"说明: {record.result.message}",
                        f"建议: {record.result.solution}",
                        "ADB 输出:",
                        record.result.output,
                        "",
                    ]
                )
            log_path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
            return summary, log_path

        self.apk_batch_worker = TaskWorker(work)
        self.apk_batch_worker.done.connect(lambda payload: self.on_apk_plan_done(payload, apk_infos, targets))
        self.apk_batch_worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("安装失败：任务异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.apk_batch_worker.start()

    def on_apk_plan_done(self, payload, apk_infos, targets):
        summary, log_path = payload
        self.latest_apk_batch_log = log_path
        self.apk_install_panel.failed_queue = []
        self.apk_install_panel.failed_target_devices = []

        for row, apk_info in enumerate(apk_infos):
            apk_records = [record for record in summary.results if record.apk_info == apk_info]
            apk_success = len(apk_records) == len(targets) and all(record.result.success for record in apk_records)
            if not apk_success:
                self.apk_install_panel.failed_queue.append(apk_info)
            message = f"成功 {sum(1 for record in apk_records if record.result.success)} / {len(targets)}"
            self.apk_install_panel.mark_queue_result(row, apk_success, message)

        for target in targets:
            target_records = [record for record in summary.results if record.target.serial == target.serial]
            target_success = len(target_records) == len(apk_infos) and all(record.result.success for record in target_records)
            if not target_success:
                self.apk_install_panel.failed_target_devices.append(target)
            message = f"成功 {sum(1 for record in target_records if record.result.success)} / {len(apk_infos)}"
            self.apk_install_panel.mark_target_result(target.serial, target_success, message)

        installed_count = len(summary.results)
        stopped = installed_count < summary.total
        success = summary.failure_count == 0 and installed_count == summary.total
        message = f"安装完成：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        if stopped:
            message = f"安装已停止：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        solution = f"日志位置：{log_path}"
        if summary.failure_count:
            solution += "\n失败项可点击“重试失败设备”，或查看安装输出定位原因。"
        else:
            solution += "\n无需处理。"
        output = log_path.read_text(encoding="utf-8", errors="replace")
        self.apk_install_panel.set_result(success, message, solution, output)
        self.apk_install_panel.retry_failed_button.setEnabled(bool(self.apk_install_panel.failed_queue))
        self.apk_install_panel.retry_failed_targets_button.setEnabled(bool(self.apk_install_panel.failed_target_devices))
        self.apk_install_panel.export_result_button.setEnabled(True)
        self.apk_install_panel.export_result_button.show()
        self.apk_install_panel._update_target_buttons()

    def install_apk_to_targets(self):
        apk_info = self.apk_install_panel.current_apk
        if not apk_info:
            self.apk_install_panel.set_failure("失败：未选择 APK。", "解决：请先选择或拖拽一个 APK 文件。")
            return
        targets = self.apk_install_panel.selected_target_records()
        if not targets:
            self.apk_install_panel.set_failure("失败：未选择安装目标。", "解决：请先勾选一台或多台已可调试设备。")
            return
        not_ready = [target for target in targets if target.status != "已可调试"]
        if not_ready:
            names = "、".join(target.serial for target in not_ready[:3])
            self.apk_install_panel.set_failure(
                "失败：存在未就绪目标设备。",
                f"解决：请先检测设备并确认状态为“已可调试”。未就绪设备：{names}",
            )
            return
        options = self.apk_install_panel.options()
        stop_on_failure = self.apk_install_panel.stop_on_failure_check.isChecked()
        self.apk_install_panel.set_running(f"正在安装到 {len(targets)} 台设备，请勿拔掉数据线或断开网络 ADB 连接...")

        def work():
            summary = TargetDeviceApkInstallQueue(self.adb, self.output_root).install_to_targets(
                apk_info,
                targets,
                options,
                stop_on_failure=stop_on_failure,
            )
            log_dir = ensure_dir(self.output_root / "apk_install")
            log_path = log_dir / f"target_install_{timestamp()}.txt"
            lines = [
                f"目标设备安装任务：1 个 APK -> {len(targets)} 台设备",
                f"APK: {apk_info.original_path}",
                f"安装文件: {apk_info.install_path}",
                f"包名: {apk_info.package_name or '未解析'}",
                f"版本: {apk_info.version_name or '未解析'} ({apk_info.version_code or '未解析'})",
                "",
            ]
            for record in summary.results:
                lines.extend(
                    [
                        f"[{record.index}/{summary.total}] {record.target.display_name()}",
                        f"序列号/IP: {record.target.serial}",
                        f"连接方式: {record.target.connection}",
                        f"结果: {'成功' if record.result.success else '失败'}",
                        f"说明: {record.result.message}",
                        f"建议: {record.result.solution}",
                        "ADB 输出:",
                        record.result.output,
                        "",
                    ]
                )
            log_path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
            return summary, log_path

        self.apk_batch_worker = TaskWorker(work)
        self.apk_batch_worker.done.connect(self.on_apk_targets_done)
        self.apk_batch_worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("安装失败：目标设备任务异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.apk_batch_worker.start()

    def on_apk_targets_done(self, payload):
        summary, log_path = payload
        self.latest_apk_batch_log = log_path
        self.apk_install_panel.failed_target_devices = [record.target for record in summary.results if not record.result.success]
        for record in summary.results:
            self.apk_install_panel.mark_target_result(record.target.serial, record.result.success, record.result.message)
        installed_count = len(summary.results)
        stopped = installed_count < summary.total
        success = summary.failure_count == 0 and installed_count == summary.total
        message = f"目标设备安装完成：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        if stopped:
            message = f"目标设备安装已停止：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        solution = f"日志位置：{log_path}"
        if summary.failure_count:
            solution += "\n失败设备可点击“重试失败设备”，或查看安装输出定位原因。"
        else:
            solution += "\n无需处理。"
        output = log_path.read_text(encoding="utf-8", errors="replace")
        self.apk_install_panel.set_result(success, message, solution, output)
        self.apk_install_panel.retry_failed_targets_button.setEnabled(bool(self.apk_install_panel.failed_target_devices))
        self.apk_install_panel.export_result_button.setEnabled(True)
        self.apk_install_panel.export_result_button.show()
        self.apk_install_panel._update_target_buttons()

    def retry_failed_apk_targets(self):
        if not self.apk_install_panel.failed_queue and not self.apk_install_panel.failed_target_devices:
            self.apk_install_panel.set_failure("没有失败项可重试。", "解决：先执行一次安装，或重新选择 APK 和设备。")
            return
        if self.apk_install_panel.failed_queue:
            self.apk_install_panel.set_queue(self.apk_install_panel.failed_queue)
        if self.apk_install_panel.failed_target_devices:
            failed_serials = {record.serial for record in self.apk_install_panel.failed_target_devices}
            self.apk_install_panel._set_target_checks(lambda record: record.serial in failed_serials)
        self.install_apk_plan()

    def install_apk_queue(self):
        apk_infos = list(self.apk_install_panel.apk_queue)
        if not apk_infos:
            self.apk_install_panel.set_failure("失败：安装队列为空。", "解决：请先选择一个或多个 APK。")
            return
        self.apk_install_panel.set_running(f"正在安装队列：共 {len(apk_infos)} 个 APK，请勿拔掉设备...")

        def work():
            summary = BatchApkInstallQueue(self.adb, self.output_root).install_all(
                apk_infos,
                self.apk_install_panel.options(),
                stop_on_failure=self.apk_install_panel.stop_on_failure_check.isChecked(),
            )
            log_dir = ensure_dir(self.output_root / "apk_install")
            log_path = log_dir / f"batch_install_{timestamp()}.txt"
            lines = [f"批量安装任务：{len(apk_infos)} 个 APK", ""]
            for record in summary.results:
                lines.extend(
                    [
                        f"[{record.index}/{summary.total}] {record.apk_info.original_path}",
                        f"包名: {record.apk_info.package_name or '未解析'}",
                        f"结果: {'成功' if record.result.success else '失败'}",
                        f"说明: {record.result.message}",
                        f"建议: {record.result.solution}",
                        "ADB 输出:",
                        record.result.output,
                        "",
                    ]
                )
            log_path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
            return summary, log_path

        self.apk_batch_worker = TaskWorker(work)
        self.apk_batch_worker.done.connect(self.on_apk_queue_done)
        self.apk_batch_worker.failed.connect(lambda msg: self.apk_install_panel.set_failure("安装失败：批量任务异常。", f"原因：{msg}\n解决：确认设备连接和 ADB 授权后重试。"))
        self.apk_batch_worker.start()

    def on_apk_queue_done(self, payload):
        summary, log_path = payload
        self.latest_apk_batch_log = log_path
        self.apk_install_panel.failed_queue = [record.apk_info for record in summary.results if not record.result.success]
        for record in summary.results:
            self.apk_install_panel.mark_queue_result(record.index - 1, record.result.success, record.result.message)
        installed_count = len(summary.results)
        stopped = installed_count < summary.total
        success = summary.failure_count == 0 and installed_count == summary.total
        message = f"批量安装完成：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        if stopped:
            message = f"批量安装已停止：成功 {summary.success_count}，失败 {summary.failure_count}，已执行 {installed_count}/{summary.total}。"
        solution = f"日志位置：{log_path}"
        if summary.failure_count:
            solution += "\n失败项可点击“重试失败”，或查看安装输出定位原因。"
        else:
            solution += "\n无需处理。"
        output = log_path.read_text(encoding="utf-8", errors="replace")
        self.apk_install_panel.set_result(success, message, solution, output)
        self.apk_install_panel.retry_failed_button.setEnabled(bool(self.apk_install_panel.failed_queue))
        self.apk_install_panel.export_result_button.setEnabled(True)
        self.apk_install_panel.export_result_button.show()

    def retry_failed_apk_queue(self):
        if not self.apk_install_panel.failed_queue:
            self.apk_install_panel.set_failure("没有失败项可重试。", "解决：先执行安装队列，或重新选择 APK。")
            return
        self.apk_install_panel.set_queue(self.apk_install_panel.failed_queue)
        self.install_apk_queue()

    def export_apk_batch_result(self):
        if not self.latest_apk_batch_log or not self.latest_apk_batch_log.exists():
            self.apk_install_panel.set_failure("没有可导出的批量安装结果。", "解决：先执行一次安装队列。")
            return
        open_in_explorer(self.latest_apk_batch_log)
        self.apk_install_panel.result.setStyleSheet(RESULT_SUCCESS_STYLE)
        self.apk_install_panel.result.setText(f"批量安装结果已生成。\n文件位置：{self.latest_apk_batch_log}")

    @staticmethod
    def _format_analysis(output_path: Path, analysis: dict[str, object]) -> tuple[str, str, str]:
        suggestions = "\n".join(f"- {item}" for item in analysis["suggestions"])
        evidence = "\n".join(f"- {item}" for item in analysis.get("evidence", [])) or "- 暂无明确证据。"
        cache_note = (
            "缓存说明：该日志可能包含设备已缓存日志以及本次抓取期间新增日志；"
            "发现的 crash/ANR/权限/网络线索需要结合客户反馈的问题发生时间判断是否相关。\n\n"
        )
        analysis_text = (
            f"输出文件：{output_path}\n\n"
            f"{cache_note}"
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
        if self.screenshot_panel.progress.maximum() == 0:
            self.screenshot_panel.set_result(False, f"操作失败：{message}")
        if self.file_panel.progress.maximum() == 0:
            self.file_panel.set_result(False, f"传输失败：{message}")
        self.set_result_status("任务失败", "FAILED", message)

    def _set_busy(self, busy: bool):
        self._busy = busy
        buttons = [
            self.diagnose_button,
            self.quick_mirror_button,
            self.quick_log_button,
            self.detail_toggle_button,
            self.live_log_button,
            self.open_output_button,
            self.connection_panel.status_button,
            self.connection_panel.usb_refresh_button,
            self.connection_panel.restart_adb_button,
            self.connection_panel.quick_scan_button,
            self.connection_panel.scan_range_button,
            self.connection_panel.save_range_button,
            self.connection_panel.connect_button,
            self.connection_panel.disconnect_button,
            self.connection_panel.pair_button,
            self.connection_panel.root_button,
            self.connection_panel.remount_button,
            self.screenshot_panel.screenshot_button,
            self.screenshot_panel.record_button,
            self.screenshot_panel.view_screenshot_button,
            self.screenshot_panel.open_screenshot_button,
            self.screenshot_panel.open_record_button,
            self.file_panel.push_button,
            self.file_panel.pull_button,
            self.single_log_panel.history_button,
            self.single_log_panel.start_live_button,
            self.single_log_panel.clear_device_log_button,
            self.single_log_panel.open_button,
            self.apk_install_panel.choose_button,
            self.apk_install_panel.choose_many_button,
            self.apk_install_panel.choose_folder_button,
            self.apk_install_panel.clear_button,
            self.apk_install_panel.open_button,
            self.apk_install_panel.select_debuggable_targets_button,
            self.apk_install_panel.clear_targets_button,
            self.apk_install_panel.start_install_button,
            self.apk_install_panel.install_targets_button,
            self.apk_install_panel.retry_failed_targets_button,
            self.apk_install_panel.start_batch_button,
            self.apk_install_panel.retry_failed_button,
            self.apk_install_panel.export_result_button,
        ]
        if hasattr(self, "adb_debug_button"):
            buttons.append(self.adb_debug_button)
        for button in buttons:
            button.setEnabled(not busy)
        for combo in self._target_device_combos():
            combo.setEnabled(not busy and combo.count() > 0 and bool(combo.currentData()))
        self.connection_panel.device_table.setEnabled(not busy)
        if not busy:
            self.screenshot_panel.set_screenshot_path(self.screenshot_panel.current_screenshot_path)
        self.apk_install_panel.install_button.setEnabled(not busy and self.apk_install_panel.current_apk is not None)
        self.apk_install_panel.start_batch_button.setEnabled(not busy and bool(self.apk_install_panel.apk_queue))
        self.apk_install_panel.retry_failed_button.setEnabled(not busy and bool(self.apk_install_panel.failed_queue))
        self.apk_install_panel.export_result_button.setEnabled(not busy and bool(self.apk_install_panel.apk_queue))
        if not busy:
            self.apk_install_panel._update_target_buttons()
            self._sync_target_action_enabled()

    def open_live_log(self):
        record = self._require_debuggable_target("无法打开实时日志")
        if not record:
            return
        window = self.live_log_windows.get(record.serial)
        if window is None:
            window = LiveLogWindow(AdbManager(self.root, serial=record.serial), self.output_root, self._device_label(record))
            self.live_log_windows[record.serial] = window
        self.live_log_window = window
        self.live_log_window.show()
        self.live_log_window.raise_()

    def open_adb_debug_window(self):
        record = self._require_debuggable_target("无法打开 ADB 调试窗口")
        if not record:
            return
        device_label = self._device_label(record)
        window = self.adb_debug_windows.get(record.serial)
        if window is None:
            window = AdbDebugWindow(AdbManager(self.root, serial=record.serial), self.root, device_label)
            self.adb_debug_windows[record.serial] = window
        window.show()
        window.raise_()

    def start_screen_mirror(self):
        record = self._require_debuggable_target("无法启动 ADB 投屏")
        if not record:
            return
        result = start_screen_mirror(self.root, self.adb.serial)
        self.set_direct_result_status("ADB 投屏", result.success, f"目标设备：{self._device_label(record)}\n{result.message}", result.solution)

    def take_screenshot(self):
        record = self._require_debuggable_target("无法截屏")
        if not record:
            return
        self.set_running_status(f"正在为 {self._device_label(record)} 截屏：adb exec-out screencap -p")
        self.screenshot_panel.set_running(f"目标设备：{self._device_label(record)}\n正在截屏：优先使用 exec-out，失败会自动改用设备端截图后拉取。")

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
            if pix.isNull():
                self.screenshot_panel.preview.clear()
                self.screenshot_panel.set_screenshot_path(None)
                self.screenshot_panel.set_result(False, "截图失败：生成的文件不是有效图片，请查看运行日志。")
                self.set_result_status("截屏失败", "FAILED", "生成的截图文件无法打开，已判定为无效图片。")
                return
            preview_size = self.screenshot_panel.preview.size()
            self.screenshot_panel.preview.setPixmap(
                pix.scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.screenshot_panel.set_screenshot_path(Path(path))
            self.screenshot_panel.set_result(True, f"截图成功：{path}")
            self.set_result_status("截屏成功", "SUCCESS", path=path)
        else:
            self.screenshot_panel.preview.clear()
            self.screenshot_panel.set_screenshot_path(None)
            self.screenshot_panel.set_result(False, "截图失败：未生成有效 PNG 文件。")
            self.set_result_status("截屏失败", "FAILED", "设备未连接、未授权、不支持截屏命令，或 ADB 返回了损坏图片。")

    def open_latest_screenshot(self):
        path = self.screenshot_panel.current_screenshot_path
        if not path or not path.exists():
            self.screenshot_panel.set_result(False, "当前没有可打开的截图，请先点击“截屏”。")
            return
        open_file_default(path)

    def record_screen(self):
        record = self._require_debuggable_target("无法录屏")
        if not record:
            return
        seconds = self.screenshot_panel.record_seconds.value()
        self.set_running_status(f"正在为 {self._device_label(record)} 录制屏幕 {seconds} 秒，请勿拔掉设备。")
        self.screenshot_panel.set_running(f"目标设备：{self._device_label(record)}\n正在录屏：预计 {seconds} 秒，完成后会自动拉取到本地。")

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
            self.screenshot_panel.set_result(True, f"录屏成功：{path}")
            self.set_result_status("录屏成功", "SUCCESS", path=path)
        else:
            self.screenshot_panel.set_result(False, "录屏失败：设备可能不支持 screenrecord，或当前连接/权限不足。")
            self.set_result_status("录屏失败", "UNSUPPORTED", "设备可能不支持 screenrecord，或当前连接/权限不足。")

    def push_file(self):
        record = self._require_debuggable_target("无法推送文件")
        if not record:
            return
        local, target = self.file_panel.push_values()
        self.set_running_status(f"正在运行：adb push {local} {target}")
        self.file_panel.set_running(f"目标设备：{self._device_label(record)}\n正在推送文件：{local}\n目标：{target}\n大文件或系统目录可能耗时较长，请等待结果。")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return FileTransfer(self.adb, self.output_root).push(runner, local, target)

        self.worker = TaskWorker(work)
        self.worker.done.connect(lambda result: self.on_transfer_done("推送文件", result))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def pull_file(self):
        record = self._require_debuggable_target("无法拉取文件")
        if not record:
            return
        device_path, local_dir = self.file_panel.pull_values()
        if not device_path:
            self.file_panel.set_result(False, "设备路径不能为空。")
            self.set_result_status("输入错误", "FAILED", "设备路径不能为空。")
            return
        self.set_running_status(f"正在运行：adb pull {device_path} {local_dir}")
        self.file_panel.set_running(f"目标设备：{self._device_label(record)}\n正在拉取文件：{device_path}\n保存目录：{local_dir}\n请等待传输完成。")

        def work():
            runner = CommandRunner(self.output_root / "command_status.json")
            return FileTransfer(self.adb, self.output_root).pull(runner, device_path, local_dir)

        self.worker = TaskWorker(work)
        self.worker.done.connect(lambda result: self.on_transfer_done("拉取文件", result))
        self.worker.failed.connect(self.on_task_failed)
        self.worker.start()

    def on_transfer_done(self, title: str, result):
        self._set_busy(False)
        message = result.error or ("传输完成。" if result.success else "传输失败，请查看运行提示。")
        self.file_panel.set_result(result.success, message)
        self.set_result_status(title, result.status, result.error)

    def closeEvent(self, event):
        if self.live_log_window:
            self.live_log_window.stop()
        for window in self.live_log_windows.values():
            window.close()
        for window in self.adb_debug_windows.values():
            window.close()
        if self.single_live_worker:
            self.single_live_worker.requestInterruption()
            self.single_live_worker.stop()
        QApplication.closeAllWindows()
        super().closeEvent(event)
