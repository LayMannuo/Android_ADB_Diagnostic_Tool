from __future__ import annotations

import ipaddress

from PySide6.QtWidgets import QFormLayout, QGridLayout, QGroupBox, QLineEdit, QPushButton, QTextEdit, QVBoxLayout

from app.gui.styles import style_button


class ConnectionPanel(QGroupBox):
    def __init__(self):
        super().__init__("ADB 远程连接")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.ip = QLineEdit()
        self.port = QLineEdit("5555")
        self.pair_ip = QLineEdit()
        self.pair_port = QLineEdit()
        self.pair_code = QLineEdit()
        form.addRow("设备 IP 地址", self.ip)
        form.addRow("连接端口", self.port)
        form.addRow("配对 IP 地址", self.pair_ip)
        form.addRow("配对端口", self.pair_port)
        form.addRow("配对码", self.pair_code)
        layout.addLayout(form)
        grid = QGridLayout()
        self.status_button = QPushButton("查看连接状态")
        self.tcpip_button = QPushButton("开启网络 ADB")
        self.connect_button = QPushButton("ADB 远程连接")
        self.disconnect_button = QPushButton("ADB 远程断开")
        self.pair_button = QPushButton("ADB 远程配对")
        self.root_button = QPushButton("adb root")
        self.remount_button = QPushButton("adb remount")
        style_button(self.status_button, "secondary", "刷新设备连接和授权状态。")
        style_button(self.tcpip_button, "engineer", "把当前 USB 设备切到网络 ADB 监听模式。")
        style_button(self.connect_button, "primary", "连接指定 IP 和端口的网络 ADB。")
        style_button(self.disconnect_button, "warning", "断开指定网络 ADB，未填 IP 时可断开全部。")
        style_button(self.pair_button, "engineer", "Android 11+ 无线调试配对。")
        style_button(self.root_button, "engineer", "工程机调试使用，量产设备通常不支持。")
        style_button(self.remount_button, "engineer", "工程机写系统分区前使用，量产设备通常不支持。")
        for index, button in enumerate(
            [
                self.status_button,
                self.tcpip_button,
                self.connect_button,
                self.disconnect_button,
                self.pair_button,
                self.root_button,
                self.remount_button,
            ]
        ):
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        self.note = QTextEdit("adb root / adb remount 仅供工程师调试使用；失败通常代表系统权限限制，不代表工具异常。")
        self.note.setReadOnly(True)
        self.note.setMaximumHeight(70)
        layout.addWidget(self.note)

    def endpoint(self) -> tuple[str, str]:
        return self.ip.text().strip(), self.port.text().strip() or "5555"

    def pair_endpoint(self) -> tuple[str, str, str]:
        return self.pair_ip.text().strip(), self.pair_port.text().strip(), self.pair_code.text().strip()

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
