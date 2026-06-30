from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return app_base_dir()


def local_app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Android_ADB_Diagnostic_Tool"
        return Path.home() / "AppData" / "Local" / "Android_ADB_Diagnostic_Tool"
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "Android_ADB_Diagnostic_Tool"
    return Path.home() / ".local" / "share" / "Android_ADB_Diagnostic_Tool"


def runtime_tools_dir() -> Path:
    return local_app_data_dir() / "runtime_tools"


def is_frozen_resource_path(path: Path) -> bool:
    if not getattr(sys, "frozen", False):
        return False
    try:
        path.resolve().relative_to(resource_base_dir())
        return True
    except (OSError, ValueError):
        return False


def stage_runtime_tool_dir(source_dir: Path, tool_name: str | None = None) -> Path:
    source_dir = source_dir.resolve()
    if not source_dir.exists():
        return source_dir

    target_dir = runtime_tools_dir() / (tool_name or source_dir.name)
    if _same_path(source_dir, target_dir):
        return source_dir

    signature = _directory_signature(source_dir)
    marker = target_dir / ".source_files"
    if marker.exists():
        try:
            if marker.read_text(encoding="utf-8") == signature:
                return target_dir
        except OSError:
            pass

    copied_ok = True
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.rglob("*")):
        relative = source.relative_to(source_dir)
        target = target_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if _same_file_size(source, target):
            continue
        try:
            shutil.copy2(source, target)
        except OSError:
            copied_ok = False

    if copied_ok:
        try:
            marker.write_text(signature, encoding="utf-8")
        except OSError:
            pass
    return target_dir


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _same_file_size(left: Path, right: Path) -> bool:
    try:
        return right.exists() and left.stat().st_size == right.stat().st_size
    except OSError:
        return False


def _directory_signature(source_dir: Path) -> str:
    rows = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            try:
                rows.append(f"{path.relative_to(source_dir).as_posix()}:{path.stat().st_size}")
            except OSError:
                continue
    return "\n".join(rows)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_text(data: bytes | str) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data).encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def sanitize_filename(value: str, default: str = "unknown") -> str:
    value = safe_text(value).strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    value = re.sub(r"\s+", "_", value)
    value = value.strip(" ._")
    return value or default


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def open_in_explorer(path: Path) -> None:
    path = path.resolve()
    if path.is_file():
        path = path.parent
    os.startfile(str(path))


def open_file_default(path: Path) -> None:
    os.startfile(str(path.resolve()))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def quote_command(parts: list[str]) -> str:
    return " ".join(f'"{p}"' if " " in p else p for p in parts)


def hidden_subprocess_kwargs() -> dict:
    if os.name == "nt":
        return {
            "creationflags": subprocess.CREATE_NO_WINDOW,
            "startupinfo": _hidden_startupinfo(),
        }
    return {}


def _hidden_startupinfo():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo
