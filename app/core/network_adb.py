from __future__ import annotations

import ipaddress
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


DEFAULT_NETWORK_ADB_PORT = "5566"
MAX_SCAN_HOSTS = 1024


def _parse_ipv4(value: str, field: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} 格式不正确。") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValueError(f"{field} 只支持 IPv4 地址。")
    return address


def _parse_port(value: str) -> int:
    try:
        port = int(str(value).strip())
    except ValueError as exc:
        raise ValueError("端口必须是数字。") from exc
    if not 1 <= port <= 65535:
        raise ValueError("端口范围必须是 1~65535。")
    return port


@dataclass(frozen=True)
class NetworkRange:
    start_ip: str
    end_ip: str
    port: str = DEFAULT_NETWORK_ADB_PORT

    def __post_init__(self) -> None:
        start = _parse_ipv4(self.start_ip, "起始 IP")
        end = _parse_ipv4(self.end_ip, "结束 IP")
        if int(end) < int(start):
            raise ValueError("结束 IP 必须大于或等于起始 IP。")
        host_count = int(end) - int(start) + 1
        if host_count > MAX_SCAN_HOSTS:
            raise ValueError(f"扫描范围最多支持 {MAX_SCAN_HOSTS} 个地址，请缩小 IP 区间。")
        port = _parse_port(self.port)
        object.__setattr__(self, "start_ip", str(start))
        object.__setattr__(self, "end_ip", str(end))
        object.__setattr__(self, "port", str(port))

    def iter_addresses(self) -> Iterable[str]:
        start = int(ipaddress.IPv4Address(self.start_ip))
        end = int(ipaddress.IPv4Address(self.end_ip))
        for value in range(start, end + 1):
            yield str(ipaddress.IPv4Address(value))

    def host_count(self) -> int:
        return int(ipaddress.IPv4Address(self.end_ip)) - int(ipaddress.IPv4Address(self.start_ip)) + 1

    def label(self) -> str:
        return f"{self.start_ip} - {self.end_ip} : {self.port}"

    def to_dict(self) -> dict[str, str]:
        return {"start_ip": self.start_ip, "end_ip": self.end_ip, "port": self.port}


def validate_network_range(start_ip: str, end_ip: str, port: str) -> tuple[bool, str, NetworkRange | None]:
    try:
        return True, "", NetworkRange(start_ip, end_ip, port or DEFAULT_NETWORK_ADB_PORT)
    except ValueError as exc:
        return False, str(exc), None


