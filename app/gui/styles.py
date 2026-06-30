from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


BRAND_BLUE = "#2563eb"
ICON_DARK = "#334155"
FILLED_BUTTON_ROLES = {"primary", "success", "warning", "danger", "engineer"}
UI_FONT_FAMILIES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "SimHei",
    "SimSun",
)
UI_FONT_FILES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
)

BUTTON_STYLES = {
    "primary": "font-weight: 500; background: #2563eb; color: white; padding: 6px 12px; border: 1px solid #2563eb; border-radius: 6px;",
    "success": "font-weight: 500; background: #147a45; color: white; padding: 6px 12px; border: 1px solid #147a45; border-radius: 6px;",
    "warning": "font-weight: 500; background: #a16207; color: white; padding: 6px 12px; border: 1px solid #a16207; border-radius: 6px;",
    "danger": "font-weight: 500; background: #b3261e; color: white; padding: 6px 12px; border: 1px solid #b3261e; border-radius: 6px;",
    "secondary": "font-weight: 500; background: #ffffff; color: #1f2937; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 6px;",
    "engineer": "font-weight: 500; background: #334155; color: white; padding: 6px 12px; border: 1px solid #334155; border-radius: 6px;",
}

APP_PAGE_STYLE = "QWidget#appPage { background: #f8fafc; }"
CARD_STYLE = "QFrame#card { background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; }"
CARD_TITLE_STYLE = "font-size: 14px; font-weight: 500; color: #1f2937;"
MUTED_TEXT_STYLE = "color: #5f6b7a;"
NAV_TABS_STYLE = (
    "QTabWidget#mainTabs::pane { border-top: 1px solid #e5e7eb; background: #f8fafc; }"
    "QTabBar::tab { background: #ffffff; color: #374151; padding: 10px 22px; min-height: 24px;"
    " border: 1px solid #e5e7eb; border-left: none; border-top: none; border-bottom: 3px solid #e5e7eb; }"
    "QTabBar::tab:selected { background: #ffffff; color: #2563eb; font-weight: 500;"
    " border-bottom: 3px solid #2563eb; }"
    "QTabBar::tab:hover { background: #f8fafc; color: #2563eb; }"
)
PANEL_HINT_STYLE = "color: #475569; background: #f8fafc; padding: 9px; border: 1px solid #dde5ef; border-radius: 6px;"
STEP_BADGE_STYLE = "font-weight: 500; color: #2563eb; background: #eff6ff; padding: 9px; border: 1px solid #bfdbfe; border-radius: 6px;"
RESULT_IDLE_STYLE = "color: #5f6b7a; background: #f8fafc; padding: 9px; border: 1px solid #dde5ef; border-radius: 6px;"
RESULT_RUNNING_STYLE = "color: #9a4d00; background: #fff7e6; padding: 9px; border: 1px solid #ffd8a8; border-radius: 6px; font-weight: 500;"
RESULT_SUCCESS_STYLE = "color: #0f7a3b; background: #f0fff4; padding: 9px; border: 1px solid #b7dfc2; border-radius: 6px; font-weight: 500;"
RESULT_FAILURE_STYLE = "color: #b3261e; background: #fff5f5; padding: 9px; border: 1px solid #f0b8b8; border-radius: 6px; font-weight: 500;"
STATUS_PILL_STYLE = "font-weight: 500; color: #0f7a3b; background: #ecfdf3; padding: 6px 10px; border: 1px solid #bfe7cb; border-radius: 999px;"
SUMMARY_PILL_STYLE = "font-weight: 500; color: #1d4ed8; background: #f8fafc; padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px;"
def app_icon(name: str, color: str | None = None) -> QIcon:
    return _cached_app_icon(name.strip().lower(), color or ICON_DARK)


