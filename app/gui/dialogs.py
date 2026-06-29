from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)


class CustomerInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("填写客户问题信息")
        self.resize(520, 420)
        self.setMinimumSize(360, 300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.customer = QLineEdit()
        self.contact = QLineEdit()
        self.phone = QLineEdit()
        self.problem = QTextEdit()
        self.steps = QTextEdit()
        self.time = QLineEdit()
        self.reproduce = QComboBox()
        self.reproduce.addItems(["是", "否", "偶发"])
        self.notes = QTextEdit()
        form.addRow("客户名称", self.customer)
        form.addRow("联系人", self.contact)
        form.addRow("联系方式", self.phone)
        form.addRow("问题现象", self.problem)
        form.addRow("复现步骤", self.steps)
        form.addRow("发生时间", self.time)
        form.addRow("是否稳定复现", self.reproduce)
        form.addRow("备注", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> dict[str, str]:
        return {
            "客户名称": self.customer.text(),
            "联系人": self.contact.text(),
            "联系方式": self.phone.text(),
            "问题现象": self.problem.toPlainText(),
            "复现步骤": self.steps.toPlainText(),
            "发生时间": self.time.text(),
            "是否稳定复现": self.reproduce.currentText(),
            "备注": self.notes.toPlainText(),
        }


class DeviceSelectDialog(QDialog):
    def __init__(self, devices: list[dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择设备")
        layout = QVBoxLayout(self)
        self.combo = QComboBox()
        for device in devices:
            self.combo.addItem(f"{device['serial']} - {device['state']}", device["serial"])
        layout.addWidget(self.combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_serial(self) -> str:
        return self.combo.currentData()


def show_info(parent, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def show_warning(parent, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)
