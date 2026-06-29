from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.core.adb_debug import build_adb_debug_command, build_external_shell_command, needs_external_shell
from app.core.adb_manager import AdbManager
from app.core.utils import hidden_subprocess_kwargs, safe_text
from app.gui.styles import style_button


class AdbCommandWorker(QThread):
    done = Signal(str)

    def __init__(self, adb: AdbManager, command_text: str, shell_mode: bool):
        super().__init__()
        self.adb = adb
        self.command_text = command_text
        self.shell_mode = shell_mode
        self.process: subprocess.Popen | None = None

    def run(self):
        command, use_serial, prefix = build_adb_debug_command(self.command_text, self.shell_mode)
        code: int | None = None
        output = ""
        try:
            self.process = subprocess.Popen(
                self.adb.build_command(command, use_serial=use_serial),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **hidden_subprocess_kwargs(),
            )
            stdout, _ = self.process.communicate(timeout=120)
            code = self.process.returncode
            output = safe_text(stdout or b"")
        except subprocess.TimeoutExpired:
            self.stop()
            output = "命令执行超时，已停止。"
        except Exception as exc:
            output = f"命令执行异常：{exc}"
        self.done.emit(f"{prefix}\n{output}\n退出码：{code}\n")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()


class AdbDebugWindow(QWidget):
    def __init__(self, adb: AdbManager, project_root: Path):
        super().__init__()
        self.adb = adb
        self.project_root = project_root
        self.shell_mode = True
        self.worker: AdbCommandWorker | None = None
        self.setWindowTitle("ADB 调试窗口")
        self.resize(860, 560)
        self.setMinimumSize(520, 320)
        layout = QVBoxLayout(self)
        self.mode_label = QLabel("当前模式：adb shell 简易模式。需要连续 cd、su、top、logcat 等完整交互时，将自动打开真实 CMD Shell。")
        self.mode_label.setWordWrap(True)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("命令输出会显示在这里，可选中复制给研发或 FAE。")
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("例如：getprop ro.product.model；输入 exit 切换模式")
        self.run_button = QPushButton("执行")
        self.stop_button = QPushButton("停止")
        self.clear_button = QPushButton("清空")
        self.save_button = QPushButton("保存输出")
        self.cmd_button = QPushButton("打开真实 CMD Shell")
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.run_button)
        input_row.addWidget(self.stop_button)
        input_row.addWidget(self.cmd_button)
        input_row.addWidget(self.save_button)
        input_row.addWidget(self.clear_button)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.output)
        layout.addLayout(input_row)
        self.run_button.clicked.connect(self.run_command)
        self.stop_button.clicked.connect(self.stop_command)
        self.cmd_button.clicked.connect(self.open_external_shell)
        self.clear_button.clicked.connect(self.output.clear)
        self.save_button.clicked.connect(self.save_output)
        self.input.returnPressed.connect(self.run_command)
        self.stop_button.setEnabled(False)
        style_button(self.run_button, "primary", "执行当前输入的 ADB 或 shell 命令。")
        style_button(self.stop_button, "danger", "停止当前正在执行的命令。")
        style_button(self.cmd_button, "engineer", "打开 Windows CMD，并直接进入 adb shell。")
        style_button(self.save_button, "secondary", "保存当前窗口输出到 output/99_tool_runtime。")
        style_button(self.clear_button, "secondary", "清空当前窗口显示，不删除已保存文件。")
        self.output.append("已进入 adb shell 简易模式。输入 exit 可回到 ADB 命令模式；需要完整 shell 时会打开真实 CMD。")

    def run_command(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        if self.shell_mode and self._needs_external_shell(text):
            self.output.append(f"检测到交互式命令：{text}，已自动打开真实 CMD Shell。")
            self.open_external_shell()
            return
        if self.shell_mode and text.lower() == "exit":
            self.shell_mode = False
            self.mode_label.setText(f"当前模式：ADB 命令模式。工作目录：{self.project_root}。输入 shell 回到 adb shell。")
            self.output.append("已退出 shell，回到软件 ADB 命令模式。")
            return
        if not self.shell_mode and text.lower() == "shell":
            self.shell_mode = True
            self.mode_label.setText("当前模式：adb shell 简易模式。需要连续 cd、su、top、logcat 等完整交互时，将自动打开真实 CMD Shell。")
            self.output.append("已进入 adb shell 简易模式。")
            return
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.output.append("正在运行：" + ("adb shell " if self.shell_mode else "adb ") + text)
        self.worker = AdbCommandWorker(self.adb, text, self.shell_mode)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def on_done(self, output: str):
        self.output.append(output)
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def stop_command(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1000)
            self.output.append("已停止当前命令。")
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def save_output(self):
        path = self.project_root / "output" / "99_tool_runtime" / "adb_debug_output.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.output.toPlainText(), encoding="utf-8", errors="replace")
        self.output.append(f"输出已保存：{path}")

    def open_external_shell(self):
        adb_path = self.adb.adb_path or self.adb.find_adb() or "adb"
        command = build_external_shell_command(adb_path, self.adb.serial)
        try:
            subprocess.Popen(command, cwd=str(self.project_root), creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.output.append("已打开真实 CMD Shell。关闭 CMD 窗口即可退出该 shell。")
        except Exception as exc:
            self.output.append(f"打开 CMD Shell 失败：{exc}")

    @staticmethod
    def _needs_external_shell(text: str) -> bool:
        return needs_external_shell(text)
