from __future__ import annotations

import traceback
from pathlib import Path

from .utils import ensure_dir, now_iso


class RuntimeLogger:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        ensure_dir(log_file.parent)

    def write(self, message: str) -> None:
        with self.log_file.open("a", encoding="utf-8", errors="replace") as file:
            file.write(f"[{now_iso()}] {message}\n")

    def exception(self, message: str, exc: BaseException) -> None:
        self.write(f"{message}: {exc}")
        with self.log_file.open("a", encoding="utf-8", errors="replace") as file:
            traceback.print_exception(exc, file=file)
