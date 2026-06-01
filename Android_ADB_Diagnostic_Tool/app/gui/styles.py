from __future__ import annotations

from PySide6.QtWidgets import QPushButton


BUTTON_STYLES = {
    "primary": "font-weight: 700; background: #1a73e8; color: white; padding: 7px 10px;",
    "success": "font-weight: 700; background: #137333; color: white; padding: 7px 10px;",
    "warning": "font-weight: 700; background: #b06000; color: white; padding: 7px 10px;",
    "danger": "font-weight: 700; background: #b3261e; color: white; padding: 7px 10px;",
    "secondary": "font-weight: 600; background: #f8fafc; color: #202124; padding: 7px 10px; border: 1px solid #d0d7de;",
    "engineer": "font-weight: 700; background: #3c4043; color: white; padding: 7px 10px;",
}


def style_button(button: QPushButton, role: str = "secondary", tooltip: str | None = None) -> None:
    button.setMinimumHeight(34)
    button.setStyleSheet(BUTTON_STYLES.get(role, BUTTON_STYLES["secondary"]))
    if tooltip:
        button.setToolTip(tooltip)
