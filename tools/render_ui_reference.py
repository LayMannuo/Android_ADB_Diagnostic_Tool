from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from app.core.apk_installer import ApkInfo
from app.core.network_adb import DeviceRecord
from app.gui.main_window import MainWindow
from app.gui.styles import RESULT_SUCCESS_STYLE, configure_application_font


SCREENSHOT_SIZE = (1585, 1000)
SCREENSHOTS = [
    (0, "01_device_connection.png"),
    (1, "02_quick_diagnosis.png"),
    (2, "03_single_log.png"),
    (3, "04_apk_install.png"),
    (4, "05_feature_description.png"),
]


def demo_devices() -> list[DeviceRecord]:
    return [
        DeviceRecord(
            serial="76A04618",
            status="已可调试",
            connection="数据线连接",
            endpoint="76A04618",
            model="AIoT3576-E",
            brand="rockchip",
            android="14",
        ),
        DeviceRecord(
            serial="192.168.1.103:5566",
            status="已可调试",
            connection="网络 ADB 连接",
            endpoint="192.168.1.103:5566",
            model="F002_T982",
            brand="Amlogic",
            android="14",
        ),
        DeviceRecord(
            serial="192.168.1.70:5566",
            status="候选设备",
            connection="网段扫描候选",
            endpoint="192.168.1.70:5566",
            model="DS950",
            brand="Amlogic",
            android="14",
        ),
    ]


def demo_apk(output_dir: Path) -> ApkInfo:
    apk_path = output_dir / "player_1.12.1_b3_XW.apk.1"
    apk_path.write_bytes(b"demo apk")
    return ApkInfo(
        original_path=apk_path,
        install_path=apk_path,
        display_name="VMPlayer",
        package_name="com.vmds.vmplay_live",
        version_name="1.12.1",
        version_code="11201",
        size_bytes=2_170_000,
        md5="e3485cd536d6ec7f8d6c5bfd86c3f19a",
        normalized=True,
        icon_path=None,
        parse_status="ok",
        parse_message="APK 信息已解析，可安装。",
    )


def prepare_window(app: QApplication, output_dir: Path) -> MainWindow:
    configure_application_font(app)
    window = MainWindow()
    window.resize(*SCREENSHOT_SIZE)
    window.start_selected_device_detail_refresh = lambda serial: None

    records = demo_devices()
    window._set_connection_devices(records)
    window.connection_panel.device_table.selectRow(0)
    window.on_connection_device_selected()
    window.run_status.setStyleSheet(RESULT_SUCCESS_STYLE)
    window.run_status.setText("成功：操作已完成。\n无需处理。")
    for line in [
        "2026-06-30 10:15:32  工具已启动，正在初始化...",
        "2026-06-30 10:15:33  ADB 路径检测：成功（adb.exe）",
        "2026-06-30 10:15:34  当前操作设备：AIoT3576-E（76A04618）",
    ]:
        window.append_log(line)

    window.apk_install_panel.set_apk_info(demo_apk(output_dir))
    window.apk_install_panel.select_debuggable_targets()
    window.single_log_panel.set_success(
        "已导出缓存日志。",
        "日志保存位置：output/single_logs/demo.txt\n\n未发现明显 crash。",
        "定位结论：等待复现后抓取",
        "关键字统计：Crash 0 / ANR 0 / 权限 0",
    )
    return window


def render(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = prepare_window(app, output_dir)
    tabs = window.centralWidget()
    if not isinstance(tabs, QTabWidget):
        raise RuntimeError("main window central widget is not QTabWidget")

    paths: list[Path] = []
    try:
        for index, filename in SCREENSHOTS:
            tabs.setCurrentIndex(index)
            if index == 0:
                window.connection_panel.mode_tabs.setCurrentIndex(1)
            app.processEvents()
            path = output_dir / filename
            if not window.grab().save(str(path)):
                raise RuntimeError(f"failed to save screenshot: {path}")
            paths.append(path)
    finally:
        window.close()
        app.quit()
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the five reference UI screenshots for design review.")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "ui_reference_redesign")
    args = parser.parse_args()
    for path in render(args.output):
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
