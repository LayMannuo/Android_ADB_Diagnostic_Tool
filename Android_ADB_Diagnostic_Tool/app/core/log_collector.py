from __future__ import annotations

import json
import shlex
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from .adb_manager import AdbManager
from .command_runner import CommandRunner
from .report_generator import ReportGenerator
from .runtime_logger import RuntimeLogger
from .screenshot_manager import ScreenshotManager
from .utils import ensure_dir, resource_base_dir, sanitize_filename, timestamp
from .zip_exporter import ZipExporter


class LogCollector:
    REQUIRED_DIRS = [
        "00_customer_info",
        "01_device_info",
        "02_logcat",
        "03_bugreport",
        "04_dumpsys",
        "05_crash_anr",
        "06_network",
        "07_cellular",
        "08_app_process",
        "09_media",
        "10_proc_system",
        "99_tool_runtime",
    ]

    def __init__(self, adb: AdbManager, project_root: Path):
        self.adb = adb
        self.project_root = project_root
        self.output_root = ensure_dir(project_root / "output")

    def collect(self, customer_info: dict[str, str], progress=None) -> tuple[Path, Path]:
        device_info = self.device_info_summary()
        model = sanitize_filename(device_info.get("model") or "Android")
        serial = sanitize_filename(self.adb.serial or device_info.get("serial") or "unknown")
        package_dir = self.output_root / f"Android_Diagnostic_{model}_{serial}_{timestamp()}"
        for dirname in self.REQUIRED_DIRS:
            ensure_dir(package_dir / dirname)
        runtime_logger = RuntimeLogger(package_dir / "99_tool_runtime" / "tool_runtime_log.txt")
        runner = CommandRunner(package_dir / "command_status.json", runtime_logger)
        self._write_customer_info(package_dir, customer_info)

        commands = self.load_commands()
        total = max(len(commands), 1)
        for index, item in enumerate(commands, start=1):
            if progress:
                progress(index, total, f"抓取 {item.get('description') or item.get('name')}")
            self._run_command(item, package_dir, runner)

        if progress:
            progress(total, total, "自动截图并生成报告")
        ScreenshotManager(self.adb, package_dir).capture(runner, target_dir=package_dir / "09_media")
        ReportGenerator().generate(package_dir, device_info)
        archive = ZipExporter().export(package_dir)
        return package_dir, archive

    def load_commands(self) -> list[dict]:
        config = resource_base_dir() / "app" / "config" / "commands.yaml"
        if yaml and config.exists():
            data = yaml.safe_load(config.read_text(encoding="utf-8"))
            return data or []
        return []

    def device_info_summary(self) -> dict[str, str]:
        connection = "未知"
        if self.adb.serial:
            connection = "网络 ADB" if ":" in self.adb.serial else "USB"
        return {
            "serial": self.adb.serial or self.adb.get_property("ro.serialno") or "unknown",
            "model": self.adb.get_property("ro.product.model") or "unknown",
            "brand": self.adb.get_property("ro.product.brand") or "unknown",
            "android": self.adb.get_property("ro.build.version.release") or "unknown",
            "sdk": self.adb.get_property("ro.build.version.sdk") or "unknown",
            "connection": connection,
        }

    def _run_command(self, item: dict, package_dir: Path, runner: CommandRunner) -> None:
        command = parse_adb_command(item["command"])
        if item.get("name") == "bugreport":
            command = ["bugreport", str(package_dir / "03_bugreport" / "bugreport.zip")]
        output = package_dir / item["output"]
        self.adb.run(command, runner, output, item["category"], item["name"], int(item.get("timeout", 20)))

    def _write_customer_info(self, package_dir: Path, info: dict[str, str]) -> None:
        text = "\n".join(f"{key}: {value}" for key, value in info.items())
        (package_dir / "00_customer_info" / "customer_info.txt").write_text(text, encoding="utf-8", errors="replace")
        (package_dir / "00_customer_info" / "customer_info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def parse_adb_command(command: object) -> list[str]:
    if isinstance(command, list):
        return [str(part) for part in command]
    return shlex.split(str(command), posix=True)
