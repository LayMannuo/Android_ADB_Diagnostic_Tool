from __future__ import annotations

import sys

from app.core.adb_manager import AdbManager
from app.core.screen_mirror import find_scrcpy
from app.core.utils import resource_base_dir


def smoke_test() -> int:
    base = resource_base_dir()
    if not (base / "app" / "config" / "commands.yaml").exists():
        return 2
    adb = AdbManager()
    if not adb.is_available():
        return 3
    code, output = adb.quick_run(["devices", "-l"], timeout=15, use_serial=False)
    if code != 0 or "List of devices" not in output:
        return 4
    if not find_scrcpy(base, include_resource=True, include_path=False):
        return 5
    return 0


def main() -> int:
    if "--smoke-test" in sys.argv:
        return smoke_test()

    from PySide6.QtWidgets import QApplication

    from app.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Android 通用 ADB 诊断助手")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
