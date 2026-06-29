from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .command_runner import CommandRunner, CommandResult
from .runtime_logger import RuntimeLogger
from .utils import (
    app_base_dir,
    hidden_subprocess_kwargs,
    is_frozen_resource_path,
    resource_base_dir,
    safe_text,
    stage_runtime_tool_dir,
)


class AdbManager:
    SERIAL_FREE_COMMANDS = {"devices", "version", "start-server", "kill-server", "connect", "disconnect", "pair"}

    def __init__(self, project_root: Path | None = None, serial: str | None = None):
        self.project_root = project_root or app_base_dir()
        self.serial = serial
        self.adb_path = self.find_adb()

    def find_adb(self) -> Path | None:
        for root in [self.project_root, resource_base_dir()]:
            bundled = root / "tools" / "adb" / "adb.exe"
            if bundled.exists():
                if is_frozen_resource_path(bundled):
                    staged = stage_runtime_tool_dir(bundled.parent, "adb") / "adb.exe"
                    if staged.exists():
                        return staged
                return bundled
        system = shutil.which("adb")
        return Path(system) if system else None

    def set_serial(self, serial: str | None) -> None:
        self.serial = serial or None

    def is_available(self) -> bool:
        self.adb_path = self.find_adb()
        return self.adb_path is not None

    def build_command(self, args: list[str], use_serial: bool = True) -> list[str]:
        if not self.adb_path:
            self.adb_path = self.find_adb()
        adb = str(self.adb_path or "adb")
        if use_serial and self.serial and args and args[0] not in self.SERIAL_FREE_COMMANDS:
            return [adb, "-s", self.serial, *args]
        return [adb, *args]

    def run(
        self,
        args: list[str],
        runner: CommandRunner,
        output_path: Path,
        category: str,
        name: str,
        timeout: int,
        use_serial: bool = True,
    ) -> CommandResult:
        return runner.run(self.build_command(args, use_serial=use_serial), output_path, category, name, timeout)

    def quick_run(self, args: list[str], timeout: int = 10, use_serial: bool = True) -> tuple[int | None, str]:
        try:
            completed = subprocess.run(
                self.build_command(args, use_serial=use_serial),
                capture_output=True,
                timeout=timeout,
                check=False,
                **hidden_subprocess_kwargs(),
            )
            return completed.returncode, safe_text(completed.stdout) + safe_text(completed.stderr)
        except subprocess.TimeoutExpired:
            return None, "命令执行超时。"
        except FileNotFoundError:
            return None, "未找到 adb。请将 adb.exe 放入 tools/adb/ 或加入系统 PATH。"
        except Exception as exc:
            RuntimeLogger(self.project_root / "output" / "tool_runtime_log.txt").exception("quick_run 异常", exc)
            return None, f"工具执行异常：{exc}"

    def list_devices(self) -> list[dict[str, str]]:
        _, output = self.quick_run(["devices", "-l"], timeout=10, use_serial=False)
        devices: list[dict[str, str]] = []
        for line in output.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            serial = parts[0]
            state = parts[1] if len(parts) > 1 else "unknown"
            devices.append({"serial": serial, "state": state, "raw": line})
        return devices

    def get_property(self, prop: str) -> str:
        _, output = self.quick_run(["shell", "getprop", prop], timeout=8)
        return output.strip()
