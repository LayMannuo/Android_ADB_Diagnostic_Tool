from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.core.single_log_collector import single_log_commands
from app.gui.styles import style_button


class SingleLogPanel(QGroupBox):
    def __init__(self):
        super().__init__("单项日志 / 问题分析")
        self.items = single_log_commands()
        layout = QVBoxLayout(self)

        hero = QLabel("先选日志类型，再选择抓取方式：已复现用“抓取当前日志”，现场复现用“开始实时抓取”。")
        hero.setWordWrap(True)
        hero.setStyleSheet("font-size: 15px; font-weight: 700; color: #202124; padding: 8px; background: #eef4ff; border: 1px solid #c9dafc;")
        layout.addWidget(hero)

        selector = QGridLayout()
        self.combo = QComboBox()
        for item in self.items:
            self.combo.addItem(str(item["title"]), str(item["name"]))
        self.category = QLabel()
        self.category.setWordWrap(True)
        self.category.setStyleSheet("font-weight: 700; color: #1a73e8;")
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.focus = QLabel()
        self.focus.setWordWrap(True)
        self.customer_hint = QLabel()
        self.customer_hint.setWordWrap(True)
        self.fae_hint = QLabel()
        self.fae_hint.setWordWrap(True)
        selector.addWidget(QLabel("日志类型"), 0, 0)
        selector.addWidget(self.combo, 0, 1)
        selector.addWidget(QLabel("日志分类"), 1, 0)
        selector.addWidget(self.category, 1, 1)
        selector.addWidget(QLabel("适用说明"), 2, 0)
        selector.addWidget(self.description, 2, 1)
        selector.addWidget(QLabel("分析重点"), 3, 0)
        selector.addWidget(self.focus, 3, 1)
        selector.addWidget(QLabel("客户提示"), 4, 0)
        selector.addWidget(self.customer_hint, 4, 1)
        selector.addWidget(QLabel("FAE 提示"), 5, 0)
        selector.addWidget(self.fae_hint, 5, 1)
        layout.addLayout(selector)

        actions = QHBoxLayout()
        self.history_button = QPushButton("抓取当前日志")
        self.start_live_button = QPushButton("开始实时抓取")
        self.stop_live_button = QPushButton("暂停并分析")
        self.clear_device_log_button = QPushButton("清除选中日志缓存")
        self.clear_display_button = QPushButton("清空页面显示")
        self.open_button = QPushButton("打开日志目录")
        style_button(self.history_button, "primary", "抓取当前日志快照，并自动做对应类型的简单分析。")
        style_button(self.start_live_button, "success", "按当前日志项启动实时抓取，适合现场复现。")
        style_button(self.stop_live_button, "warning", "暂停实时抓取，并对已保存内容做简单分析。")
        style_button(self.clear_device_log_button, "danger", "清除当前选中日志缓存，建议复现问题前使用。")
        style_button(self.clear_display_button, "secondary", "只清空软件页面显示，不删除已保存文件。")
        style_button(self.open_button, "secondary", "打开当前单项日志保存目录。")
        for button in [
            self.history_button,
            self.start_live_button,
            self.stop_live_button,
            self.clear_device_log_button,
            self.clear_display_button,
            self.open_button,
        ]:
            actions.addWidget(button)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.result = QLabel("等待操作。")
        self.result.setWordWrap(True)
        self.result.setStyleSheet("color: #5f6368;")
        layout.addWidget(self.progress)
        layout.addWidget(self.result)

        cards = QHBoxLayout()
        self.conclusion = QLabel("定位结论：暂无")
        self.conclusion.setWordWrap(True)
        self.conclusion.setMinimumHeight(72)
        self.conclusion.setStyleSheet("padding: 10px; border: 1px solid #dfe3ea; background: #f8fafc; font-weight: 700;")
        self.counts = QLabel("关键字统计：暂无")
        self.counts.setWordWrap(True)
        self.counts.setMinimumHeight(72)
        self.counts.setStyleSheet("padding: 10px; border: 1px solid #dfe3ea; background: #f8fafc;")
        cards.addWidget(self.conclusion)
        cards.addWidget(self.counts)
        layout.addLayout(cards)

        self.analysis = QTextEdit()
        self.analysis.setReadOnly(True)
        self.analysis.setMinimumHeight(180)
        self.analysis.setPlaceholderText("分析建议、证据和日志保存位置会显示在这里。")
        self.live_preview = QTextEdit()
        self.live_preview.setReadOnly(True)
        self.live_preview.setMinimumHeight(160)
        self.analysis_title = QLabel("分析建议")
        self.live_preview_title = QLabel("实时预览")
        layout.addWidget(self.analysis_title)
        layout.addWidget(self.analysis)
        layout.addWidget(self.live_preview_title)
        layout.addWidget(self.live_preview)

        self.combo.currentIndexChanged.connect(self.refresh_description)
        self.clear_display_button.clicked.connect(self.clear_display)
        self.refresh_description()

    def selected_name(self) -> str:
        return str(self.combo.currentData())

    def selected_item(self) -> dict[str, object]:
        return self.items[self.combo.currentIndex()]

    def refresh_description(self):
        item = self.items[self.combo.currentIndex()]
        self.category.setText(str(item.get("category_title", "通用日志")))
        self.description.setText(str(item["description"]))
        self.focus.setText(str(item.get("focus", "通用分析")))
        self.customer_hint.setText(str(item.get("customer_hint", "按当前场景抓取日志后发给工程师。")))
        self.fae_hint.setText(str(item.get("fae_hint", "结合问题时间点和关键字进行定位。")))
        self.start_live_button.setEnabled(bool(item.get("supports_live")))
        self.clear_device_log_button.setEnabled(bool(item.get("supports_clear")))
        self.live_preview_title.setText(str(item.get("live_preview_title", "实时预览：该日志项不支持实时抓取")))
        self.live_preview.setPlaceholderText(str(item.get("live_placeholder", "该日志项主要用于快照抓取，请点击“抓取当前日志”。")))

    def set_running(self, text: str):
        self.history_button.setEnabled(False)
        self.start_live_button.setEnabled(False)
        self.clear_device_log_button.setEnabled(False)
        self.combo.setEnabled(False)
        self.progress.setRange(0, 0)
        self.result.setStyleSheet("color: #b06000; font-weight: 700;")
        self.result.setText(text)

    def set_idle(self):
        self.history_button.setEnabled(True)
        self.combo.setEnabled(True)
        self.stop_live_button.setEnabled(False)
        self.refresh_description()
        self.progress.setRange(0, 1)

    def set_success(self, text: str, analysis_text: str, conclusion: str, counts: str):
        self.set_idle()
        self.progress.setValue(1)
        self.result.setStyleSheet("color: #137333; font-weight: 700;")
        self.result.setText(text)
        self.conclusion.setText(conclusion)
        self.conclusion.setStyleSheet("padding: 10px; border: 1px solid #b7dfc2; background: #f0fff4; font-weight: 700;")
        self.counts.setText(counts)
        self.analysis.setPlainText(analysis_text)

    def set_failure(self, text: str, analysis_text: str):
        self.set_idle()
        self.progress.setValue(0)
        self.result.setStyleSheet("color: #b3261e; font-weight: 700;")
        self.result.setText(text)
        self.conclusion.setText("定位结论：抓取失败")
        self.conclusion.setStyleSheet("padding: 10px; border: 1px solid #f0b8b8; background: #fff5f5; font-weight: 700;")
        self.analysis.setPlainText(analysis_text)

    def append_live_line(self, text: str):
        self.live_preview.append(text)

    def set_live_status(self, text: str, running: bool):
        self.result.setStyleSheet("color: #b06000; font-weight: 700;" if running else "color: #137333; font-weight: 700;")
        self.result.setText(text)
        self.combo.setEnabled(not running)
        self.history_button.setEnabled(not running)
        self.clear_device_log_button.setEnabled(False if running else self.clear_device_log_button.isEnabled())
        self.start_live_button.setEnabled(not running)
        self.stop_live_button.setEnabled(running)
        if running:
            self.live_preview.clear()

    def clear_display(self):
        self.analysis.clear()
        self.live_preview.clear()
        self.conclusion.setText("定位结论：暂无")
        self.counts.setText("关键字统计：暂无")
        self.result.setStyleSheet("color: #5f6368;")
        self.result.setText("页面显示已清空。")
