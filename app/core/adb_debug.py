from __future__ import annotations

import shlex
from pathlib import Path


SERIAL_FREE_COMMANDS = {"devices", "version", "connect", "disconnect", "pair", "start-server", "kill-server"}
INTERACTIVE_SHELL_COMMANDS = {"su", "sh", "top", "logcat", "vi", "vim", "nano", "screenrecord"}


def build_adb_debug_command(command_text: str, shell_mode: bool) -> tuple[list[str], bool, str]:
    command_text = command_text.strip()
    if shell_mode:
        return ["shell", command_text], True, f"$ {command_text}"

    parts = shlex.split(command_text, posix=False)
    if parts and parts[0].lower() == "adb":
        parts = parts[1:]
    parts = [_strip_wrapping_quotes(part) for part in parts]
    use_serial = bool(parts and parts[0] not in SERIAL_FREE_COMMANDS)
    return parts, use_serial, f"adb {command_text}"


def build_external_shell_command(adb_path: Path | str, serial: str | None = None) -> list[str]:
    adb = str(adb_path).replace("/", "\\")
    if serial:
        shell_command = f'"{adb}" -s "{serial}" shell'
    else:
        shell_command = f'"{adb}" shell'
    return ["cmd", "/k", shell_command]


def needs_external_shell(command_text: str) -> bool:
    first = command_text.strip().split(maxsplit=1)[0].lower() if command_text.strip() else ""
    return first in INTERACTIVE_SHELL_COMMANDS


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
