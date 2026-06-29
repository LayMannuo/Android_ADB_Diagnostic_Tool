from __future__ import annotations

from pathlib import Path

from .adb_manager import AdbManager
from .command_runner import CommandRunner, CommandResult
from .utils import ensure_dir, sanitize_filename, timestamp


def single_log_commands() -> list[dict[str, object]]:
    items = [
        {
            "name": "logcat_history",
            "title": "历史 Logcat（推荐先用）",
            "description": "自动抓取设备当前缓存的历史日志：adb logcat -d -v time。适合客户已经复现过问题后立即抓取。",
            "command": ["logcat", "-d", "-v", "time"],
            "live_command": ["logcat", "-v", "time"],
            "live_preview_title": "实时预览：Logcat 全量日志",
            "live_placeholder": "这里显示实时 Logcat 全量输出。适合现场复现应用、系统服务、权限、网络等综合问题。",
            "clear_command": ["logcat", "-c"],
            "output": "logcat_history.txt",
            "timeout": 60,
            "focus": "历史日志",
            "customer_hint": "适合问题已经出现后立即抓取，不需要复现。",
            "fae_hint": "优先看崩溃、ANR、权限、网络和问题发生时间点前后日志。",
        },
        {
            "name": "crash_logcat",
            "title": "Crash 专项日志",
            "description": "抓取 crash buffer：adb logcat -b crash -d -v time。适合快速判断 Java/native 崩溃。",
            "command": ["logcat", "-b", "crash", "-d", "-v", "time"],
            "live_command": ["logcat", "-b", "crash", "-v", "time"],
            "live_preview_title": "实时预览：Crash buffer 崩溃日志",
            "live_placeholder": "这里显示 Crash buffer 输出。只有发生崩溃时通常才会出现关键内容。",
            "clear_command": ["logcat", "-b", "crash", "-c"],
            "output": "logcat_crash.txt",
            "timeout": 60,
            "focus": "崩溃分析",
            "customer_hint": "适合 APP 闪退、系统组件崩溃。",
            "fae_hint": "重点确认进程名、异常类型、堆栈首因和重复次数。",
        },
        {
            "name": "dmesg",
            "title": "内核 Dmesg",
            "description": "抓取内核日志：adb shell dmesg。适合分析驱动、硬件、内核报错、USB/网络底层异常；权限不足会明确提示。",
            "command": ["shell", "dmesg"],
            "live_command": ["shell", "dmesg", "-w"],
            "live_preview_title": "实时预览：内核 dmesg 日志",
            "live_placeholder": "这里显示内核 dmesg 实时输出。适合观察驱动、硬件、USB、内核权限和底层异常。",
            "clear_command": ["shell", "dmesg", "-C"],
            "output": "dmesg.txt",
            "timeout": 30,
            "focus": "内核/驱动分析",
            "customer_hint": "适合黑屏、重启、硬件异常、USB 或底层网络问题。",
            "fae_hint": "重点看 kernel panic、watchdog、driver error、avc denied、硬件枚举失败。",
        },
        {
            "name": "cellular_4g",
            "title": "4G / 蜂窝网络日志",
            "description": "抓取通用蜂窝网络状态：telephony.registry、phone、carrier_config、mobile_data 和 gsm/ril 属性。适合分析 SIM、信号、APN、移动数据问题。",
            "commands": [
                ["shell", "dumpsys", "telephony.registry"],
                ["shell", "dumpsys", "phone"],
                ["shell", "dumpsys", "carrier_config"],
                ["shell", "settings", "get", "global", "mobile_data"],
                ["shell", "getprop"],
            ],
            "live_command": ["logcat", "-b", "radio", "-v", "time"],
            "live_preview_title": "实时预览：4G/radio 蜂窝日志",
            "live_placeholder": "这里显示 radio buffer 实时输出。适合观察 SIM、注册网络、信号、APN、数据连接等问题。",
            "clear_command": ["logcat", "-b", "radio", "-c"],
            "output": "cellular_4g.txt",
            "timeout": 60,
            "focus": "4G/SIM/APN/信号分析",
            "customer_hint": "适合无服务、无 4G、不能上网、SIM/APN 异常。",
            "fae_hint": "先看 radio buffer，再结合 telephony.registry、APN、mobile_data、gsm/ril 属性。",
        },
        {
            "name": "network",
            "title": "网络状态",
            "description": "抓取 IP 地址信息：adb shell ip addr。适合判断设备是否有网卡/IP。",
            "command": ["shell", "ip", "addr"],
            "live_command": ["shell", "sh", "-c", "while true; do date; ip addr; ip route; sleep 3; done"],
            "live_preview_title": "实时预览：网络状态轮询",
            "live_placeholder": "这里每隔数秒显示 IP、路由等网络状态快照，不是 logcat。",
            "output": "network_ip_addr.txt",
            "timeout": 20,
            "focus": "网络分析",
            "customer_hint": "适合 Wi-Fi/以太网已连接但无法联网。",
            "fae_hint": "重点看 IP、路由、DNS、网关和接口状态。",
        },
        {
            "name": "device_props",
            "title": "设备属性",
            "description": "抓取 getprop。适合确认 Android 版本、型号、序列号、网络属性和系统属性。",
            "command": ["shell", "getprop"],
            "output": "device_getprop.txt",
            "timeout": 30,
            "focus": "设备信息",
            "customer_hint": "适合确认设备型号、版本、序列号是否正确。",
            "fae_hint": "重点看 ro.build、ro.product、persist、gsm、net 等属性。",
        },
        {
            "name": "dumpsys_activity",
            "title": "Activity 状态",
            "description": "抓取 activity dumpsys。适合分析前台页面、任务栈、启动失败和页面卡住问题。",
            "command": ["shell", "dumpsys", "activity"],
            "live_command": ["logcat", "-b", "main", "-b", "system", "-v", "time"],
            "live_preview_title": "实时预览：Activity 相关系统日志",
            "live_placeholder": "这里显示 main/system buffer 中与页面启动、前后台、窗口焦点相关的实时日志。",
            "output": "dumpsys_activity.txt",
            "timeout": 60,
            "focus": "页面/启动分析",
            "customer_hint": "适合页面打不开、启动慢、页面卡住。",
            "fae_hint": "结合 ActivityRecord、Task、Window focus 和启动日志判断页面状态。",
        },
    ]
    analyzer_map = {
        "logcat_history": "logcat",
        "crash_logcat": "logcat",
        "dmesg": "dmesg",
        "cellular_4g": "radio",
        "network": "network",
        "device_props": "props",
        "dumpsys_activity": "activity",
    }
    category_map = {
        "logcat_history": "应用/系统日志",
        "crash_logcat": "崩溃日志",
        "dmesg": "内核日志",
        "cellular_4g": "4G/蜂窝网络",
        "network": "网络状态",
        "device_props": "设备信息",
        "dumpsys_activity": "页面/Activity",
    }
    for item in items:
        name = str(item["name"])
        item["analyzer"] = analyzer_map.get(name, "logcat")
        item["category_title"] = category_map.get(name, "通用日志")
        item["supports_snapshot"] = bool(item.get("command") or item.get("commands"))
        item["supports_live"] = bool(item.get("live_command"))
        item["supports_clear"] = bool(item.get("clear_command"))
    return items


