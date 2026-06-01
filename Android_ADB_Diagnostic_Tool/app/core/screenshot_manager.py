from __future__ import annotations

import subprocess
from pathlib import Path

from .adb_manager import AdbManager
from .command_runner import CommandResult, CommandRunner
from .runtime_logger import RuntimeLogger
from .utils import ensure_dir, hidden_subprocess_kwargs, now_iso, sanitize_filename, timestamp


class ScreenshotManager:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = output_root
        self.runtime_dir = ensure_dir(output_root / "99_tool_runtime")
        self.logger = RuntimeLogger(self.runtime_dir / "screenshot_log.txt")

    def capture(self, runner: CommandRunner, serial: str | None = None, target_dir: Path | None = None) -> Path | None:
        if serial:
            self.adb.set_serial(serial)
        target_dir = ensure_dir(target_dir or self.output_root / "screenshots")
        filename = f"screenshot_{sanitize_filename(self.adb.serial or 'device')}_{timestamp()}.png"
        local_file = target_dir / filename
        try:
            command = self.adb.build_command(["exec-out", "screencap", "-p"])
            completed = subprocess.run(
                command,
                capture_output=True,
                timeout=30,
                check=False,
                **hidden_subprocess_kwargs(),
            )
            if completed.returncode == 0 and completed.stdout:
                local_file.write_bytes(completed.stdout)
                runner.record_result(
                    CommandResult(
                        category="media",
                        name="screenshot_exec_out",
                        command=" ".join(command),
                        output_file=str(local_file),
                        start_time=now_iso(),
                        end_time=now_iso(),
                        duration_seconds=0,
                        success=True,
                        exit_code=0,
                        status="SUCCESS",
                        error="",
                    )
                )
        except Exception as exc:
            self.logger.write(f"exec-out 截图失败，尝试备用方案：{exc}")
        if local_file.exists() and local_file.stat().st_size > 0:
            self.logger.write(f"截图成功：{local_file}")
            return local_file

        remote = "/sdcard/fae_screenshot.png"
        self.adb.run(["shell", "screencap", "-p", remote], runner, self.runtime_dir / "screencap_fallback.txt", "media", "screenshot_fallback_create", 30)
        pull = self.adb.run(["pull", remote, str(local_file)], runner, self.runtime_dir / "screencap_pull.txt", "media", "screenshot_fallback_pull", 60)
        self.adb.run(["shell", "rm", remote], runner, self.runtime_dir / "screencap_cleanup.txt", "media", "screenshot_fallback_cleanup", 15)
        if pull.success and local_file.exists():
            self.logger.write(f"截图成功：{local_file}")
            return local_file
        self.logger.write("截图失败，已记录到 command_status.json")
        return None

    def record_screen(self, runner: CommandRunner, target_dir: Path | None = None, seconds: int = 10) -> Path | None:
        target_dir = ensure_dir(target_dir or self.output_root / "screenrecords")
        filename = f"screenrecord_{sanitize_filename(self.adb.serial or 'device')}_{timestamp()}.mp4"
        local_file = target_dir / filename
        remote = "/sdcard/fae_screen.mp4"
        create = self.adb.run(
            ["shell", "screenrecord", remote, "--time-limit", str(seconds)],
            runner,
            self.runtime_dir / "screenrecord_create.txt",
            "media",
            "screenrecord_create",
            seconds + 20,
        )
        if not create.success:
            self.logger.write("录屏命令失败或设备不支持 screenrecord。")
            return None
        pull = self.adb.run(["pull", remote, str(local_file)], runner, self.runtime_dir / "screenrecord_pull.txt", "media", "screenrecord_pull", 60)
        self.adb.run(["shell", "rm", remote], runner, self.runtime_dir / "screenrecord_cleanup.txt", "media", "screenrecord_cleanup", 15)
        if pull.success and local_file.exists():
            self.logger.write(f"录屏成功：{local_file}")
            return local_file
        return None
