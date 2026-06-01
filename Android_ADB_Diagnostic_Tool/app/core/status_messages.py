from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusDetail:
    message: str
    solution: str
    color: str


def status_detail(status: str, error: str = "") -> StatusDetail:
    status = (status or "UNKNOWN").upper()
    error = error or ""
    if status == "SUCCESS":
        return StatusDetail("成功：操作已完成。", "无需处理。", "green")
    if status == "TIMEOUT":
        return StatusDetail(
            "失败：命令执行超时。",
            "解决：重新插拔 USB、确认设备解锁并允许 USB 调试；如果设备很慢，可稍后重试。",
            "red",
        )
    if status == "PERMISSION_DENIED":
        return StatusDetail(
            "失败：设备权限不足。",
            "解决：普通客户可忽略该项；工程师可尝试 adb root / adb remount，量产固件不支持时属于设备限制。",
            "red",
        )
    if status == "NOT_AVAILABLE":
        return StatusDetail(
            "失败：命令、路径或设备能力不可用。",
            "解决：确认设备已连接并授权；如果是 /data、/system 等路径，可能需要更高权限。",
            "red",
        )
    if status == "UNSUPPORTED":
        return StatusDetail(
            "失败：当前设备不支持该命令。",
            "解决：换用其它日志项继续分析；该失败不影响一键诊断包生成。",
            "red",
        )
    if "unauthorized" in error.lower():
        return StatusDetail(
            "失败：设备未授权。",
            "解决：请在 Android 设备弹窗中点击“允许 USB 调试”，然后重新检测设备。",
            "red",
        )
    if "offline" in error.lower():
        return StatusDetail(
            "失败：设备处于 offline 状态。",
            "解决：重新插拔 USB，关闭再打开 USB 调试，必要时点击“重启 ADB 服务”。",
            "red",
        )
    return StatusDetail(
        f"失败：{error or '命令执行失败。'}",
        "解决：确认设备连接、USB 调试授权、网络连通和目标路径权限后重试。",
        "red",
    )