@lru_cache(maxsize=256)
def _cached_app_icon(name: str, color: str) -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    icon_color = QColor(color)
    pen = QPen(icon_color, 2)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QBrush(Qt.NoBrush))

    def line(x1: float, y1: float, x2: float, y2: float) -> None:
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def rect(x: float, y: float, w: float, h: float, radius: float = 3) -> None:
        painter.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    if name in {"adb", "device", "mirror"}:
        rect(6, 7, 20, 13, 2.5)
        line(14, 21, 18, 21)
        line(16, 20, 16, 25)
        line(11, 25, 21, 25)
        if name == "adb":
            line(10, 12, 22, 12)
    elif name in {"diagnosis", "scan"}:
        painter.drawEllipse(QRectF(8, 7, 13, 13))
        line(18.5, 18.5, 25, 25)
        if name == "scan":
            line(11, 13.5, 18, 13.5)
    elif name in {"file", "log"}:
        rect(9, 5, 14, 22, 2.2)
        line(18, 5, 23, 10)
        line(18, 5, 18, 10)
        line(18, 10, 23, 10)
        line(12, 15, 20, 15)
        line(12, 19, 20, 19)
    elif name in {"apk", "package"}:
        rect(7, 9, 18, 16, 2.2)
        line(7, 14, 25, 14)
        line(12, 9, 12, 6)
        line(20, 9, 20, 6)
    elif name == "install":
        rect(7, 18, 18, 7, 2)
        line(16, 6, 16, 17)
        line(11, 12, 16, 17)
        line(21, 12, 16, 17)
    elif name == "info":
        painter.drawEllipse(QRectF(7, 7, 18, 18))
        painter.setBrush(QBrush(icon_color))
        painter.drawEllipse(QRectF(15, 10, 2, 2))
        painter.setBrush(QBrush(Qt.NoBrush))
        line(16, 15, 16, 21)
    elif name == "folder":
        rect(6, 10, 20, 14, 2)
        line(6, 12, 13, 12)
        line(13, 12, 15, 9)
        line(15, 9, 23, 9)
    elif name in {"refresh", "restart"}:
        painter.drawArc(QRectF(8, 8, 16, 16), 40 * 16, 280 * 16)
        line(22, 7, 24, 14)
        line(22, 7, 15, 8)
        if name == "restart":
            line(16, 9, 16, 16)
    elif name in {"connect", "check"}:
        line(8, 16, 14, 22)
        line(14, 22, 24, 10)
    elif name in {"clear", "disconnect", "stop"}:
        line(10, 10, 22, 22)
        line(22, 10, 10, 22)
    elif name == "save":
        rect(7, 6, 18, 20, 2)
        rect(11, 18, 10, 6, 1.5)
        line(11, 6, 11, 13)
        line(21, 6, 21, 13)
    elif name == "terminal":
        rect(6, 7, 20, 18, 2)
        line(10, 13, 14, 16)
        line(10, 19, 14, 16)
        line(17, 19, 22, 19)
    elif name == "camera":
        rect(6, 10, 20, 14, 2)
        line(12, 10, 14, 7)
        line(14, 7, 19, 7)
        line(19, 7, 21, 10)
        painter.drawEllipse(QRectF(13, 13, 6, 6))
    elif name == "record":
        painter.setBrush(QBrush(icon_color))
        painter.drawEllipse(QRectF(10, 10, 12, 12))
        painter.setBrush(QBrush(Qt.NoBrush))
    elif name == "upload":
        line(16, 22, 16, 8)
        line(11, 13, 16, 8)
        line(21, 13, 16, 8)
        line(9, 24, 23, 24)
    elif name == "download":
        line(16, 8, 16, 22)
        line(11, 17, 16, 22)
        line(21, 17, 16, 22)
        line(9, 24, 23, 24)
    elif name == "list":
        line(12, 10, 24, 10)
        line(12, 16, 24, 16)
        line(12, 22, 24, 22)
        painter.setBrush(QBrush(icon_color))
        for y in (9, 15, 21):
            painter.drawEllipse(QRectF(7, y, 2, 2))
        painter.setBrush(QBrush(Qt.NoBrush))
    else:
        painter.drawEllipse(QRectF(8, 8, 16, 16))

    painter.end()
    return QIcon(pixmap)


def _icon_color_for_role(role: str) -> str:
    return "#ffffff" if role in FILLED_BUTTON_ROLES else ICON_DARK


def style_button(button: QPushButton, role: str = "secondary", tooltip: str | None = None, icon: QIcon | str | None = None) -> None:
    button.setMinimumHeight(34)
    button.setStyleSheet(BUTTON_STYLES.get(role, BUTTON_STYLES["secondary"]))
    if isinstance(icon, str):
        button.setIcon(app_icon(icon, _icon_color_for_role(role)))
        button.setProperty("appIcon", icon)
        button.setIconSize(QSize(18, 18))
    elif icon is not None and not icon.isNull():
        button.setIcon(icon)
        button.setIconSize(QSize(18, 18))
    if tooltip:
        button.setToolTip(tooltip)


def style_card(widget: QWidget) -> None:
    widget.setObjectName("card")
    widget.setStyleSheet(CARD_STYLE)


def make_step_header(text: str) -> QFrame:
    header = QFrame()
    header.setObjectName("stepHeader")
    header.setProperty("plainText", text)
    header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    header.setStyleSheet("QFrame#stepHeader { background: transparent; border: none; }")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    number, title = _split_step_text(text)
    badge = QLabel(number)
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(20, 20)
    badge.setStyleSheet("background: #2563eb; color: #ffffff; border-radius: 10px; font-weight: 500;")
    label = QLabel(title)
    label.setStyleSheet("font-size: 14px; font-weight: 500; color: #111827;")
    layout.addWidget(badge, 0, Qt.AlignVCenter)
    layout.addWidget(label, 0, Qt.AlignVCenter)
    layout.addStretch(1)
    return header


def _split_step_text(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return "1", ""
    first, _, rest = stripped.partition(" ")
    if first.isdigit():
        return first, rest or stripped
    return "1", stripped


def configure_application_font(app) -> str:
    available = set(QFontDatabase.families())
    if not available:
        for font_file in UI_FONT_FILES:
            path = Path(font_file)
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        available = set(QFontDatabase.families())
    for family in UI_FONT_FAMILIES:
        if family in available:
            _apply_smooth_font(app, QFont(family, 9))
            return family
    fallback = app.font()
    if fallback.pointSize() <= 0 or fallback.pointSize() > 9:
        fallback.setPointSize(9)
    _apply_smooth_font(app, fallback)
    return app.font().family()


def _apply_smooth_font(app, font: QFont) -> None:
    font.setStyleStrategy(QFont.PreferAntialias)
    if hasattr(font, "setHintingPreference") and hasattr(QFont, "PreferNoHinting"):
        font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setProperty("fontRendering", "antialias")
