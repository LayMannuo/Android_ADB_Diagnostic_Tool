from __future__ import annotations

from pathlib import PurePosixPath, Path

from .adb_manager import AdbManager
from .command_runner import CommandRunner, CommandResult
from .runtime_logger import RuntimeLogger
from .utils import ensure_dir


DIRECTORY_TARGET_NAMES = {
    "Download",
    "Documents",
    "Movies",
    "Pictures",
    "Music",
    "bin",
    "app",
    "priv-app",
    "lib",
    "lib64",
    "xbin",
    "tmp",
}


def normalize_push_device_path(local_file: Path, device_path: str) -> str:
    target = (device_path or "").strip().replace("\\", "/") or "/sdcard/Download/"
    filename = local_file.name
    if not filename:
        return target
    if target.endswith("/"):
        return target + filename

    final_segment = PurePosixPath(target).name
    if final_segment in DIRECTORY_TARGET_NAMES or ("." not in final_segment and local_file.suffix):
        return target.rstrip("/") + "/" + filename
    return target


class FileTransfer:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.log_file = ensure_dir(output_root / "99_tool_runtime") / "file_transfer_log.txt"
        self.logger = RuntimeLogger(self.log_file)

    def push(self, runner: CommandRunner, local_file: Path, device_path: str) -> CommandResult:
        if not local_file.exists():
            self.logger.write(f"本地文件不存在：{local_file}")
        target_path = normalize_push_device_path(local_file, device_path)
        result = self.adb.run(["push", str(local_file), target_path], runner, self.log_file, "file_transfer", "adb_push", 300)
        if result.success:
            result.error = f"实际推送目标：{target_path}"
        self.logger.write(f"push 结果：{result.status} {result.error}")
        return result

    def pull(self, runner: CommandRunner, device_path: str, local_dir: Path) -> CommandResult:
        ensure_dir(local_dir)
        result = self.adb.run(["pull", device_path, str(local_dir)], runner, self.log_file, "file_transfer", "adb_pull", 300)
        if result.success:
            result.error = f"已拉取到：{local_dir}"
        self.logger.write(f"pull 结果：{result.status} {result.error}")
        return result
