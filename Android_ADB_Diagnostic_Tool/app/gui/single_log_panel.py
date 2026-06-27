from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.core.single_log_collector import single_log_commands
from app.gui.styles import CARD_TITLE_STYLE, RESULT_FAILURE_STYLE, RESULT_IDLE_STYLE, RESULT_RUNNING_STYLE, RESULT_SUCCESS_STYLE, STEP_BADGE_STYLE, style_button, style_card


class SingleLogPanel(QFrame):
    LIVE_PREVIEW_LINE_LIMIT = 1000

    def __init__(self):
        super().__init__()
        style_card(self)
        self.items = single_log_commands()
        self._live_preview_lines: list[str] = []
        self._pending_live_preview_lines: list[str] = []
        self._live_flush_timer = QTimer(self)
        self._live_flush_timer.setInterval(150)
        self._live_flush_timer.timeout.connect(self.flush_live_preview)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("单项日志 / 问题分析")
        title.setStyleSheet(CARD_TITLE_STYLE)
        layout.addWidget(title)

        hero = QLabel("1 选择日志类型：默认保留设备已缓存日志；需要丢弃旧日志时再手动清除缓存。")
        hero.setWordWrap(True)
        hero.setStyleSheet(STEP_BADGE_STYLE)
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
        self.capability = QLabel()
        self.capability.setWordWrap(True)
        self.capability.setStyleSheet("color: #137333; background: #f0fff4; padding: 8px; border: 1px solid #b7dfc2;")
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
        selector.addWidget(QLabel("当前能力"), 6, 0)
        selector.addWidget(self.capability, 6, 1)
        layout.addLayout(selector)

        action_title = QLabel("2 选择抓取方式")
        action_title.setStyleSheet(STEP_BADGE_STYLE)
        layout.addWidget(action_title)

        actions = QHBoxLayout()
        self.history_button = QPushButton("导出已缓存日志")
        self.start_live_button = QPushButton("开始持续抓取（含缓存）")
        self.stop_live_button = QPushButton("停止抓取并分析")
        self.clear_device_log_button = QPushButton("清除设备日志缓存（高级）")
        self.clear_display_button = QPushButton("清空页面显示")
        self.open_button = QPushButton("打开日志目录")
        style_button(self.history_button, "primary", "导出设备当前已缓存日志，并自动做对应类型的简单分析。")
        style_button(self.start_live_button, "success", "持续抓取选中日志项：先接收设备已缓存日志，再继续追加新增日志。")
        style_button(self.stop_live_button, "warning", "停止持续抓取，并对已保存的完整日志文件做简单分析。")
        style_button(self.clear_device_log_button, "danger", "高级操作：清空设备当前日志缓存。只有明确要丢弃旧日志时使用。")
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
        advanced_hint = QLabel("高级操作说明：清除设备日志缓存会丢弃旧日志；默认不要清除，除非你明确要重新开始采集。")
        advanced_hint.setWordWrap(True)
        advanced_hint.setStyleSheet("color: #b3261e; background: #fff5f5; padding: 8px; border: 1px solid #f0b8b8;")
        layout.addWidget(advanced_hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.result = QLabel("等待操作。默认保留设备已缓存日志；完整日志会保存到文件。")
        self.result.setWordWrap(True)
        self.result.setStyleSheet(RESULT_IDLE_STYLE)
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
        self.analysis_title = QLabel("3 分析结果 / 证据 / 下一步建议")
        self.analysis_title.setStyleSheet(STEP_BADGE_STYLE)
        self.live_preview_title = QLabel("实时预览")
        self.live_preview_title.setStyleSheet("font-weight: 700; color: #202124;")
        layout.addWidget(self.analysis_title)
        layout.addWidget(self.analysis)
        layout.addWidget(self.live_preview_title)
        layout.addWidget(self.live_preview)

        self.combo.currentIndexChanged.connect(self.refresh_description)
        self.clear_display_button.clicked.connect(self.clear_display)
        self.refresh_description()
        self.stop_live_button.setEnabled(False)

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
        self.stop_live_button.setEnabled(False)
        self.live_preview_title.setText(str(item.get("live_preview_title", "实时预览：该日志项不支持实时抓取")))
        self.live_preview.setPlaceholderText(str(item.get("live_placeholder", "该日志项主要用于快照抓取，请点击“导出已缓存日志”。")))
        live_text = "支持实时抓取" if item.get("supports_live") else "不支持实时抓取"
        clear_text = "支持清除缓存" if item.get("supports_clear") else "无缓存可清除"
        snapshot_text = "支持当前快照抓取" if item.get("supports_snapshot") else "不支持快照抓取"
        self.capability.setText(f"{snapshot_text} / {live_text} / {clear_text}")

    def set_running(self, text: str):
        self.history_button.setEnabled(False)
        self.start_live_button.setEnabled(False)
        self.stop_live_button.setEnabled(False)
        self.clear_device_log_button.setEnabled(False)
        self.combo.setEnabled(False)
        self.progress.setRange(0, 0)
        self.result.setStyleSheet(RESULT_RUNNING_STYLE)
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
        self.result.setStyleSheet(RESULT_SUCCESS_STYLE)
        self.result.setText(text)
        self.conclusion.setText(conclusion)
        self.conclusion.setStyleSheet("padding: 10px; border: 1px solid #b7dfc2; background: #f0fff4; font-weight: 700;")
        self.counts.setText(counts)
        self.analysis.setPlainText(analysis_text)

    def set_failure(self, text: str, analysis_text: str):
        self.set_idle()
        self.progress.setValue(0)
        self.result.setStyleSheet(RESULT_FAILURE_STYLE)
        self.result.setText(text)
        self.conclusion.setText("定位结论：抓取失败")
        self.conclusion.setStyleSheet("padding: 10px; border: 1px solid #f0b8b8; background: #fff5f5; font-weight: 700;")
        self.analysis.setPlainText(analysis_text)

    def append_live_line(self, text: str):
        self._pending_live_preview_lines.append(text)
        if not self._live_flush_timer.isActive():
            self._live_flush_timer.start()

    def flush_live_preview(self):
        if not self._pending_live_preview_lines:
            self._live_flush_timer.stop()
            return
        self._live_preview_lines.extend(self._pending_live_preview_lines)
        self._pending_live_preview_lines.clear()
        if len(self._live_preview_lines) > self.LIVE_PREVIEW_LINE_LIMIT:
            self._live_preview_lines = self._live_preview_lines[-self.LIVE_PREVIEW_LINE_LIMIT :]
        self.live_preview.setPlainText("\n".join(self._live_preview_lines))
        self.live_preview.moveCursor(QTextCursor.End)

    def set_live_status(self, text: str, running: bool):
        self.result.setStyleSheet(RESULT_RUNNING_STYLE if running else RESULT_SUCCESS_STYLE)
        suffix = f"\n界面仅显示最近 {self.LIVE_PREVIEW_LINE_LIMIT} 行，完整日志已持续保存到文件。"
        self.result.setText(text + suffix if running else text)
        self.combo.setEnabled(not running)
        self.history_button.setEnabled(not running)
        self.clear_device_log_button.setEnabled(False if running else self.clear_device_log_button.isEnabled())
        self.start_live_button.setEnabled(not running)
        self.stop_live_button.setEnabled(running)
        if running:
            self._live_preview_lines.clear()
            self._pending_live_preview_lines.clear()
            self.live_preview.clear()

    def clear_display(self):
        self.analysis.clear()
        self._live_preview_lines.clear()
        self._pending_live_preview_lines.clear()
        self.live_preview.clear()
        self.conclusion.setText("定位结论：暂无")
        self.counts.setText("关键字统计：暂无")
        self.result.setStyleSheet(RESULT_IDLE_STYLE)
        self.result.setText("页面显示已清空。")
