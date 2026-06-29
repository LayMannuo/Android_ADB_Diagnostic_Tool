from __future__ import annotations

import os
import re
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
