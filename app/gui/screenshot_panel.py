from pathlib import Path

from PySide6.QtCore import Qt, Signal
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


class ClickablePreview(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ScreenshotPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.current_screenshot_path: Path | None = None
        style_card(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        title = QLabel("截屏 / 录屏")
        title.setStyleSheet(CARD_TITLE_STYLE)
        layout.addWidget(title)
        self.capture_actions_row = QHBoxLayout()
        self.recording_actions_row = QHBoxLayout()
        self.screenshot_button = QPushButton("截屏")
        self.view_screenshot_button = QPushButton("查看截图")
        self.open_screenshot_button = QPushButton("打开截图目录")
        self.record_button = QPushButton(RECORD_BUTTON_TEXT)
        self.open_record_button = QPushButton("打开录屏目录")
        style_button(self.screenshot_button, "primary", "抓取当前设备屏幕截图。", "camera")
        style_button(self.view_screenshot_button, "secondary", "用 Windows 默认图片查看器打开本次截图。", "file")
        style_button(self.open_screenshot_button, "secondary", "打开截图保存目录。", "folder")
        style_button(self.record_button, "primary", "按设置秒数录制设备屏幕。", "record")
        style_button(self.open_record_button, "secondary", "打开录屏保存目录。", "folder")
        self.view_screenshot_button.setEnabled(False)
        self.record_seconds = QSpinBox()
        self.record_seconds.setRange(1, 180)
        self.record_seconds.setValue(10)
        self.record_seconds.setSuffix(" 秒")
        self.capture_actions_row.addWidget(self.screenshot_button)
        self.capture_actions_row.addWidget(self.view_screenshot_button)
        self.capture_actions_row.addWidget(self.open_screenshot_button)
        self.capture_actions_row.addStretch(1)
        self.recording_actions_row.addWidget(QLabel("录屏时长"))
        self.recording_actions_row.addWidget(self.record_seconds)
        self.recording_actions_row.addWidget(self.record_button)
        self.recording_actions_row.addWidget(self.open_record_button)
        self.recording_actions_row.addStretch(1)
        self.preview = ClickablePreview("截图成功后将在这里显示预览，点击预览可打开原图")
        self.preview.setMinimumHeight(140)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setCursor(Qt.PointingHandCursor)
        self.preview.setStyleSheet("border: 1px solid #dfe3ea; color: #5f6368; padding: 8px; background: #fbfcfe;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status = QLabel("等待截图或录屏。")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addLayout(self.capture_actions_row)
        layout.addLayout(self.recording_actions_row)
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

    def set_screenshot_path(self, path: Path | None):
        self.current_screenshot_path = path
        self.view_screenshot_button.setEnabled(bool(path and path.exists()))
