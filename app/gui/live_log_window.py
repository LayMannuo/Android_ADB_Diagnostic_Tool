from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.core.adb_manager import AdbManager
from app.core.utils import ensure_dir, hidden_subprocess_kwargs, now_iso, safe_text
from app.gui.styles import style_button


class LiveLogWorker(QThread):
    line = Signal(str)
    status = Signal(str)

    def __init__(self, adb: AdbManager, save_file: Path, command: list[str] | None = None, display_command: str = "adb logcat -v time"):
        super().__init__()
        self.adb = adb
        self.save_file = save_file
        self.command = command or ["logcat", "-v", "time"]
        self.display_command = display_command
        self.process: subprocess.Popen | None = None

    def run(self):
        ensure_dir(self.save_file.parent)
        self.status.emit(f"正在运行：{self.display_command}")
        with self.save_file.open("a", encoding="utf-8", errors="replace") as log:
            try:
                marker = f"===== 工具开始持续抓取：{now_iso()}；以下输出包含设备已缓存日志，并会继续追加新日志 ====="
                log.write(marker + "\n")
                self.line.emit(marker)
                self.process = subprocess.Popen(
                    self.adb.build_command(self.command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    **hidden_subprocess_kwargs(),
                )
                assert self.process.stdout is not None
                for raw in iter(self.process.stdout.readline, b""):
                    if self.isInterruptionRequested():
                        break
                    text = safe_text(raw).rstrip()
                    log.write(text + "\n")
                    self.line.emit(text)
            finally:
                self.stop()
                self.status.emit("实时日志已停止")

    def stop(self):
        if self.process and self.process.poll() is None:
            if _terminate_process_tree(self.process):
                return
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()


class LiveLogWindow(QWidget):
    def __init__(self, adb: AdbManager, output_root: Path):
        super().__init__()
        self.adb = adb
        self.output_root = output_root
        self.worker: LiveLogWorker | None = None
        self.setWindowTitle("实时日志")
        self.resize(760, 460)
        self.setMinimumSize(420, 300)
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("开始持续抓取（含缓存）")
        self.stop_button = QPushButton("停止持续抓取")
        self.clear_button = QPushButton("清空显示")
        self.save_button = QPushButton("选择保存目录")
        style_button(self.start_button, "success", "先保存设备已缓存 logcat，再持续追加新日志。")
        style_button(self.stop_button, "warning", "停止持续日志抓取。")
        style_button(self.clear_button, "secondary", "清空窗口显示，不删除保存文件。")
        style_button(self.save_button, "secondary", "选择实时日志保存目录。")
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.save_button)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addLayout(buttons)
        layout.addWidget(self.text)
        self.save_dir = output_root / "99_tool_runtime"
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.clear_button.clicked.connect(self.text.clear)
        self.save_button.clicked.connect(self.choose_dir)

    def choose_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", str(self.output_root))
        if path:
            self.save_dir = Path(path)

    def start(self):
        if self.worker and self.worker.isRunning():
            return
        self.worker = LiveLogWorker(self.adb, self.save_dir / "live_logcat.txt")
        self.worker.line.connect(self.text.append)
        self.worker.status.connect(self.text.append)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.requestInterruption()
            self.worker.stop()
            self.worker.wait(2000)

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


def _terminate_process_tree(process: subprocess.Popen) -> bool:
    if process.poll() is not None:
        return True
    if not process.pid:
        return False
    if subprocess.os.name != "nt":
        return False
    try:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=5,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        process.wait(timeout=2)
        return process.poll() is not None
    except Exception:
        return False
