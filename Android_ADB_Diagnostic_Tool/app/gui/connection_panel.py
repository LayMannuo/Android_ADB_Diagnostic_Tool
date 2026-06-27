from __future__ import annotations

import ipaddress

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.network_adb import DEFAULT_NETWORK_ADB_PORT, DeviceRecord, NetworkRange, validate_network_range
from app.gui.styles import CARD_TITLE_STYLE, MUTED_TEXT_STYLE, PANEL_HINT_STYLE, RESULT_IDLE_STYLE, style_button, style_card


class ConnectionPanel(QFrame):
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
        self.summary = QLabel("先找到设备，再选择投屏、抓日志、安装 APK 或生成诊断包。")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(PANEL_HINT_STYLE)
        layout.addWidget(self.summary)

        self.device_list_frame = self._build_device_box()
        layout.addWidget(self.device_list_frame)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setDocumentMode(True)
        self.mode_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #d9e1ec; border-radius: 8px; background: #ffffff; top: -1px; }"
            "QTabBar::tab { background: #f5f7fb; color: #374151; padding: 9px 16px; border: 1px solid #d9e1ec; border-bottom: none; min-width: 86px; }"
            "QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; font-weight: 700; }"
        )
        self.mode_tabs.addTab(self._build_usb_box(), "数据线")
        self.mode_tabs.addTab(self._build_network_box(), "同一网络")
        self.mode_tabs.addTab(self._build_pair_box(), "无线配对")
        self.mode_tabs.addTab(self._build_engineer_box(), "高级")
        layout.addWidget(self.mode_tabs)

        self.note = QTextEdit(
            "使用建议：普通客户优先使用“数据线连接”或“扫描当前网络”。"
            "同一网络连接默认端口为 5566，可按现场配置修改；只有通过 ADB 验证后才会显示“已可调试”。"
            "root、remount 属于工程师操作，量产设备不支持时通常是系统限制。"
        )
        self.note.setReadOnly(True)
        self.note.setMaximumHeight(78)
        layout.addWidget(self.note)

    def title(self) -> str:
        return self._title

    def _build_usb_box(self) -> QWidget:
        box = QWidget()
        layout = QGridLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        hint = QLabel("第一次使用建议先接数据线，检测到设备后可一键开启同一网络调试。")
        hint.setWordWrap(True)
        hint.setStyleSheet(RESULT_IDLE_STYLE)
        self.status_button = QPushButton("检测数据线设备")
        self.tcpip_button = QPushButton("开启同一网络调试")
        self.port = QLineEdit(DEFAULT_NETWORK_ADB_PORT)
        self.port.setMaximumWidth(90)
        self.port.setToolTip("同一网络调试端口，默认 5566，可修改。")
        style_button(self.status_button, "primary", "刷新数据线连接和授权状态。")
        style_button(self.tcpip_button, "success", "对当前选中数据线设备开启同一网络调试端口。")
        layout.addWidget(hint, 0, 0, 1, 3)
        layout.addWidget(QLabel("端口"), 1, 0)
        layout.addWidget(self.port, 1, 1)
        layout.addWidget(self.status_button, 1, 2)
        layout.addWidget(self.tcpip_button, 2, 0, 1, 3)
        return box

    def _build_network_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        quick = QHBoxLayout()
        self.quick_scan_button = QPushButton("扫描当前网络")
        self.scan_status = QLabel("默认扫描当前电脑所在网段，端口 5566。")
        self.scan_status.setWordWrap(True)
        self.scan_status.setStyleSheet(RESULT_IDLE_STYLE)
        style_button(self.quick_scan_button, "primary", "自动识别当前网段并扫描可调试设备。")
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
        style_button(self.scan_range_button, "secondary", "按起始 IP、结束 IP 和端口扫描。")
        style_button(self.save_range_button, "secondary", "保存当前网段，方便下次复用。")
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

        manual = QHBoxLayout()
        self.ip = QLineEdit()
        self.ip.setPlaceholderText("指定设备 IP，例如 192.168.28.20")
        self.connect_button = QPushButton("连接指定地址")
        self.disconnect_button = QPushButton("断开连接")
        style_button(self.connect_button, "success", "连接指定 IP 和端口的同一网络设备。")
        style_button(self.disconnect_button, "warning", "断开指定或当前选中的同一网络设备。")
        manual.addWidget(QLabel("指定 IP"))
        manual.addWidget(self.ip, 1)
        manual.addWidget(self.connect_button)
        manual.addWidget(self.disconnect_button)
        layout.addLayout(manual)
        return box

    def _build_pair_box(self) -> QWidget:
        box = QWidget()
        layout = QFormLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.pair_ip = QLineEdit()
        self.pair_port = QLineEdit()
        self.pair_code = QLineEdit()
        self.pair_button = QPushButton("无线调试配对")
        style_button(self.pair_button, "engineer", "Android 11+ 无线调试配对，配对成功后再连接设备地址。")
        layout.addRow("配对 IP 地址", self.pair_ip)
        layout.addRow("配对端口", self.pair_port)
        layout.addRow("配对码", self.pair_code)
        layout.addRow(QWidget(), self.pair_button)
        return box

    def _build_device_box(self) -> QFrame:
        box = QFrame()
        style_card(box)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 14)
        title_row = QHBoxLayout()
        title = QLabel("已发现设备")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1f2937;")
        self.empty_device_hint = QLabel("当前没有设备。请先检测数据线设备，或扫描同一网络。")
        self.empty_device_hint.setStyleSheet(MUTED_TEXT_STYLE)
        self.empty_device_hint.setWordWrap(True)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.empty_device_hint)
        layout.addLayout(title_row)
        self.device_table = QTableWidget(0, 6)
        self.device_table.setMinimumHeight(170)
        self.device_table.setHorizontalHeaderLabels(["设备", "状态", "连接方式", "IP/端口", "系统", "下一步"])
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf2; border-radius: 6px; gridline-color: #edf1f6; selection-background-color: #dbeafe; selection-color: #111827; }"
            "QHeaderView::section { background: #f8fafc; color: #374151; font-weight: 700; padding: 8px; border: none; border-right: 1px solid #e5eaf2; }"
            "QTableWidget::item { padding: 8px; }"
        )
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.device_table)
        return box

    def _build_engineer_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 16, 16, 16)
        hint = QLabel("工程师高级操作。普通客户无需使用；量产设备不支持 root/remount 通常是系统限制。")
        hint.setWordWrap(True)
        hint.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addWidget(hint)
        engineer = QHBoxLayout()
        self.root_button = QPushButton("adb root")
        self.remount_button = QPushButton("adb remount")
        style_button(self.root_button, "engineer", "工程机调试使用，量产设备通常不支持。")
        style_button(self.remount_button, "engineer", "工程机写系统分区前使用，量产设备通常不支持。")
        engineer.addWidget(self.root_button)
        engineer.addWidget(self.remount_button)
        engineer.addStretch(1)
        layout.addLayout(engineer)
        return box

    def endpoint(self) -> tuple[str, str]:
        return self.ip.text().strip(), self.port.text().strip() or DEFAULT_NETWORK_ADB_PORT

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
        self.records = records
        self.empty_device_hint.setVisible(not records)
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
        if records and not self.device_table.selectionModel().selectedRows():
            self.device_table.selectRow(0)

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
            self.port.setText(scan_range.port)

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
            "发现候选设备": "#1a73e8",
            "连接失败": "#b3261e",
        }
        return QBrush(QColor(colors.get(status, "#5f6368")))

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