def tcp_port_open(ip: str, port: str, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((ip, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        infos = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
    except OSError:
        infos = []
    for info in infos:
        ip = info[4][0]
        try:
            address = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if not address.is_loopback and not address.is_link_local:
            addresses.add(str(address))
    return sorted(addresses)


def default_range_from_local_ip(ip: str, port: str = DEFAULT_NETWORK_ADB_PORT) -> NetworkRange:
    address = _parse_ipv4(ip, "本机 IP")
    octets = str(address).split(".")
    prefix = ".".join(octets[:3])
    return NetworkRange(f"{prefix}.1", f"{prefix}.254", port)


def suggested_current_network_ranges(port: str = DEFAULT_NETWORK_ADB_PORT) -> list[NetworkRange]:
    ranges: list[NetworkRange] = []
    for ip in local_ipv4_addresses():
        try:
            ranges.append(default_range_from_local_ip(ip, port))
        except ValueError:
            continue
    return ranges


@dataclass(frozen=True)
class ScanResult:
    ip: str
    port: str
    endpoint: str
    status: str
    message: str
    port_open: bool = False
    adb_verified: bool = False
    state: str = ""
    model: str = ""
    brand: str = ""
    android: str = ""

    def as_device_record(self) -> "DeviceRecord":
        return DeviceRecord(
            serial=self.endpoint,
            status=self.status,
            connection="同一网络连接",
            endpoint=self.endpoint,
            model=self.model,
            brand=self.brand,
            android=self.android,
            message=self.message,
        )


@dataclass(frozen=True)
class DeviceRecord:
    serial: str
    status: str
    connection: str
    endpoint: str = ""
    model: str = ""
    brand: str = ""
    android: str = ""
    message: str = ""
    raw: str = ""

    def display_name(self) -> str:
        if self.model and self.brand:
            return f"{self.brand} {self.model}"
        return self.model or self.serial or "未知设备"

    def next_action(self) -> str:
        if self.status == "已可调试":
            return "可投屏、抓日志、安装 APK 或生成诊断包。"
        if self.status == "未授权":
            return "请查看设备屏幕，点击允许 USB 调试。"
        if self.status == "离线":
            return "请重新插拔数据线，或重启 ADB 服务后刷新。"
        if self.status == "发现候选设备":
            return "端口有响应，但还未确认是 Android 调试设备。"
        return self.message or "请检查连接方式后重试。"


def status_from_adb_state(state: str) -> str:
    normalized = state.strip().lower()
    if normalized == "device":
        return "已可调试"
    if normalized == "unauthorized":
        return "未授权"
    if normalized == "offline":
        return "离线"
    return "连接失败"


def adb_connection_failed(output: str, code: int | None) -> bool:
    text = output.lower()
    failure_tokens = ["unable", "failed", "cannot", "refused", "timed out", "no route", "10060", "10061"]
    return code not in (0, None) or any(token in text for token in failure_tokens)


class NetworkAdbScanner:
    def __init__(
        self,
        adb,
        port_checker: Callable[[str, str, float], bool] = tcp_port_open,
        port_timeout: float = 0.2,
        adb_timeout: int = 8,
    ):
        self.adb = adb
        self.port_checker = port_checker
        self.port_timeout = port_timeout
        self.adb_timeout = adb_timeout

    def probe_endpoint(self, ip: str, port: str, assume_port_open: bool = False) -> ScanResult:
        endpoint = f"{ip}:{port}"
        if not assume_port_open and not self.port_checker(ip, port, self.port_timeout):
            return ScanResult(
                ip=ip,
                port=port,
                endpoint=endpoint,
                status="连接失败",
                message="端口未响应：请确认设备在同一网络，并已开启同一网络调试端口。",
                port_open=False,
            )

        code, output = self.adb.quick_run(["connect", endpoint], timeout=self.adb_timeout, use_serial=False)
        if adb_connection_failed(output, code):
            return ScanResult(
                ip=ip,
                port=port,
                endpoint=endpoint,
                status="发现候选设备",
                message=f"端口已响应，但 ADB 连接失败：{output.strip() or '无返回信息'}",
                port_open=True,
                adb_verified=False,
            )

        old_serial = getattr(self.adb, "serial", None)
        try:
            if hasattr(self.adb, "set_serial"):
                self.adb.set_serial(endpoint)
            state_code, state_output = self.adb.quick_run(["get-state"], timeout=self.adb_timeout)
            state = state_output.strip()
            status = status_from_adb_state(state)
            if state_code == 0 and status == "已可调试":
                model = self._get_prop("ro.product.model")
                brand = self._get_prop("ro.product.brand")
                android = self._get_prop("ro.build.version.release")
                return ScanResult(
                    ip=ip,
                    port=port,
                    endpoint=endpoint,
                    status="已可调试",
                    message="已确认可以执行 ADB 调试命令。",
                    port_open=True,
                    adb_verified=True,
                    state=state,
                    model=model,
                    brand=brand,
                    android=android,
                )
            return ScanResult(
                ip=ip,
                port=port,
                endpoint=endpoint,
                status=status,
                message=self._state_message(status, state or output),
                port_open=True,
                adb_verified=False,
                state=state,
            )
        finally:
            if hasattr(self.adb, "set_serial"):
                self.adb.set_serial(old_serial)

    def scan_range(
        self,
        scan_range: NetworkRange,
        progress: Callable[[int, int, str], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> list[ScanResult]:
        addresses = list(scan_range.iter_addresses())
        results: list[ScanResult] = []
        open_ips: list[str] = []
        total = len(addresses)
        max_workers = min(64, max(1, total))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.port_checker, ip, scan_range.port, self.port_timeout): ip
                for ip in addresses
            }
            for index, future in enumerate(as_completed(futures), start=1):
                if should_stop and should_stop():
                    break
                ip = futures[future]
                try:
                    is_open = future.result()
                except Exception:
                    is_open = False
                if is_open:
                    open_ips.append(ip)
                if progress:
                    progress(index, total, f"正在探测 {ip}:{scan_range.port}")

        verify_total = total + len(open_ips)
        for index, ip in enumerate(open_ips, start=1):
            if should_stop and should_stop():
                break
            if progress:
                progress(total + index, verify_total, f"正在验证 {ip}:{scan_range.port}")
            result = self.probe_endpoint(ip, scan_range.port, assume_port_open=True)
            if result.port_open or result.adb_verified:
                results.append(result)
        return results

    def _get_prop(self, prop: str) -> str:
        _, output = self.adb.quick_run(["shell", "getprop", prop], timeout=self.adb_timeout)
        return output.strip()

    @staticmethod
    def _state_message(status: str, raw: str) -> str:
        if status == "未授权":
            return "设备需要授权：请查看设备屏幕并点击允许 USB 调试。"
        if status == "离线":
            return "设备离线：请重新连接设备，或重启 ADB 服务后重试。"
        return f"ADB 未确认可调试：{raw.strip() or '无返回信息'}"


class NetworkRangeStore:
    def __init__(self, path: Path, limit: int = 5):
        self.path = path
        self.limit = limit

    def load(self) -> list[NetworkRange]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        ranges: list[NetworkRange] = []
        for item in data:
            try:
                ranges.append(NetworkRange(item["start_ip"], item["end_ip"], item.get("port", DEFAULT_NETWORK_ADB_PORT)))
            except (KeyError, ValueError):
                continue
        return ranges[: self.limit]

    def save_recent(self, scan_range: NetworkRange) -> list[NetworkRange]:
        existing = [item for item in self.load() if item.label() != scan_range.label()]
        ranges = [scan_range, *existing][: self.limit]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([item.to_dict() for item in ranges], ensure_ascii=False, indent=2), encoding="utf-8")
        return ranges
