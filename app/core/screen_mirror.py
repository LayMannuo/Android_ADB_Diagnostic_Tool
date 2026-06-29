from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .utils import resource_base_dir


@dataclass(frozen=True)
class ScreenMirrorResult:
    success: bool
    message: str
    solution: str


def find_scrcpy(project_root: Path, include_resource: bool = True, include_path: bool = True) -> Path | None:
    candidates = [project_root / "tools" / "scrcpy" / "scrcpy.exe"]
    if include_resource:
        candidates.append(resource_base_dir() / "tools" / "scrcpy" / "scrcpy.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if not include_path:
        return None
    system = shutil.which("scrcpy")
    return Path(system) if system else None


def start_screen_mirror(
    project_root: Path,
    serial: str | None = None,
    include_resource: bool = True,
    include_path: bool = True,
) -> ScreenMirrorResult:
    scrcpy = find_scrcpy(project_root, include_resource=include_resource, include_path=include_path)
    if not scrcpy:
        return ScreenMirrorResult(
            False,
            "未找到投屏组件 scrcpy。",
            "解决：将 scrcpy.exe 放入 tools/scrcpy/，或把 scrcpy 加入系统 PATH；ADB 本身不能直接显示实时画面。",
        )
    command = [str(scrcpy)]
    if serial:
        command.extend(["-s", serial])
    try:
        subprocess.Popen(command, cwd=str(scrcpy.parent))
        return ScreenMirrorResult(True, "投屏窗口已启动。", "如果没有画面，请确认设备已授权 USB 调试并保持亮屏。")
    except Exception as exc:
        return ScreenMirrorResult(False, f"投屏启动失败：{exc}", "解决：确认 scrcpy 文件完整、设备已连接并授权。")
