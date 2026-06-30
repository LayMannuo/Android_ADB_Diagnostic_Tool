from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from app.core.apk_installer import ApkInfo, ApkInstallOptions
from app.core.network_adb import DeviceRecord
from app.gui.styles import (
    CARD_TITLE_STYLE,
    MUTED_TEXT_STYLE,
    PANEL_HINT_STYLE,
    RESULT_FAILURE_STYLE,
    RESULT_IDLE_STYLE,
    RESULT_RUNNING_STYLE,
    RESULT_SUCCESS_STYLE,
    SUMMARY_PILL_STYLE,
    make_step_header,
    style_button,
    style_card,
)


class ApkInstallPanel(QFrame):
    file_selected = Signal(str)
    files_selected = Signal(list)

    def __init__(self):
        super().__init__()
        self._title = "APK 安装"
        self.setAcceptDrops(True)
        self.current_apk: ApkInfo | None = None
        self.apk_queue: list[ApkInfo] = []
        self.failed_queue: list[ApkInfo] = []
        self.target_devices: list[DeviceRecord] = []
        self.failed_target_devices: list[DeviceRecord] = []
        self._updating_targets = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        style_card(self)

        title = QLabel("APK 安装")
        title.setStyleSheet(CARD_TITLE_STYLE)
        subtitle = QLabel("选择一个或多个 APK，勾选目标设备，最后点击一次开始安装。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(MUTED_TEXT_STYLE)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.start_install_button = QPushButton("开始安装")
        style_button(self.start_install_button, "success", "按待安装 APK 和已勾选设备串行执行安装。", "install")
        self.start_install_button.setEnabled(False)

        readiness_title = make_step_header("1 安装准备")
        layout.addWidget(readiness_title)
        self.install_readiness_frame = QFrame()
        self.install_readiness_frame.setObjectName("installReadiness")
        self.install_readiness_frame.setStyleSheet("QFrame#installReadiness { background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; }")
        readiness = QHBoxLayout(self.install_readiness_frame)
        readiness.setContentsMargins(12, 10, 12, 10)
        readiness.setSpacing(10)
        self.apk_count_value = QLabel("未选择 APK")
        self.target_count_value = QLabel("未选择设备")
        self.options_value = QLabel("选项：-r")
        self.ready_state_value = QLabel("状态：未就绪")
        self.primary_apk_summary = QLabel("应用：未选择")
        for label in [self.apk_count_value, self.target_count_value, self.options_value, self.ready_state_value, self.primary_apk_summary]:
            label.setStyleSheet(SUMMARY_PILL_STYLE)
            readiness.addWidget(label)
        readiness.addStretch(1)
        readiness.addWidget(self.start_install_button)
        layout.addWidget(self.install_readiness_frame)

        step1 = make_step_header("2 选择 APK")
        layout.addWidget(step1)

        self.drop_hint = QLabel("拖拽 APK 到这里，或点击添加 APK。文件名类似 1.apk(1).1 会自动识别为 APK。")
        self.drop_hint.setWordWrap(True)
        self.drop_hint.setMinimumHeight(58)
        self.drop_hint.setStyleSheet(
            "font-size: 14px; font-weight: 500; color: #174ea6; padding: 12px;"
            "border: 1px dashed #9bbcff; background: #f4f8ff; border-radius: 7px;"
        )
        layout.addWidget(self.drop_hint)

        actions = QHBoxLayout()
        self.choose_button = QPushButton("添加 APK")
        self.choose_many_button = QPushButton("选择多个 APK")
        self.choose_folder_button = QPushButton("选择文件夹")
        self.install_button = QPushButton("安装到当前设备")
        self.clear_button = QPushButton("清空")
        self.open_button = QPushButton("打开安装日志目录")
        style_button(self.choose_button, "primary", "选择一个或多个 APK 文件加入待安装列表。", "file")
        style_button(self.choose_many_button, "secondary", "一次选择多个 APK 加入待安装列表。", "list")
        style_button(self.choose_folder_button, "secondary", "扫描文件夹中的 APK 并加入待安装列表。", "folder")
        style_button(self.install_button, "secondary", "把当前 APK 安装到“设备连接”页当前选中的设备。", "install")
        style_button(self.clear_button, "secondary", "清空当前页面显示。", "clear")
        style_button(self.open_button, "secondary", "打开 APK 安装输出目录。", "folder")
        self.install_button.setEnabled(False)
        self.install_button.hide()
        self.choose_many_button.hide()
        actions.addWidget(self.choose_button)
        actions.addWidget(self.choose_folder_button)
        actions.addWidget(self.install_button)
        actions.addStretch(1)
        actions.addWidget(self.clear_button)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)

        target_title = make_step_header("3 选择安装目标")
        layout.addWidget(target_title)

        self.target_summary = QLabel("未发现设备。请先在“设备连接”页使用数据线连接、网络连接或网段扫描。")
        self.target_summary.setWordWrap(True)
        self.target_summary.setStyleSheet(MUTED_TEXT_STYLE)
        layout.addWidget(self.target_summary)
        target_actions = QHBoxLayout()
        self.select_debuggable_targets_button = QPushButton("全选已可调试")
        self.clear_targets_button = QPushButton("清空选择")
        self.install_targets_button = QPushButton("安装到选中设备")
        self.retry_failed_targets_button = QPushButton("重试失败项")
        style_button(self.select_debuggable_targets_button, "secondary", "勾选所有状态为已可调试的设备。", "check")
        style_button(self.clear_targets_button, "secondary", "清空目标设备选择。", "clear")
        style_button(self.install_targets_button, "success", "把当前 APK 串行安装到勾选的设备。", "install")
        style_button(self.retry_failed_targets_button, "secondary", "仅重试上次安装失败的设备。", "refresh")
        self.install_targets_button.setEnabled(False)
        self.install_targets_button.hide()
        self.retry_failed_targets_button.setEnabled(False)
        self.retry_failed_targets_button.hide()
        target_actions.addStretch(1)
        target_actions.addWidget(self.select_debuggable_targets_button)
        target_actions.addWidget(self.clear_targets_button)
        target_actions.addWidget(self.install_targets_button)
        target_actions.addWidget(self.retry_failed_targets_button)
        layout.addLayout(target_actions)

        self.target_device_table = QTableWidget(0, 7)
        self.target_device_table.setHorizontalHeaderLabels(["选择", "设备", "连接方式", "状态", "系统", "序列号/IP", "安装结果"])
        self.target_device_table.verticalHeader().setVisible(False)
        self.target_device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.target_device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.target_device_table.setAlternatingRowColors(True)
        self.target_device_table.setMinimumHeight(160)
        self.target_device_table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf2; border-radius: 6px; gridline-color: #edf1f6; selection-background-color: #dbeafe; selection-color: #111827; }"
            "QHeaderView::section { background: #f8fafc; color: #374151; font-weight: 500; padding: 7px; border: none; border-right: 1px solid #e5eaf2; }"
            "QTableWidget::item { padding: 6px; }"
        )
        target_header = self.target_device_table.horizontalHeader()
        target_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(5, QHeaderView.Stretch)
        target_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.target_device_table)

        queue_title = make_step_header("4 待安装 APK")
        layout.addWidget(queue_title)

        self.queue_table = QTableWidget(0, 7)
        self.queue_table.setHorizontalHeaderLabels(["序号", "应用", "包名", "版本", "大小", "文件", "状态"])
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setSelectionMode(QTableWidget.SingleSelection)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setMinimumHeight(170)
        self.queue_table.setStyleSheet(
            "QTableWidget { border: 1px solid #e5eaf2; border-radius: 6px; gridline-color: #edf1f6; selection-background-color: #dbeafe; selection-color: #111827; }"
            "QHeaderView::section { background: #f8fafc; color: #374151; font-weight: 500; padding: 7px; border: none; border-right: 1px solid #e5eaf2; }"
            "QTableWidget::item { padding: 6px; }"
        )
        queue_header = self.queue_table.horizontalHeader()
        queue_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        queue_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        queue_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        queue_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        queue_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        queue_header.setSectionResizeMode(5, QHeaderView.Stretch)
        queue_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.queue_table)

        batch_actions = QHBoxLayout()
        self.stop_on_failure_check = QCheckBox("失败后停止队列")
        self.start_batch_button = QPushButton("开始安装队列")
        self.retry_failed_button = QPushButton("重试失败")
        self.export_result_button = QPushButton("导出安装结果")
        style_button(self.start_batch_button, "success", "按队列顺序串行安装所有 APK。", "install")
        style_button(self.retry_failed_button, "secondary", "仅把失败的 APK 重新加入队列并安装。", "refresh")
        style_button(self.export_result_button, "secondary", "导出批量安装结果，便于发给工程师。", "download")
        self.start_batch_button.setEnabled(False)
        self.start_batch_button.hide()
        self.retry_failed_button.setEnabled(False)
        self.retry_failed_button.hide()
        self.export_result_button.setEnabled(False)
        self.export_result_button.hide()
        batch_actions.addWidget(self.stop_on_failure_check)
        batch_actions.addStretch(1)
        batch_actions.addWidget(self.start_batch_button)
        batch_actions.addWidget(self.retry_failed_button)
        batch_actions.addWidget(self.export_result_button)
        layout.addLayout(batch_actions)

        step2 = make_step_header("5 确认 APK 信息与安装选项")
        layout.addWidget(step2)

        options = QHBoxLayout()
        self.replace_check = QCheckBox("覆盖安装 -r：升级或重复安装时使用")
        self.downgrade_check = QCheckBox("允许降级 -d：版本低于已安装版本时使用")
        self.grant_check = QCheckBox("授予权限 -g：自动授予运行时权限")
        self.replace_check.setChecked(True)
        for checkbox in [self.replace_check, self.downgrade_check, self.grant_check]:
            options.addWidget(checkbox)
        layout.addLayout(options)

        info_box = QFrame()
        info_box.setObjectName("apkInfoBox")
        info_box.setStyleSheet("QFrame#apkInfoBox { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 7px; }")
        info_layout = QGridLayout(info_box)
        self.icon = QLabel("图标")
        self.icon.setFixedSize(72, 72)
        self.icon.setStyleSheet("border: 1px solid #dfe3ea; color: #5f6368; padding: 6px;")
        info_layout.addWidget(self.icon, 0, 0, 3, 1)
        self.fields: dict[str, QLabel] = {}
        labels = ["应用名称", "包名", "版本名称", "版本号", "大小", "MD5", "原始文件", "安装文件", "识别状态"]
        for row, name in enumerate(labels):
            info_layout.addWidget(QLabel(name), row, 1)
            value = QLabel("未选择")
            value.setWordWrap(True)
            value.setTextInteractionFlags(value.textInteractionFlags() | Qt.TextSelectableByMouse)
            self.fields[name] = value
            info_layout.addWidget(value, row, 2)
        layout.addWidget(info_box)

        step3 = make_step_header("6 安装结果")
        layout.addWidget(step3)

        self.result = QLabel("等待选择 APK。")
        self.result.setWordWrap(True)
        self.result.setStyleSheet(RESULT_IDLE_STYLE)
        layout.addWidget(self.result)

        output_title = QLabel("ADB 输出 / FAE 调试日志")
        output_title.setStyleSheet("font-weight: 500; color: #202124;")
        layout.addWidget(output_title)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(170)
        self.output.setPlaceholderText("安装输出、失败原因和解决建议会显示在这里。")
        layout.addWidget(self.output)

        self.choose_button.clicked.connect(self.choose_file)
        self.choose_many_button.clicked.connect(self.choose_files)
        self.choose_folder_button.clicked.connect(self.choose_folder)
        self.clear_button.clicked.connect(self.clear_display)
        self.select_debuggable_targets_button.clicked.connect(self.select_debuggable_targets)
        self.clear_targets_button.clicked.connect(self.clear_target_selection)
        self.target_device_table.itemChanged.connect(self.refresh_target_summary)
        self.replace_check.toggled.connect(self.refresh_readiness_summary)
        self.downgrade_check.toggled.connect(self.refresh_readiness_summary)
        self.grant_check.toggled.connect(self.refresh_readiness_summary)

    def title(self) -> str:
        return self._title

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)
        if paths:
            if len(paths) == 1:
                self.file_selected.emit(paths[0])
            else:
                self.files_selected.emit(paths)
            event.acceptProposedAction()

    def choose_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添加 APK 文件", "", "APK 文件 (*.apk *apk*);;所有文件 (*.*)")
        if not paths:
            return
        if len(paths) == 1:
            self.file_selected.emit(paths[0])
        else:
            self.files_selected.emit(paths)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择多个 APK 文件", "", "APK 文件 (*.apk *apk*);;所有文件 (*.*)")
        if paths:
            self.files_selected.emit(paths)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含 APK 的文件夹")
        if not folder:
            return
        paths = [str(path) for path in sorted(Path(folder).glob("*.apk"))]
        if paths:
            self.files_selected.emit(paths)

    def options(self) -> ApkInstallOptions:
        return ApkInstallOptions(
            replace=self.replace_check.isChecked(),
            downgrade=self.downgrade_check.isChecked(),
            grant_permissions=self.grant_check.isChecked(),
        )

    def refresh_readiness_summary(self) -> None:
        selected_targets = len(self.selected_target_serials())
        apk_count = len(self.apk_queue)
        option_flags = []
        if self.replace_check.isChecked():
            option_flags.append("-r")
        if self.downgrade_check.isChecked():
            option_flags.append("-d")
        if self.grant_check.isChecked():
            option_flags.append("-g")
        self.apk_count_value.setText(f"APK {apk_count} 个" if apk_count else "未选择 APK")
        self.target_count_value.setText(f"已选设备 {selected_targets} 台" if selected_targets else "未选择设备")
        self.options_value.setText(f"选项：{' '.join(option_flags) if option_flags else '默认'}")
        self.ready_state_value.setText("状态：可开始安装" if apk_count and selected_targets else "状态：未就绪")
        primary = self.apk_queue[0] if self.apk_queue else None
        if primary:
            app_name = primary.display_name or primary.original_path.name
            package = primary.package_name or "包名未解析"
            version = primary.version_name or primary.version_code or "版本未解析"
            self.primary_apk_summary.setText(f"{app_name} · {package} · {version}")
        else:
            self.primary_apk_summary.setText("应用：未选择")

    def set_target_devices(self, records: list[DeviceRecord]) -> None:
        previous_selected = set(self.selected_target_serials())
        self.target_devices = list(records)
        self._updating_targets = True
        try:
            self.target_device_table.setRowCount(len(records))
            for row, record in enumerate(records):
                checked = record.serial in previous_selected or (not previous_selected and record.status == "已可调试")
                select_item = QTableWidgetItem("")
                select_item.setFlags((select_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                select_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                select_item.setData(Qt.UserRole, record.serial)
                self.target_device_table.setItem(row, 0, select_item)
                cells = [
                    record.display_name(),
                    record.connection,
                    record.status,
                    _device_system_text(record),
                    record.endpoint or record.serial,
                    "待安装" if checked else "-",
                ]
                for column, value in enumerate(cells, start=1):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if column == 3:
                        item.setForeground(_status_brush(record.status))
                    self.target_device_table.setItem(row, column, item)
        finally:
            self._updating_targets = False
        self.refresh_target_summary()

    def selected_target_serials(self) -> list[str]:
        serials: list[str] = []
        for row in range(self.target_device_table.rowCount()):
            item = self.target_device_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                serial = item.data(Qt.UserRole)
                if serial:
                    serials.append(str(serial))
        return serials

    def selected_target_records(self) -> list[DeviceRecord]:
        selected = set(self.selected_target_serials())
        return [record for record in self.target_devices if record.serial in selected]

    def select_debuggable_targets(self) -> None:
        self._set_target_checks(lambda record: record.status == "已可调试")

    def clear_target_selection(self) -> None:
        self._set_target_checks(lambda record: False)

    def _set_target_checks(self, predicate) -> None:
        self._updating_targets = True
        try:
            for row, record in enumerate(self.target_devices):
                item = self.target_device_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked if predicate(record) else Qt.Unchecked)
                    result_item = self.target_device_table.item(row, 6)
                    if result_item:
                        result_item.setText("待安装" if predicate(record) else "-")
        finally:
            self._updating_targets = False
        self.refresh_target_summary()

    def refresh_target_summary(self, *_):
        if self._updating_targets:
            return
        selected_count = len(self.selected_target_serials())
        total = len(self.target_devices)
        if not total:
            self.target_summary.setText("未发现设备。请先在“设备连接”页使用数据线连接、网络连接或网段扫描。")
        else:
            ready_count = sum(1 for record in self.target_devices if record.status == "已可调试")
            self.target_summary.setText(f"已发现 {total} 台设备，已可调试 {ready_count} 台，已选择 {selected_count} 台。")
        self._update_target_buttons()

    def mark_target_result(self, serial: str, success: bool, message: str) -> None:
        for row in range(self.target_device_table.rowCount()):
            item = self.target_device_table.item(row, 0)
            if item and item.data(Qt.UserRole) == serial:
                result_item = QTableWidgetItem("成功" if success else "失败")
                result_item.setFlags(result_item.flags() & ~Qt.ItemIsEditable)
                result_item.setToolTip(message)
                self.target_device_table.setItem(row, 6, result_item)
                return

    def _update_target_buttons(self) -> None:
        has_apk = bool(self.apk_queue)
        has_targets = bool(self.selected_target_serials())
        has_failures = bool(self.failed_queue or self.failed_target_devices)
        self.start_install_button.setEnabled(has_apk and has_targets)
        self.install_targets_button.setEnabled(has_apk and has_targets)
        self.retry_failed_targets_button.setVisible(has_failures)
        self.retry_failed_targets_button.setEnabled(has_apk and has_failures)
        self.refresh_readiness_summary()

    def set_apk_info(self, info: ApkInfo):
        self.current_apk = info
        self.install_button.setEnabled(False)
        self.set_queue([info])
        self._set_icon(info.icon_path)
        self.fields["应用名称"].setText(info.display_name or "未解析到，仍可安装")
        self.fields["包名"].setText(info.package_name or "未解析到，安装时由系统校验")
        self.fields["版本名称"].setText(info.version_name or "未解析到")
        self.fields["版本号"].setText(info.version_code or "未解析到")
        self.fields["大小"].setText(_format_size(info.size_bytes))
        self.fields["MD5"].setText(info.md5)
        self.fields["原始文件"].setText(str(info.original_path))
        self.fields["安装文件"].setText(str(info.install_path))
        status = "文件名异常，已复制并规范化为 .apk。" if info.normalized else "标准 APK，已复制到临时安装目录。"
        self.fields["识别状态"].setText(f"{status}\n{info.parse_message}")
        self.result.setStyleSheet(RESULT_SUCCESS_STYLE)
        self.result.setText("APK 已进入待安装列表。请确认包名、版本和 MD5，确认无误后点击“开始安装”。")
        self.output.setPlainText(info.parse_message)
        self._update_target_buttons()

    def add_apk_info(self, info: ApkInfo):
        self.current_apk = info
        self.install_button.setEnabled(False)
        self.apk_queue.append(info)
        self.refresh_queue_table()
        self.result.setStyleSheet(RESULT_SUCCESS_STYLE)
        self.result.setText(f"已加入待安装列表：{len(self.apk_queue)} 个 APK。确认无误后点击“开始安装”。")
        self._update_target_buttons()

    def set_queue(self, infos: list[ApkInfo]):
        self.apk_queue = list(infos)
        self.refresh_queue_table()

    def refresh_queue_table(self):
        self.queue_table.setRowCount(len(self.apk_queue))
        for row, info in enumerate(self.apk_queue):
            values = [
                str(row + 1),
                info.display_name or "未解析",
                info.package_name or "未解析",
                info.version_name or info.version_code or "未解析",
                _format_size(info.size_bytes),
                info.original_path.name,
                "待安装",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.queue_table.setItem(row, column, item)
        has_items = bool(self.apk_queue)
        self.start_batch_button.setEnabled(has_items)
        self.export_result_button.setEnabled(False)
        self._update_target_buttons()

    def mark_queue_result(self, row: int, success: bool, message: str):
        if row < 0 or row >= self.queue_table.rowCount():
            return
        item = QTableWidgetItem("成功" if success else "失败")
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setToolTip(message)
        self.queue_table.setItem(row, 6, item)

    def set_running(self, text: str):
        self.install_button.setEnabled(False)
        self.start_install_button.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.choose_many_button.setEnabled(False)
        self.choose_folder_button.setEnabled(False)
        self.start_batch_button.setEnabled(False)
        self.install_targets_button.setEnabled(False)
        self.retry_failed_targets_button.setEnabled(False)
        self.select_debuggable_targets_button.setEnabled(False)
        self.clear_targets_button.setEnabled(False)
        self.retry_failed_button.hide()
        self.retry_failed_targets_button.hide()
        self.export_result_button.hide()
        self.result.setStyleSheet(RESULT_RUNNING_STYLE)
        self.result.setText(text)

    def set_result(self, success: bool, message: str, solution: str, output: str):
        self.choose_button.setEnabled(True)
        self.choose_many_button.setEnabled(True)
        self.choose_folder_button.setEnabled(True)
        self.select_debuggable_targets_button.setEnabled(True)
        self.clear_targets_button.setEnabled(True)
        self.install_button.setEnabled(False)
        self.start_batch_button.setEnabled(bool(self.apk_queue))
        self._update_target_buttons()
        self.result.setStyleSheet(RESULT_SUCCESS_STYLE if success else RESULT_FAILURE_STYLE)
        self.result.setText(f"{message}\n{solution}")
        self.output.setPlainText(f"{message}\n{solution}\n\nADB 输出：\n{output}")

    def set_failure(self, message: str, solution: str):
        self.choose_button.setEnabled(True)
        self.choose_many_button.setEnabled(True)
        self.choose_folder_button.setEnabled(True)
        self.select_debuggable_targets_button.setEnabled(True)
        self.clear_targets_button.setEnabled(True)
        self.install_button.setEnabled(False)
        self.start_batch_button.setEnabled(bool(self.apk_queue))
        self._update_target_buttons()
        self.result.setStyleSheet(RESULT_FAILURE_STYLE)
        self.result.setText(f"{message}\n{solution}")
        self.output.setPlainText(f"{message}\n{solution}")

    def clear_display(self):
        self.current_apk = None
        self.apk_queue.clear()
        self.failed_queue.clear()
        self.failed_target_devices.clear()
        self.install_button.setEnabled(False)
        self.start_install_button.setEnabled(False)
        self.start_batch_button.setEnabled(False)
        self.retry_failed_button.setEnabled(False)
        self.export_result_button.setEnabled(False)
        self.retry_failed_button.hide()
        self.retry_failed_targets_button.hide()
        self.export_result_button.hide()
        self._update_target_buttons()
        self.queue_table.setRowCount(0)
        self.icon.clear()
        self.icon.setText("图标")
        for value in self.fields.values():
            value.setText("未选择")
        self.result.setStyleSheet(RESULT_IDLE_STYLE)
        self.result.setText("页面显示已清空。")
        self.output.clear()

    def _set_icon(self, path: Path | None):
        if path and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.icon.setPixmap(pixmap.scaled(64, 64))
                return
        self.icon.setPixmap(QPixmap())
        self.icon.setText("无图标")


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def _device_system_text(record: DeviceRecord) -> str:
    parts = []
    if record.android:
        parts.append(f"Android {record.android}")
    if record.brand:
        parts.append(record.brand)
    return " / ".join(parts) if parts else "-"


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
