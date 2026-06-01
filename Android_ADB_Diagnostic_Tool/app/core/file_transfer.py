from __future__ import annotations

from pathlib import Path

from .adb_manager import AdbManager
from .command_runner import CommandRunner, CommandResult
from .runtime_logger import RuntimeLogger
from .utils import ensure_dir


class FileTransfer:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.log_file = ensure_dir(output_root / "99_tool_runtime") / "file_transfer_log.txt"
        self.logger = RuntimeLogger(self.log_file)

    def push(self, runner: CommandRunner, local_file: Path, device_path: str) -> CommandResult:
        if not local_file.exists():
            self.logger.write(f"本地文件不存在：{local_file}")
        if not device_path.strip():
            device_path = "/sdcard/Download/"
        result = self.adb.run(["push", str(local_file), device_path], runner, self.log_file, "file_transfer", "adb_push", 300)
        self.logger.write(f"push 结果：{result.status} {result.error}")
        return result

    def pull(self, runner: CommandRunner, device_path: str, local_dir: Path) -> CommandResult:
        ensure_dir(local_dir)
        result = self.adb.run(["pull", device_path, str(local_dir)], runner, self.log_file, "file_transfer", "adb_pull", 300)
        self.logger.write(f"pull 结果：{result.status} {result.error}")
        return result
