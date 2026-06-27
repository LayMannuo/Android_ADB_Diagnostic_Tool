from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .adb_manager import AdbManager
from .network_adb import DeviceRecord
from .utils import ensure_dir, hidden_subprocess_kwargs, resource_base_dir, safe_text, sanitize_filename, timestamp


@dataclass(frozen=True)
class ApkInfo:
    original_path: Path
    install_path: Path
    display_name: str
    package_name: str
    version_name: str
    version_code: str
    size_bytes: int
    md5: str
    normalized: bool
    icon_path: Path | None
    parse_status: str
    parse_message: str


@dataclass(frozen=True)
class ApkInstallOptions:
    replace: bool = True
    downgrade: bool = False
    grant_permissions: bool = False

    def build_args(self, apk_path: Path) -> list[str]:
        args = ["install"]
        if self.replace:
            args.append("-r")
        if self.downgrade:
            args.append("-d")
        if self.grant_permissions:
            args.append("-g")
        args.append(str(apk_path))
        return args


@dataclass(frozen=True)
class ApkInstallResult:
    success: bool
    status: str
    message: str
    solution: str
    output: str


@dataclass(frozen=True)
class BatchApkInstallRecord:
    index: int
    apk_info: ApkInfo
    result: ApkInstallResult


@dataclass(frozen=True)
class BatchApkInstallSummary:
    total: int
    results: list[BatchApkInstallRecord]

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.results if item.result.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.results if not item.result.success)


@dataclass(frozen=True)
class TargetDeviceInstallRecord:
    index: int
    target: DeviceRecord
    apk_info: ApkInfo
    result: ApkInstallResult


@dataclass(frozen=True)
class TargetDeviceInstallSummary:
    total: int
    results: list[TargetDeviceInstallRecord]

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.results if item.result.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.results if not item.result.success)


@dataclass(frozen=True)
class ApkInstallPlanRecord:
    index: int
    apk_info: ApkInfo
    target: DeviceRecord
    result: ApkInstallResult


@dataclass(frozen=True)
class ApkInstallPlanSummary:
    total: int
    results: list[ApkInstallPlanRecord]

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.results if item.result.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.results if not item.result.success)


def normalize_apk_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    lower = name.lower()
    index = lower.find(".apk")
    if index >= 0:
        name = name[: index + 4]
    elif not lower.endswith(".apk"):
        stem = Path(name).stem or "install"
        name = f"{stem}.apk"
    return name


def has_abnormal_apk_filename(filename: str) -> bool:
    name = Path(filename).name.strip()
    lower = name.lower()
    index = lower.find(".apk")
    return index < 0 or lower[index + 4 :] != ""


def parse_apk_file(source_path: Path, temp_root: Path) -> ApkInfo:
    source_path = source_path.resolve()
    temp_root = ensure_dir(temp_root / timestamp())
    normalized_name = normalize_apk_filename(source_path.name)
    safe_name = sanitize_filename(Path(normalized_name).stem, "install") + ".apk"
    install_path = temp_root / safe_name
    shutil.copy2(source_path, install_path)
    size_bytes = source_path.stat().st_size
    md5 = _md5(source_path)
    metadata = _parse_with_apkutils(install_path, temp_root)
    if metadata.get("parse_status") != "SUCCESS":
        aapt_metadata = _parse_with_aapt(install_path, temp_root)
        if aapt_metadata.get("parse_status") == "SUCCESS":
            metadata = aapt_metadata
    normalized = has_abnormal_apk_filename(source_path.name)
    return ApkInfo(
        original_path=source_path,
        install_path=install_path,
        display_name=metadata.get("display_name", ""),
        package_name=metadata.get("package_name", ""),
        version_name=metadata.get("version_name", ""),
        version_code=metadata.get("version_code", ""),
        size_bytes=size_bytes,
        md5=md5,
        normalized=normalized,
        icon_path=metadata.get("icon_path"),
        parse_status=metadata.get("parse_status", "PARTIAL"),
        parse_message=metadata.get("parse_message", "未找到 aapt/aapt2，已完成大小和 MD5 解析，可继续安装。"),
    )