def analyze_log_text(text: str, analyzer: str = "logcat") -> dict[str, object]:
    lower = text.lower()
    crash_count = lower.count("fatal exception") + lower.count("crash") + lower.count("tombstone")
    anr_count = lower.count(" anr") + lower.count("application not responding") + lower.count("input dispatching timed out")
    permission_count = lower.count("permission denied") + lower.count("avc: denied") + lower.count("eacces")
    timeout_count = lower.count("timeout") + lower.count("timed out")
    dns_count = lower.count("unknown host") + lower.count("dns") + lower.count("net.dns")
    network_count = lower.count("network is unreachable") + lower.count("no route to host") + lower.count("failed to connect")
    kernel_count = (
        lower.count("kernel panic")
        + lower.count("watchdog")
        + lower.count("hung task")
        + lower.count("thermal")
        + lower.count("mmc")
        + lower.count("usb")
        + lower.count("i/o error")
    )
    radio_count = (
        lower.count("ril")
        + lower.count("radio")
        + lower.count("sim")
        + lower.count("apn")
        + lower.count("data_call")
        + lower.count("data call")
        + lower.count("registration")
    )

    conclusion = "未定位到明确高频问题"
    severity = "低"
    suggestions: list[str] = []
    evidence: list[str] = []

    if analyzer == "dmesg" and kernel_count:
        conclusion = "疑似内核/驱动/硬件底层异常"
        severity = "高"
        suggestions.append("优先分析 dmesg 中 kernel panic、watchdog、USB、MMC、thermal、I/O error 附近的时间点。")
        suggestions.append("如果出现重启/黑屏/外设异常，请同步抓取完整诊断包和问题复现步骤。")
        evidence.append(f"发现内核/驱动关键字 {kernel_count} 次。")
    elif analyzer == "radio" and radio_count:
        conclusion = "疑似 4G/蜂窝网络/SIM/APN 问题"
        severity = "中"
        suggestions.append("优先检查 SIM 状态、网络注册、APN、data call、RIL/radio 错误和问题发生时间点。")
        suggestions.append("如果客户反馈不能上网，请同时抓取网络状态和完整诊断包中的 07_cellular 目录。")
        evidence.append(f"发现 4G/radio/SIM/APN 关键字 {radio_count} 次。")
    elif crash_count:
        conclusion = "疑似应用崩溃或系统组件崩溃"
        severity = "高"
        suggestions.append("优先分析 crash 堆栈：确认进程名、异常类型、崩溃时间点和重复次数。")
        suggestions.append("如果是客户 APP 崩溃，把崩溃前后 1 分钟 logcat 发给研发。")
        evidence.append(f"发现 crash/fatal/tombstone 关键字 {crash_count} 次。")
    elif anr_count:
        conclusion = "疑似 ANR 或主线程卡顿"
        severity = "高"
        suggestions.append("优先检查 ANR 时间点附近是否有主线程阻塞、CPU/IO 压力或系统服务无响应。")
        evidence.append(f"发现 ANR/超时派发关键字 {anr_count} 次。")
    elif dns_count or network_count:
        conclusion = "疑似网络/DNS 连接问题"
        severity = "中"
        suggestions.append("检查设备 IP、网关、DNS 和路由；如果 IP ping 成功但域名失败，优先怀疑 DNS。")
        suggestions.append("建议再抓取一键诊断包中的 06_network 目录做完整网络分析。")
        evidence.append(f"发现 DNS/网络异常关键字 {dns_count + network_count} 次。")
    elif permission_count:
        conclusion = "疑似权限不足或系统路径访问受限"
        severity = "中"
        suggestions.append("确认是否访问 /data、/system、/vendor 等受限路径；工程机可尝试 adb root / adb remount。")
        evidence.append(f"发现权限不足关键字 {permission_count} 次。")
    elif timeout_count:
        conclusion = "疑似命令超时或设备响应慢"
        severity = "中"
        suggestions.append("检查 USB 线、设备负载和 ADB 稳定性；必要时重启 ADB 服务后重试。")
        evidence.append(f"发现 timeout/timed out 关键字 {timeout_count} 次。")

    if not suggestions:
        suggestions.append("未发现明显 crash/ANR/权限/网络关键字。请结合客户填写的问题时间，继续筛选对应时间段日志。")
        suggestions.append("如果问题刚复现，建议先点“抓取历史 Logcat”；如果要现场复现，点“开始实时 Logcat”。")

    return {
        "crash_count": crash_count,
        "anr_count": anr_count,
        "permission_count": permission_count,
        "timeout_count": timeout_count,
        "dns_count": dns_count,
        "network_count": network_count,
        "kernel_count": kernel_count,
        "radio_count": radio_count,
        "severity": severity,
        "conclusion": conclusion,
        "evidence": evidence,
        "suggestions": suggestions,
    }


