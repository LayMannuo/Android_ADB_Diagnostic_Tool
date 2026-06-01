from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout

from app.gui.styles import style_button


class FileTransferPanel(QGroupBox):
    def __init__(self):
        super().__init__("ADB 文件传输")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.local_file = QLineEdit()
        browse_file = QPushButton("选择文件")
        row = QHBoxLayout()
        row.addWidget(self.local_file)
        row.addWidget(browse_file)
        self.push_path = QLineEdit("/sdcard/Download/")
        self.pull_path = QLineEdit()
        self.local_dir = QLineEdit()
        browse_dir = QPushButton("选择目录")
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.local_dir)
        dir_row.addWidget(browse_dir)
        form.addRow("本地文件", row)
        form.addRow("设备目标路径", self.push_path)
        form.addRow("设备文件/目录", self.pull_path)
        form.addRow("本地保存目录", dir_row)
        layout.addLayout(form)
        self.push_button = QPushButton("推送文件到设备")
        self.pull_button = QPushButton("从设备拉取文件")
        style_button(browse_file, "secondary", "选择要推送到设备的本地文件。")
        style_button(browse_dir, "secondary", "选择从设备拉取文件后的本地保存目录。")
        style_button(self.push_button, "primary", "执行 adb push，把本地文件发送到设备。")
        style_button(self.pull_button, "primary", "执行 adb pull，把设备文件拉取到本地。")
        layout.addWidget(self.push_button)
        layout.addWidget(self.pull_button)
        note = QTextEdit("普通客户建议使用 /sdcard/Download/。/system、/vendor、/product、/data 通常需要 adb root + adb remount；失败可能是设备权限限制。")
        note.setReadOnly(True)
        note.setMaximumHeight(80)
        layout.addWidget(note)
        browse_file.clicked.connect(self.choose_file)
        browse_dir.clicked.connect(self.choose_dir)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择要推送的文件")
        if path:
            self.local_file.setText(path)

    def choose_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.local_dir.setText(path)

    def push_values(self) -> tuple[Path, str]:
        return Path(self.local_file.text()), self.push_path.text().strip() or "/sdcard/Download/"

    def pull_values(self) -> tuple[str, Path]:
        return self.pull_path.text().strip(), Path(self.local_dir.text())