def classify_install_failure(output: str) -> tuple[str, str]:
    text = output or ""
    lower = text.lower()
    if "success" in lower:
        return "安装成功：应用已安装到设备。", "无需处理。"
    if "install_failed_version_downgrade" in lower:
        return "安装失败：APK 版本低于设备已安装版本。", "解决：勾选“允许降级”后重试，或先卸载设备上的高版本应用。"
    if "install_failed_update_incompatible" in lower:
        return "安装失败：签名不一致，无法覆盖旧应用。", "解决：先卸载旧版本应用，再重新安装；注意卸载可能清除应用数据。"
    if "install_failed_already_exists" in lower:
        return "安装失败：应用已存在。", "解决：勾选“覆盖安装”后重试，或先卸载旧应用。"
    if "install_parse_failed" in lower or "parse" in lower and "failed" in lower:
        return "安装失败：APK 解析失败，文件可能损坏或不是有效 APK。", "解决：重新获取 APK，确认文件完整后再安装。"
    if "no certificates" in lower or "certificates" in lower:
        return "安装失败：APK 签名异常。", "解决：请确认 APK 已正确签名，或让研发重新打包签名版本。"
    if "insufficient_storage" in lower or "not enough space" in lower:
        return "安装失败：设备存储空间不足。", "解决：清理设备存储空间后重试。"
    if "unauthorized" in lower:
        return "安装失败：设备未授权。", "解决：请在设备弹窗中点击“允许 USB 调试”，然后重新检测设备。"
    if "offline" in lower:
        return "安装失败：设备处于 offline 状态。", "解决：重新插拔 USB，关闭再打开 USB 调试，必要时重启 ADB 服务。"
    if "device" in lower and "not found" in lower or "no devices" in lower:
        return "安装失败：未检测到设备。", "解决：连接设备、开启 USB 调试并点击“检测设备”后重试。"
    return "安装失败：adb install 执行失败。", "解决：确认设备连接、USB 调试授权、APK 文件完整，并查看下方 ADB 输出。"


class ApkInstaller:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = output_root

    def install(self, apk_info: ApkInfo, options: ApkInstallOptions, cleanup_on_success: bool = True) -> ApkInstallResult:
        code, output = self.adb.quick_run(options.build_args(apk_info.install_path), timeout=300)
        success = code == 0 and "success" in output.lower()
        message, solution = classify_install_failure(output)
        if success and not apk_info.package_name:
            return ApkInstallResult(
                False,
                "FAILED",
                "安装结果未确认：APK 未解析到包名，无法执行安装后 pm path 校验。",
                "解决：请确认 APK 元信息可解析，或让研发提供标准 APK；工具已保留临时安装文件，可重新选择后再试。",
                output,
            )
        if success and apk_info.package_name:
            _, verify_output = self.adb.quick_run(["shell", "pm", "path", apk_info.package_name], timeout=20)
            if "package:" not in verify_output:
                return ApkInstallResult(
                    False,
                    "FAILED",
                    "安装结果未确认：adb install 返回成功，但设备中未查询到该包名。",
                    "解决：确认 APK 包名是否正确、设备是否有多用户/安装策略限制；可重试安装或查看下方 ADB 输出。",
                    output + "\n\n安装后校验输出：\n" + verify_output,
                )
        status = "SUCCESS" if success else "FAILED"
        if success and cleanup_on_success:
            _safe_delete(apk_info.install_path)
        return ApkInstallResult(success, status, message, solution, output)


