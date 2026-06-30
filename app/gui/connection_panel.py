from __future__ import annotations

import ipaddress

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.network_adb import DEFAULT_NETWORK_ADB_PORT, DeviceRecord, NetworkRange, validate_network_range
from app.gui.styles import (
    CARD_TITLE_STYLE,
    MUTED_TEXT_STYLE,
    PANEL_HINT_STYLE,
    RESULT_IDLE_STYLE,
    SUMMARY_PILL_STYLE,
    make_step_header,
    style_button,
    style_card,
)


class ConnectionPanel(QFrame):
    disconnect_device_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._title = "设备连接中心"
        self.records: list[DeviceRecord] = []
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        style_card(self)
        title = QLabel("设备连接中心")
        title.setStyleSheet(CARD_TITLE_STYLE)
        layout.addWidget(title)
        self.summary = QLabel("连接是所有操作的第一步。先选择连接方式并确认设备“已可调试”，再执行投屏、日志、截图、文件传输或 APK 安装。")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(PANEL_HINT_STYLE)
        layout.addWidget(self.summary)

        self.method_title = make_step_header("1 选择连接方式")
        layout.addWidget(self.method_title)
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setDocumentMode(True)
        self._method_tab_heights = [145, 200, 175]
        self.mode_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #d9e1ec; border-radius: 8px; background: #ffffff; top: -1px; }"
            "QTabBar::tab { background: #f8fafc; color: #475569; padding: 9px 18px; border: 1px solid #d9e1ec; border-bottom: none; min-width: 96px; }"
            "QTabBar::tab:selected { background: #ffffff; color: #2563eb; font-weight: 500; }"
        )
        self.mode_tabs.addTab(self._build_usb_box(), "数据线连接")
        self.mode_tabs.addTab(self._build_network_box(), "网络连接")
        self.mode_tabs.addTab(self._build_scan_box(), "网段扫描")
        self.mode_tabs.currentChanged.connect(self._apply_method_tab_height)
        self._apply_method_tab_height(0)
        layout.addWidget(self.mode_tabs)

        self.device_list_frame = self._build_device_box()
        layout.addWidget(self.device_list_frame)

        self.note_title = make_step_header("3 使用建议")
        layout.addWidget(self.note_title)
        self.note = QLabel(
            "使用建议：数据线连接用于 USB 检测和授权；网络连接用于已知 IP 的设备；网段扫描用于不知道设备 IP 的场景。"
            "无线配对是网络连接的辅助步骤，适用于 Android 11+。"
            "只有通过 ADB 验证后才会显示“已可调试”。"
            "root、remount 属于工程师操作，量产设备不支持时通常是系统限制。"
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet(PANEL_HINT_STYLE)
        layout.addWidget(self.note)
        self.engineer_tools_frame = self._build_engineer_box()
        layout.addWidget(self.engineer_tools_frame)

    def title(self) -> str:
        return self._title

    def _apply_method_tab_height(self, index: int) -> None:
        height = self._method_tab_heights[index] if 0 <= index < len(self._method_tab_heights) else self._method_tab_heights[0]
        self.mode_tabs.setMinimumHeight(height)
        self.mode_tabs.setMaximumHeight(height)

    def _build_usb_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        self.usb_hint = QLabel("适合第一次连接、USB 授权确认、offline/unauthorized 排查。数据线连接不涉及 IP 或端口。")
        self.usb_hint.setWordWrap(True)
        self.usb_hint.setStyleSheet(RESULT_IDLE_STYLE)
        self.usb_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.usb_hint)

        actions = QHBoxLayout()
        self.status_button = QPushButton("检测数据线设备")
        self.usb_refresh_button = QPushButton("刷新")
        self.restart_adb_button = QPushButton("重启 ADB 服务")
        style_button(self.status_button, "primary", "检测 USB 连接、本机 ADB 和设备授权状态。", "device")
        style_button(self.usb_refresh_button, "secondary", "重新刷新当前设备列表。", "refresh")
        style_button(self.restart_adb_button, "warning", "重启本机 ADB 服务，适合设备 offline 或连接异常时使用。", "restart")
        actions.addWidget(self.status_button)
        actions.addWidget(self.usb_refresh_button)
        actions.addWidget(self.restart_adb_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return box

    def _build_network_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        self.network_hint = QLabel("已知设备 IP 时使用：输入 IP 和端口后点击“连接设备”。Android 11+ 可先完成无线配对，再连接设备地址。")
        self.network_hint.setWordWrap(True)
        self.network_hint.setStyleSheet(RESULT_IDLE_STYLE)
        self.network_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.network_hint.setMinimumHeight(40)
        self.network_hint.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(self.network_hint)

        manual = QHBoxLayout()
        manual.setSpacing(10)
        self.ip = QLineEdit()
        self.ip.setPlaceholderText("指定设备 IP，例如 192.168.28.20")
        self.ip.setMinimumWidth(320)
        self.connect_port = QLineEdit(DEFAULT_NETWORK_ADB_PORT)
        self.connect_port.setMinimumWidth(82)
        self.connect_port.setMaximumWidth(90)
        self.connect_port.setToolTip("连接指定 IP 时使用的 ADB 网络端口，默认 5566。")
        self.connect_button = QPushButton("连接设备")
        self.disconnect_button = QPushButton("断开全部网络设备")
        style_button(self.connect_button, "success", "连接指定 IP 和端口的网络 ADB 设备。", "connect")
        style_button(self.disconnect_button, "warning", "断开所有通过 adb connect 建立的网络 ADB 设备；单台网络设备请在设备列表行内点击断开。", "disconnect")
        self.connect_button.setMinimumWidth(120)
        self.disconnect_button.setMinimumWidth(170)
        manual.addWidget(QLabel("指定 IP"))
        manual.addWidget(self.ip, 1)
        manual.addWidget(QLabel("连接端口"))
        manual.addWidget(self.connect_port)
        manual.addWidget(self.connect_button)
        manual.addWidget(self.disconnect_button)
        layout.addLayout(manual)

        pair_title = QLabel("无线配对（Android 11+，可选）")
        pair_title.setStyleSheet("font-size: 14px; font-weight: 500; color: #1f2937;")
        layout.addWidget(pair_title)
        layout.addWidget(self._build_pair_box())
        return box

    def _build_scan_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        quick = QHBoxLayout()
        self.quick_scan_button = QPushButton("扫描当前网段")
        self.scan_status = QLabel("默认扫描当前电脑所在网段，端口 5566。")
        self.scan_status.setWordWrap(True)
        self.scan_status.setStyleSheet(RESULT_IDLE_STYLE)
        self.scan_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        style_button(self.quick_scan_button, "primary", "自动识别当前网段并扫描可调试设备。", "scan")
        quick.addWidget(self.quick_scan_button)
        quick.addWidget(self.scan_status, 1)
        layout.addLayout(quick)

        range_form = QGridLayout()
        self.start_ip = QLineEdit()
        self.end_ip = QLineEdit()
        self.scan_port = QLineEdit(DEFAULT_NETWORK_ADB_PORT)
        self.scan_port.setMaximumWidth(90)
        self.saved_ranges = QComboBox()
        self.saved_ranges.addItem("未保存常用网段")
        self.scan_range_button = QPushButton("扫描指定范围")
        self.save_range_button = QPushButton("保存网段")
        style_button(self.scan_range_button, "secondary", "按起始 IP、结束 IP 和端口扫描。", "scan")
        style_button(self.save_range_button, "secondary", "保存当前网段，方便下次复用。", "save")
        range_form.addWidget(QLabel("起始 IP"), 0, 0)
        range_form.addWidget(self.start_ip, 0, 1)
        range_form.addWidget(QLabel("结束 IP"), 0, 2)
        range_form.addWidget(self.end_ip, 0, 3)
        range_form.addWidget(QLabel("端口"), 0, 4)
        range_form.addWidget(self.scan_port, 0, 5)
        range_form.addWidget(QLabel("常用网段"), 1, 0)
        range_form.addWidget(self.saved_ranges, 1, 1, 1, 3)
        range_form.addWidget(self.save_range_button, 1, 4)
        range_form.addWidget(self.scan_range_button, 1, 5)
        layout.addLayout(range_form)
        return box

    def _build_pair_box(self) -> QWidget:
        box = QWidget()
        layout = QGridLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        self.pair_ip = QLineEdit()
        self.pair_port = QLineEdit()
        self.pair_code = QLineEdit()
        self.pair_ip.setPlaceholderText("配对 IP")
        self.pair_port.setPlaceholderText("端口")
        self.pair_code.setPlaceholderText("配对码")
        self.pair_port.setMaximumWidth(90)
        self.pair_code.setMaximumWidth(120)
        self.pair_button = QPushButton("无线调试配对")
        style_button(self.pair_button, "engineer", "Android 11+ 无线调试配对，配对成功后再连接设备地址。", "connect")
        layout.addWidget(QLabel("配对 IP"), 0, 0)
        layout.addWidget(self.pair_ip, 0, 1)
        layout.addWidget(QLabel("端口"), 0, 2)
        layout.addWidget(self.pair_port, 0, 3)
        layout.addWidget(QLabel("配对码"), 0, 4)
        layout.addWidget(self.pair_code, 0, 5)
        layout.addWidget(self.pair_button, 0, 6)
        layout.setColumnStretch(1, 1)
        return box

    def _build_device_box(self) -> QFrame:
        box = QFrame()
        style_card(box)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 14)
        title_row = QHBoxLayout()
        self.device_list_title = make_step_header("2 设备列表")
        self.empty_device_hint = QLabel("当前没有设备。请先选择数据线连接、网络连接或网段扫描。")
        self.empty_device_hint.setStyleSheet(MUTED_TEXT_STYLE)
        self.empty_device_hint.setWordWrap(True)
        title_row.addWidget(self.device_list_title)
        title_row.addStretch(1)
        title_row.addWidget(self.empty_device_hint)
        layout.addLayout(title_row)
        summary = QHBoxLayout()
        self.device_summary_labels = {
            "found": QLabel("已发现 0 台"),
            "ready": QLabel("已可调试 0 台"),
            "current": QLabel("当前操作设备：未选择"),
        }
        for label in self.device_summary_labels.values():
            label.setStyleSheet(SUMMARY_PILL_STYLE)
            summary.addWidget(label)
        summary.addStretch(1)
        layout.addLayout(summary)
        self.scope_hint = QLabel("选中一行后，投屏、截图、日志、文件传输和 ADB 调试窗口都针对该设备执行。")
        self.scope_hint.setWordWrap(True)
        self.scope_hint.setStyleSheet(MUTED_TEXT_STYLE)
        layout.addWidget(self.scope_hint)
        self.status_legend = QLabel("已可调试=可操作  未授权=确认授权  离线=不可操作  候选设备=待验证")
        self.status_legend.setWordWrap(True)
        self.status_legend.setStyleSheet(PANEL_HINT_STYLE)
        layout.addWidget(self.status_legend)
        self.device_table = QTableWidget(0, 7)
        self.device_table.setMinimumHeight(190)
        self.device_table.setHorizontalHeaderLabels(["设备", "状态", "连接方式", "序列号/IP", "系统", "下一步", "操作"])
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf2; border-radius: 6px; gridline-color: #edf1f6; selection-background-color: #dbeafe; selection-color: #111827; }"
            "QHeaderView::section { background: #f8fafc; color: #374151; font-weight: 500; padding: 8px; border: none; border-right: 1px solid #e5eaf2; }"
            "QTableWidget::item { padding: 8px; }"
        )
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.device_table.setColumnWidth(6, 96)
        layout.addWidget(self.device_table)
        self.device_table.itemSelectionChanged.connect(self._sync_device_summary)
        self.device_table.cellClicked.connect(self._handle_device_cell_clicked)
        return box

    def _build_engineer_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        title = make_step_header("4 工程师高级操作")
        layout.addWidget(title)
        hint = QLabel("工程师高级操作。普通客户无需使用；量产设备不支持 root/remount 通常是系统限制。")
        hint.setWordWrap(True)
        hint.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addWidget(hint)
        engineer = QHBoxLayout()
        self.root_button = QPushButton("adb root")
        self.remount_button = QPushButton("adb remount")
        style_button(self.root_button, "engineer", "工程机调试使用，量产设备通常不支持。", "terminal")
        style_button(self.remount_button, "engineer", "工程机写系统分区前使用，量产设备通常不支持。", "package")
        engineer.addWidget(self.root_button)
        engineer.addWidget(self.remount_button)
        engineer.addStretch(1)
        layout.addLayout(engineer)
        return box

    def endpoint(self) -> tuple[str, str]:
        port = self.connect_port.text().strip() or DEFAULT_NETWORK_ADB_PORT
        return self.ip.text().strip(), port

    def pair_endpoint(self) -> tuple[str, str, str]:
        return self.pair_ip.text().strip(), self.pair_port.text().strip(), self.pair_code.text().strip()

    def scan_range_values(self) -> tuple[bool, str, NetworkRange | None]:
        return validate_network_range(self.start_ip.text(), self.end_ip.text(), self.scan_port.text() or DEFAULT_NETWORK_ADB_PORT)

    def selected_serial(self) -> str | None:
        rows = self.device_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.device_table.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    def set_scan_status(self, message: str, color: str = "gray") -> None:
        colors = {
            "green": "#137333",
            "yellow": "#b06000",
            "red": "#b3261e",
            "gray": "#5f6368",
        }
        self.scan_status.setStyleSheet(f"color: {colors.get(color, colors['gray'])}; background: #f8fafc; padding: 9px; border: 1px solid #dfe3ea; border-radius: 6px;")
        self.scan_status.setText(message)

    def set_devices(self, records: list[DeviceRecord]) -> None:
        current = self.selected_serial()
        self.records = records
        self.empty_device_hint.setVisible(not records)
        ready_count = sum(1 for record in records if record.status == "已可调试")
        self.device_summary_labels["found"].setText(f"已发现 {len(records)} 台")
        self.device_summary_labels["ready"].setText(f"已可调试 {ready_count} 台")
        self.device_table.setRowCount(0)
        self.device_table.setRowCount(len(records))
        for row, record in enumerate(records):
            cells = [
                record.display_name(),
                record.status,
                record.connection,
                record.endpoint or record.serial,
                self._system_text(record),
                record.next_action(),
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if column == 0:
                    item.setData(Qt.UserRole, record.serial)
                if column == 1:
                    item.setForeground(self._status_brush(record.status))
                self.device_table.setItem(row, column, item)
            self._set_row_action(row, record)
            self.device_table.setRowHeight(row, 34)
        selected_row = next((row for row, record in enumerate(records) if record.serial == current), -1)
        if records:
            self.device_table.selectRow(selected_row if selected_row >= 0 else 0)
        self._sync_device_summary()

    def _set_row_action(self, row: int, record: DeviceRecord) -> None:
        item = QTableWidgetItem("断开连接" if self._is_network_record(record) else "-")
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        if self._is_network_record(record):
            item.setData(Qt.UserRole, record.serial)
            item.setForeground(self._action_brush())
            item.setToolTip("断开这台网络 ADB 设备。")
        else:
            item.setForeground(self._muted_brush())
        self.device_table.setItem(row, 6, item)

    def _handle_device_cell_clicked(self, row: int, column: int) -> None:
        if column != 6 or row < 0 or row >= len(self.records):
            return
        record = self.records[row]
        if self._is_network_record(record):
            serial = record.serial
            QTimer.singleShot(0, lambda: self.disconnect_device_requested.emit(serial))

    @staticmethod
    def _is_network_record(record: DeviceRecord) -> bool:
        return record.connection == "网络 ADB 连接"

    def _sync_device_summary(self) -> None:
        serial = self.selected_serial()
        record = next((item for item in self.records if item.serial == serial), None)
        if not record:
            self.device_summary_labels["current"].setText("当前操作设备：未选择")
            return
        self.device_summary_labels["current"].setText(f"当前操作设备：{record.display_name()} / {record.serial}")

    def add_or_update_devices(self, records: list[DeviceRecord]) -> None:
        by_serial = {record.serial: record for record in self.records}
        for record in records:
            by_serial[record.serial] = record
        self.set_devices(list(by_serial.values()))

    def set_recent_ranges(self, ranges: list[NetworkRange]) -> None:
        self.saved_ranges.clear()
        if not ranges:
            self.saved_ranges.addItem("未保存常用网段")
            return
        for scan_range in ranges:
            self.saved_ranges.addItem(scan_range.label(), scan_range)

    def apply_selected_range(self) -> None:
        scan_range = self.saved_ranges.currentData()
        if isinstance(scan_range, NetworkRange):
            self.start_ip.setText(scan_range.start_ip)
            self.end_ip.setText(scan_range.end_ip)
            self.scan_port.setText(scan_range.port)
            self.connect_port.setText(scan_range.port)

    @staticmethod
    def _system_text(record: DeviceRecord) -> str:
        parts = []
        if record.android:
            parts.append(f"Android {record.android}")
        if record.brand:
            parts.append(record.brand)
        return " / ".join(parts) if parts else "-"

    @staticmethod
    def _status_brush(status: str):
        from PySide6.QtGui import QColor, QBrush

        colors = {
            "已可调试": "#137333",
            "未授权": "#b06000",
            "离线": "#b3261e",
            "候选设备": "#1a73e8",
            "发现候选设备": "#1a73e8",
            "连接失败": "#b3261e",
        }
        return QBrush(QColor(colors.get(status, "#5f6368")))

    @staticmethod
    def _action_brush():
        from PySide6.QtGui import QColor, QBrush

        return QBrush(QColor("#a16207"))

    @staticmethod
    def _muted_brush():
        from PySide6.QtGui import QColor, QBrush

        return QBrush(QColor("#64748b"))

    @staticmethod
    def validate_endpoint(ip: str, port: str) -> tuple[bool, str]:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return False, "IP 地址格式不正确。"
        try:
            value = int(port)
        except ValueError:
            return False, "端口必须是数字。"
        if not 1 <= value <= 65535:
            return False, "端口范围必须是 1~65535。"
        return True, ""
