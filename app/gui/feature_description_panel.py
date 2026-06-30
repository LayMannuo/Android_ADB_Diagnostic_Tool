from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from app.gui.styles import CARD_TITLE_STYLE, MUTED_TEXT_STYLE, PANEL_HINT_STYLE, make_step_header, style_card


class FeatureDescriptionPanel(QFrame):
    def __init__(self):
        super().__init__()
        style_card(self)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("功能说明")
        title.setStyleSheet(CARD_TITLE_STYLE)
        subtitle = QLabel("给客户和 FAE 的操作说明、状态解释和交付边界。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(MUTED_TEXT_STYLE)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        flow_title = make_step_header("1 推荐使用流程")
        layout.addWidget(flow_title)
        flow = QHBoxLayout()
        self.flow_cards = []
        for name, body in [
            ("连接设备", "在设备连接页选择数据线连接、网络连接或网段扫描。"),
            ("确认已可调试", "只有已可调试设备才能投屏、抓日志、安装 APK 或生成诊断包。"),
            ("执行操作", "按现场问题进入快速诊断、单项日志、APK 安装或辅助工具。"),
            ("导出结果", "把诊断包、日志、截图、安装结果发给工程师分析。"),
        ]:
            card = self._info_card(name, body)
            self.flow_cards.append(card)
            flow.addWidget(card)
        layout.addLayout(flow)

        pages_title = make_step_header("2 页面说明")
        layout.addWidget(pages_title)
        pages = QGridLayout()
        page_items = [
            ("设备连接", "数据线连接、网络连接、网段扫描。确认设备已可调试。"),
            ("快速诊断", "一键生成诊断包，适合客户交付现场信息。包含 62 项 ADB 采集命令、自动截图、summary_report.html 报告、command_status.json 执行明细，并压缩为 zip。"),
            ("单项日志", "按问题类型抓指定日志，并自动分析关键字。采集范围包括 logcat/dmesg 7 项。"),
            ("APK 安装", "添加 APK，勾选设备，一次开始安装。目标设备表显示每台设备的安装结果。"),
            ("辅助工具", "截图、录屏、文件传输、ADB 调试窗口。耗时操作后台执行，不阻塞界面。"),
            ("诊断范围", "设备信息 12 项、bugreport 1 项、dumpsys 16 项、网络 10 项；单条命令失败时流程继续执行。"),
        ]
        for index, (name, body) in enumerate(page_items):
            pages.addWidget(self._info_card(name, body), index // 2, index % 2)
        layout.addLayout(pages)

        rules_title = make_step_header("3 状态与颜色规则")
        layout.addWidget(rules_title)
        rules = QGridLayout()
        for index, (name, body, color) in enumerate(
            [
                ("已可调试 / 成功", "可继续操作。", "#0f7a3b"),
                ("运行中 / 等待", "请勿断开设备。", "#9a4d00"),
                ("失败", "查看原因和解决建议。", "#b3261e"),
                ("候选设备", "扫描发现但未确认 ADB 可用。", "#1d4ed8"),
            ]
        ):
            label = QLabel(f"{name}：{body}")
            label.setWordWrap(True)
            label.setStyleSheet(f"font-weight: 500; color: {color}; background: #f8fafc; padding: 9px; border: 1px solid #dde5ef; border-radius: 6px;")
            rules.addWidget(label, index // 2, index % 2)
        layout.addLayout(rules)

        delivery_title = make_step_header("4 交付说明")
        layout.addWidget(delivery_title)
        bottom = QHBoxLayout()
        bottom.addWidget(
            self._info_card(
                "交付边界",
                "最终交付为单个 exe，内置 ADB 和投屏组件。root / remount 属于工程师操作，量产设备不支持通常是系统限制。",
            ),
            2,
        )
        bottom.addWidget(
            self._info_card(
                "常见问题",
                "设备未授权：请在设备屏幕确认 USB 调试授权。\n网络设备只显示候选：端口响应但 ADB 未验证成功。\n截图损坏：工具会校验 PNG，并失败时切换备用截图方式。",
            ),
            3,
        )
        layout.addLayout(bottom)

        note = QLabel("失败策略：权限不足、不支持或超时都会记录到报告和状态文件；bugreport 可能耗时较长，卡在该项时优先等待。")
        note.setWordWrap(True)
        note.setStyleSheet(PANEL_HINT_STYLE)
        layout.addWidget(note)

    @staticmethod
    def _info_card(title: str, body: str) -> QFrame:
        card = QFrame()
        card.setObjectName("infoCard")
        card.setStyleSheet("QFrame#infoCard { background: #ffffff; border: 1px solid #dfe6f0; border-radius: 8px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 500; color: #1f2937;")
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet(MUTED_TEXT_STYLE)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return card
