from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemountStatus:
    success: bool
    message: str
    solution: str


def evaluate_remount_result(exit_code: int | None, output: str) -> RemountStatus:
    text = (output or "").lower()
    if exit_code == 0 and any(token in text for token in ["remount succeeded", "remounted", "now remounting"]):
        return RemountStatus(True, "remount 成功：系统分区可能已切换为可写。", "工程师可继续执行需要写系统分区的操作。")
    if "not root" in text or "adbd cannot run as root" in text or "root" in text and exit_code != 0:
        return RemountStatus(False, "remount 失败：设备未 root 或量产固件限制。", "解决：先执行 adb root；如果提示量产版本不支持 root，则属于设备系统限制。")
    if "verity" in text or "disable-verity" in text:
        return RemountStatus(False, "remount 未完全生效：设备启用了 verified boot/verity。", "解决：工程机可按提示 disable-verity 后重启；客户量产设备通常无法处理。")
    if "permission denied" in text or "operation not permitted" in text:
        return RemountStatus(False, "remount 失败：权限不足。", "解决：确认设备授权、root 状态和固件权限。普通客户无需处理。")
    if exit_code == 0:
        return RemountStatus(True, "remount 命令返回成功，但未发现明确成功关键字。", "建议工程师再验证目标分区是否可写；普通客户可忽略。")
    return RemountStatus(False, "remount 失败：未识别的设备返回。", "解决：查看 adb remount 输出；通常与 root、verity 或动态分区权限有关。")
