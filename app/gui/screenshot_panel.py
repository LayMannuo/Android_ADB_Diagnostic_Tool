from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSpinBox, QVBoxLayout

from app.core.ui_text import RECORD_BUTTON_TEXT
from app.gui.styles import (
    CARD_TITLE_STYLE,
    RESULT_FAILURE_STYLE,
    RESULT_IDLE_STYLE,
    RESULT_RUNNING_STYLE,
    RESULT_SUCCESS_STYLE,
    style_button,
    style_card,
)


class ScreenshotPanel(QFrame):
    def __init__(self):
        super().__init__()
        style_card(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        title = QLabel("截屏 / 录屏")
        title.setStyleSheet(CARD_TITLE_STYLE)
        layout.addWidget(title)
        buttons = QHBoxLayout()
        self.screenshot_button = QPushButton("截屏")
        self.open_screenshot_button = QPushButton("打开截图目录")
        self.record_button = QPushButton(RECORD_BUTTON_TEXT)
        self.mirror_button = QPushButton("ADB 投屏")
        self.open_record_button = QPushButton("打开录屏目录")
        style_button(self.screenshot_button, "primary", "抓取当前设备屏幕截图。")
        style_button(self.open_screenshot_button, "secondary", "打开截图保存目录。")
        style_button(self.record_button, "primary", "按设置秒数录制设备屏幕。")
        style_button(self.mirror_button, "success", "启动 scrcpy 实时投屏窗口。")
        style_button(self.open_record_button, "secondary", "打开录屏保存目录。")
        self.record_seconds = QSpinBox()
        self.record_seconds.setRange(1, 180)
        self.record_seconds.setValue(10)
        self.record_seconds.setSuffix(" 秒")
        buttons.addWidget(self.screenshot_button)
        buttons.addWidget(self.open_screenshot_button)
        buttons.addWidget(QLabel("录屏时长"))
        buttons.addWidget(self.record_seconds)
        buttons.addWidget(self.record_button)
        buttons.addWidget(self.mirror_button)
        buttons.addWidget(self.open_record_button)
        buttons.addStretch(1)
        self.preview = QLabel("截图成功后将在这里显示预览")
        self.preview.setMinimumHeight(140)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("border: 1px solid #dfe3ea; color: #5f6368; padding: 8px; background: #fbfcfe;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status = QLabel("等待截图或录屏。")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.preview)

    def set_running(self, text: str):
        self.progress.setRange(0, 0)
        self.status.setStyleSheet(RESULT_RUNNING_STYLE)
        self.status.setText(text)

    def set_result(self, success: bool, text: str):
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if success else 0)
        self.status.setStyleSheet(RESULT_SUCCESS_STYLE if success else RESULT_FAILURE_STYLE)
        self.status.setText(text)