class BatchApkInstallQueue:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = output_root

    def install_all(
        self,
        apk_infos: list[ApkInfo],
        options: ApkInstallOptions,
        stop_on_failure: bool = False,
        progress: Callable[[int, int, ApkInfo, ApkInstallResult], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> BatchApkInstallSummary:
        installer = ApkInstaller(self.adb, self.output_root)
        results: list[BatchApkInstallRecord] = []
        total = len(apk_infos)
        for index, apk_info in enumerate(apk_infos, start=1):
            if should_stop and should_stop():
                break
            result = installer.install(apk_info, options)
            results.append(BatchApkInstallRecord(index=index, apk_info=apk_info, result=result))
            if progress:
                progress(index, total, apk_info, result)
            if stop_on_failure and not result.success:
                break
        return BatchApkInstallSummary(total=total, results=results)


class TargetDeviceApkInstallQueue:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = output_root

    def install_to_targets(
        self,
        apk_info: ApkInfo,
        targets: list[DeviceRecord],
        options: ApkInstallOptions,
        stop_on_failure: bool = False,
        progress: Callable[[int, int, DeviceRecord, ApkInstallResult], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> TargetDeviceInstallSummary:
        installer = ApkInstaller(self.adb, self.output_root)
        original_serial = getattr(self.adb, "serial", None)
        results: list[TargetDeviceInstallRecord] = []
        total = len(targets)
        try:
            for index, target in enumerate(targets, start=1):
                if should_stop and should_stop():
                    break
                self.adb.set_serial(target.serial)
                result = installer.install(apk_info, options, cleanup_on_success=False)
                results.append(TargetDeviceInstallRecord(index=index, target=target, apk_info=apk_info, result=result))
                if progress:
                    progress(index, total, target, result)
                if stop_on_failure and not result.success:
                    break
        finally:
            self.adb.set_serial(original_serial)
        if results and len(results) == total and all(record.result.success for record in results):
            _safe_delete(apk_info.install_path)
        return TargetDeviceInstallSummary(total=total, results=results)


class ApkInstallPlanQueue:
    def __init__(self, adb: AdbManager, output_root: Path):
        self.adb = adb
        self.output_root = output_root

    def install_all(
        self,
        apk_infos: list[ApkInfo],
        targets: list[DeviceRecord],
        options: ApkInstallOptions,
        stop_on_failure: bool = False,
        progress: Callable[[int, int, ApkInfo, DeviceRecord, ApkInstallResult], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> ApkInstallPlanSummary:
        installer = ApkInstaller(self.adb, self.output_root)
        original_serial = getattr(self.adb, "serial", None)
        total = len(apk_infos) * len(targets)
        results: list[ApkInstallPlanRecord] = []
        try:
            for apk_info in apk_infos:
                for target in targets:
                    if should_stop and should_stop():
                        return ApkInstallPlanSummary(total=total, results=results)
                    self.adb.set_serial(target.serial)
                    result = installer.install(apk_info, options, cleanup_on_success=False)
                    record = ApkInstallPlanRecord(index=len(results) + 1, apk_info=apk_info, target=target, result=result)
                    results.append(record)
                    if progress:
                        progress(record.index, total, apk_info, target, result)
                    if stop_on_failure and not result.success:
                        return ApkInstallPlanSummary(total=total, results=results)
        finally:
            self.adb.set_serial(original_serial)
        for apk_info in apk_infos:
            apk_results = [record for record in results if record.apk_info == apk_info]
            if len(apk_results) == len(targets) and all(record.result.success for record in apk_results):
                _safe_delete(apk_info.install_path)
        return ApkInstallPlanSummary(total=total, results=results)


def find_aapt() -> Path | None:
    candidates = [
        resource_base_dir() / "tools" / "aapt" / "aapt.exe",
        resource_base_dir() / "tools" / "aapt" / "aapt2.exe",
        resource_base_dir() / "tools" / "android" / "aapt.exe",
        resource_base_dir() / "tools" / "android" / "aapt2.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    system = shutil.which("aapt") or shutil.which("aapt2")
    return Path(system) if system else None


def _parse_with_apkutils(apk_path: Path, temp_root: Path) -> dict[str, object]:
    try:
        import apkutils2
    except Exception:
        return {"parse_status": "PARTIAL", "parse_message": "未安装 apkutils2，已完成大小和 MD5 解析，可继续安装。"}
    try:
        apk = apkutils2.APK(str(apk_path))
        manifest = apk.get_manifest() or {}
        app = manifest.get("application") or {}
        if isinstance(app, list):
            app = app[0] if app else {}
        display_name = str(app.get("@android:label") or "").strip()
        display_name = _resolve_apkutils_label(apk, display_name)
        icon_path = None
        icon_error = ""
        try:
            icon_path = _extract_icon(apk_path, apk.get_app_icon(), temp_root)
        except Exception:
            icon_error = " 未解析到图标，不影响安装。"
        parse_message = "APK 信息解析完成。" + icon_error
        if not display_name:
            display_name = _fallback_display_name(manifest.get("@package", ""))
        return {
            "parse_status": "SUCCESS",
            "parse_message": parse_message,
            "package_name": str(manifest.get("@package") or ""),
            "version_code": str(manifest.get("@android:versionCode") or ""),
            "version_name": str(manifest.get("@android:versionName") or ""),
            "display_name": display_name,
            "icon_path": icon_path,
        }
    except Exception as exc:
        return {"parse_status": "PARTIAL", "parse_message": f"APK 深度解析失败：{exc}。已完成大小和 MD5 解析，可继续安装。"}


def _resolve_apkutils_label(apk, label: str) -> str:
    if not label:
        return ""
    if not label.startswith("@"):
        return label
    resource_id = label[1:]
    try:
        rid = int(resource_id, 16)
    except ValueError:
        return ""
    try:
        resources = apk.get_arsc()
        values = resources.get_resolved_res_configs(rid) if resources else []
    except Exception:
        return ""
    for _, value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _fallback_display_name(package_name: object) -> str:
    text = str(package_name or "").strip()
    if not text:
        return ""
    return text.rsplit(".", 1)[-1] or text


def _parse_with_aapt(apk_path: Path, temp_root: Path) -> dict[str, object]:
    aapt = find_aapt()
    if not aapt:
        return {}
    try:
        completed = subprocess.run(
            [str(aapt), "dump", "badging", str(apk_path)],
            capture_output=True,
            timeout=30,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {"parse_status": "PARTIAL", "parse_message": f"aapt 解析异常：{exc}。仍可继续安装。"}
    output = safe_text(completed.stdout) + safe_text(completed.stderr)
    if completed.returncode != 0:
        return {"parse_status": "PARTIAL", "parse_message": f"aapt 解析失败。仍可继续安装。\n{output.strip()}"}
    metadata: dict[str, object] = {
        "parse_status": "SUCCESS",
        "parse_message": "APK 信息解析完成。",
        "package_name": _match(output, r"package: name='([^']*)'"),
        "version_code": _match(output, r"versionCode='([^']*)'"),
        "version_name": _match(output, r"versionName='([^']*)'"),
        "display_name": _match(output, r"application-label:'([^']*)'"),
    }
    icon_inside_apk = _best_icon_path(output)
    if icon_inside_apk:
        metadata["icon_path"] = _extract_icon(apk_path, icon_inside_apk, temp_root)
    return metadata


def _match(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _best_icon_path(aapt_output: str) -> str:
    icons = re.findall(r"application-icon(?:-\d+)?:'([^']+)'", aapt_output)
    if not icons:
        return ""
    png_icons = [icon for icon in icons if icon.lower().endswith(".png")]
    return (png_icons or icons)[-1]


def _extract_icon(apk_path: Path, inside_path: str, temp_root: Path) -> Path | None:
    try:
        with zipfile.ZipFile(apk_path) as archive:
            data = archive.read(inside_path)
    except Exception:
        return None
    suffix = Path(inside_path).suffix or ".png"
    icon_path = ensure_dir(temp_root / "icons") / f"apk_icon_{timestamp()}{suffix}"
    icon_path.write_bytes(data)
    return icon_path


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
