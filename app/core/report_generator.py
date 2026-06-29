from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from .utils import now_iso


class ReportGenerator:
    def generate(self, package_dir: Path, device_info: dict[str, str]) -> Path:
        status_file = package_dir / "command_status.json"
        statuses = []
        if status_file.exists():
            statuses = json.loads(status_file.read_text(encoding="utf-8"))
        counts = Counter(item.get("status", "UNKNOWN") for item in statuses)
        suggestions = self._suggestions(statuses)
        report = package_dir / "summary_report.html"
        rows = "\n".join(
            f"<tr><td>{html.escape(item.get('category', ''))}</td><td>{html.escape(item.get('name', ''))}</td>"
            f"<td>{html.escape(item.get('status', ''))}</td><td>{html.escape(item.get('error', ''))}</td></tr>"
            for item in statuses
        )
        report.write_text(
            f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Android ADB 诊断报告</title>
  <style>
    body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 24px; color: #202124; }}
    h1 {{ margin-bottom: 4px; }}
    .muted {{ color: #5f6368; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .box {{ border: 1px solid #dfe3ea; border-radius: 6px; padding: 12px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #dfe3ea; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f7fb; }}
  </style>
</head>
<body>
  <h1>Android ADB 诊断报告</h1>
  <p class="muted">生成时间：{html.escape(now_iso())}</p>
  <h2>基础信息</h2>
  <div class="grid">
    <div class="box">设备型号：{html.escape(device_info.get("model", "未知"))}</div>
    <div class="box">Android 版本：{html.escape(device_info.get("android", "未知"))}</div>
    <div class="box">SDK 版本：{html.escape(device_info.get("sdk", "未知"))}</div>
    <div class="box">序列号：{html.escape(device_info.get("serial", "未知"))}</div>
    <div class="box">连接方式：{html.escape(device_info.get("connection", "未知"))}</div>
    <div class="box">日志目录：{html.escape(str(package_dir))}</div>
  </div>
  <h2>执行结果</h2>
  <p>总命令数：{len(statuses)}，成功：{counts["SUCCESS"]}，失败：{counts["FAILED"]}，超时：{counts["TIMEOUT"]}，权限不足：{counts["PERMISSION_DENIED"]}，不支持：{counts["UNSUPPORTED"]}，不可用：{counts["NOT_AVAILABLE"]}</p>
  <h2>FAE 建议</h2>
  <ul>{''.join(f'<li>{html.escape(item)}</li>' for item in suggestions)}</ul>
  <h2>命令明细</h2>
  <table><thead><tr><th>分类</th><th>名称</th><th>状态</th><th>错误信息</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>
""",
            encoding="utf-8",
        )
        return report

    def _suggestions(self, statuses: list[dict]) -> list[str]:
        suggestions = []
        all_text = " ".join((item.get("error", "") + " " + item.get("status", "")).lower() for item in statuses)
        if "unauthorized" in all_text:
            suggestions.append("设备未授权，请在设备上点击“允许 USB 调试”。")
        if "offline" in all_text:
            suggestions.append("设备处于 offline 状态，建议重新插拔 USB 并重新开启 USB 调试。")
        if "timeout" in all_text:
            suggestions.append("存在超时命令，可能与设备响应慢、权限或连接不稳定有关。")
        if "permission" in all_text or "denied" in all_text:
            suggestions.append("存在权限不足项，这通常不影响基础日志分析，可结合 root/remount 状态判断。")
        if not suggestions:
            suggestions.append("未发现明显工具级异常，请优先查看 logcat、bugreport 与截图。")
        return suggestions
