from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .runtime_logger import RuntimeLogger
from .utils import ensure_dir, hidden_subprocess_kwargs, now_iso, quote_command, safe_text


@dataclass
class CommandResult:
    category: str
    name: str
    command: str
    output_file: str
    start_time: str
    end_time: str
    duration_seconds: float
    success: bool
    exit_code: int | None
    status: str
    error: str


class CommandRunner:
    def __init__(self, status_file: Path, runtime_logger: RuntimeLogger | None = None):
        self.status_file = status_file
        self.runtime_logger = runtime_logger or RuntimeLogger(status_file.parent / "99_tool_runtime" / "tool_runtime_log.txt")
        ensure_dir(status_file.parent)

    def run(
        self,
        command: list[str],
        output_path: Path,
        category: str,
        name: str,
        timeout: int,
        cwd: Path | None = None,
    ) -> CommandResult:
        ensure_dir(output_path.parent)
        start = time.monotonic()
        start_iso = now_iso()
        status = "SUCCESS"
        error = ""
        exit_code: int | None = None
        output_text = ""
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                timeout=timeout,
                check=False,
                **hidden_subprocess_kwargs(),
            )
            exit_code = completed.returncode
            output_text = safe_text(completed.stdout) + safe_text(completed.stderr)
            if completed.returncode != 0:
                status = self._classify_failure(output_text)
                error = self._friendly_error(status, output_text)
        except subprocess.TimeoutExpired as exc:
            status = "TIMEOUT"
            error = "命令执行超时，已跳过该项并继续执行。"
            output_text = safe_text(exc.stdout or b"") + safe_text(exc.stderr or b"") + "\n" + error
        except FileNotFoundError as exc:
            status = "NOT_AVAILABLE"
            error = "未找到 adb 或命令不可用。"
            output_text = f"{error}\n{exc}"
        except Exception as exc:
            status = "FAILED"
            error = f"工具执行异常：{exc}"
            output_text = error
            self.runtime_logger.exception(f"执行命令失败：{quote_command(command)}", exc)

        output_path.write_text(output_text, encoding="utf-8", errors="replace")
        end_iso = now_iso()
        duration = round(time.monotonic() - start, 3)
        result = CommandResult(
            category=category,
            name=name,
            command=quote_command(command),
            output_file=str(output_path),
            start_time=start_iso,
            end_time=end_iso,
            duration_seconds=duration,
            success=status == "SUCCESS",
            exit_code=exit_code,
            status=status,
            error=error,
        )
        self.record_result(result)
        return result

    def record_result(self, result: CommandResult) -> None:
        ensure_dir(self.status_file.parent)
        data: list[dict] = []
        if self.status_file.exists():
            try:
                data = json.loads(self.status_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = []
        data.append(asdict(result))
        self.status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _classify_failure(output: str) -> str:
        lower = output.lower()
        if "permission denied" in lower or "not permitted" in lower:
            return "PERMISSION_DENIED"
        if "inaccessible or not found" in lower or "not found" in lower or "no such file" in lower:
            return "NOT_AVAILABLE"
        if "unknown command" in lower or "not supported" in lower or "unsupported" in lower:
            return "UNSUPPORTED"
        return "FAILED"

    @staticmethod
    def _friendly_error(status: str, output: str) -> str:
        if status == "PERMISSION_DENIED":
            return "设备权限不足，已记录并继续。"
        if status == "NOT_AVAILABLE":
            return "该路径或命令在当前设备上不可用，已记录并继续。"
        if status == "UNSUPPORTED":
            return "当前设备不支持该命令，已记录并继续。"
        tail = output.strip().splitlines()[-1:] or ["命令执行失败"]
        return tail[0]