class SingleLogCollector:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = ensure_dir(output_root / "single_logs")

    def collect(self, command_name: str, runner: CommandRunner) -> tuple[CommandResult, Path, dict[str, object]]:
        items = {item["name"]: item for item in single_log_commands()}
        item = items[command_name]
        folder = ensure_dir(self.output_root / f"{sanitize_filename(str(item['name']))}_{timestamp()}")
        output_path = folder / str(item["output"])
        if "commands" in item:
            parts = []
            result = None
            for index, command in enumerate(item["commands"], start=1):
                part_path = folder / f"{Path(str(item['output'])).stem}_{index}.txt"
                result = self.adb.run(
                    list(command),
                    runner,
                    part_path,
                    "single_log",
                    f"{item['name']}_{index}",
                    int(item["timeout"]),
                )
                parts.append(f"\n\n===== adb {' '.join(command)} =====\n")
                if part_path.exists():
                    parts.append(part_path.read_text(encoding="utf-8", errors="replace"))
            output_path.write_text("".join(parts), encoding="utf-8", errors="replace")
            assert result is not None
        else:
            result = self.adb.run(
                list(item["command"]),
                runner,
                output_path,
                "single_log",
                str(item["name"]),
                int(item["timeout"]),
            )
        text = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
        return result, output_path, analyze_log_text(text, str(item.get("analyzer", "logcat")))
