from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget


BUTTON_STYLES = {
    "primary": "font-weight: 700; background: #1f5fd1; color: white; padding: 7px 12px; border: 1px solid #1f5fd1; border-radius: 5px;",
    "success": "font-weight: 700; background: #177245; color: white; padding: 7px 12px; border: 1px solid #177245; border-radius: 5px;",
    "warning": "font-weight: 700; background: #9a5a00; color: white; padding: 7px 12px; border: 1px solid #9a5a00; border-radius: 5px;",
    "danger": "font-weight: 700; background: #b3261e; color: white; padding: 7px 12px; border: 1px solid #b3261e; border-radius: 5px;",
    "secondary": "font-weight: 600; background: #ffffff; color: #202124; padding: 7px 12px; border: 1px solid #c9d1dc; border-radius: 5px;",
    "engineer": "font-weight: 700; background: #374151; color: white; padding: 7px 12px; border: 1px solid #374151; border-radius: 5px;",
}

APP_PAGE_STYLE = "background: #f4f6f8;"
CARD_STYLE = "QFrame#card { background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; }"
CARD_TITLE_STYLE = "font-size: 15px; font-weight: 700; color: #1f2937;"
MUTED_TEXT_STYLE = "color: #5f6b7a;"
PANEL_HINT_STYLE = "color: #5f6b7a; background: #f8fafc; padding: 9px; border: 1px solid #dde5ef; border-radius: 6px;"
STEP_BADGE_STYLE = "font-weight: 700; color: #1d4ed8; background: #edf4ff; padding: 9px; border: 1px solid #c9dafc; border-radius: 6px;"
RESULT_IDLE_STYLE = "color: #5f6b7a; background: #f8fafc; padding: 9px; border: 1px solid #dde5ef; border-radius: 6px;"
RESULT_RUNNING_STYLE = "color: #9a4d00; background: #fff7e6; padding: 9px; border: 1px solid #ffd8a8; border-radius: 6px; font-weight: 700;"
RESULT_SUCCESS_STYLE = "color: #0f7a3b; background: #f0fff4; padding: 9px; border: 1px solid #b7dfc2; border-radius: 6px; font-weight: 700;"
RESULT_FAILURE_STYLE = "color: #b3261e; background: #fff5f5; padding: 9px; border: 1px solid #f0b8b8; border-radius: 6px; font-weight: 700;"
STATUS_PILL_STYLE = "font-weight: 700; color: #0f7a3b; background: #ecfdf3; padding: 6px 10px; border: 1px solid #bfe7cb; border-radius: 999px;"


def style_button(button: QPushButton, role: str = "secondary", tooltip: str | None = None) -> None:
    button.setMinimumHeight(34)
    button.setStyleSheet(BUTTON_STYLES.get(role, BUTTON_STYLES["secondary"]))
    if tooltip:
        button.setToolTip(tooltip)


def style_card(widget: QWidget) -> None:
    widget.setObjectName("card")
    widget.setStyleSheet(CARD_STYLE)
