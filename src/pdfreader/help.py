"""Canonical shortcut definitions and the help dialog.

This module is the single source of truth for keybindings: ``viewer.py`` reads
``SHORTCUTS`` to register the actual ``QShortcut`` objects, and the help dialog
renders the same list — so the documented keys can never drift from behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class Shortcut:
    """One logical action and every key sequence that triggers it.

    ``action`` is the identifier the viewer maps to a handler method.
    ``keys`` are Qt key-sequence strings (e.g. ``"Ctrl+O"``, ``"PgDown"``).
    """

    action: str
    label: str
    keys: list[str] = field(default_factory=list)


# Order here is also the order shown in the help dialog.
SHORTCUTS: list[Shortcut] = [
    Shortcut("open", "Open file", ["O", "Ctrl+O"]),
    Shortcut("goto", "Go to page", ["G", "Ctrl+G"]),
    Shortcut("next", "Next page", ["J", "Space", "PgDown"]),
    Shortcut("prev", "Previous page", ["K", "Shift+Space", "PgUp"]),
    Shortcut("first", "First page", ["Home", "Ctrl+Home"]),
    Shortcut("last", "Last page", ["End", "Ctrl+End"]),
    Shortcut("zoom_in", "Zoom in", ["+", "=", "Ctrl++"]),
    Shortcut("zoom_out", "Zoom out", ["-", "Ctrl+-"]),
    Shortcut("fit_width", "Fit to width", ["W"]),
    Shortcut("fit_height", "Fit to height", ["H"]),
    Shortcut("custom_scale", "Custom scale (enter %)", ["F"]),
    Shortcut("help", "Show this help", ["?", "F1"]),
    Shortcut("quit", "Quit", ["Q", "Ctrl+Q"]),
]


def _format_keys(keys: list[str]) -> str:
    return "  /  ".join(keys)


class HelpDialog(QDialog):
    """A simple scrollable list of all shortcuts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(420, 480)

        rows = ["<table cellspacing='8'>"]
        rows.append(
            "<tr><th align='left'>Keys</th><th align='left'>Action</th></tr>"
        )
        for sc in SHORTCUTS:
            rows.append(
                f"<tr><td><b>{_format_keys(sc.keys)}</b></td>"
                f"<td>{sc.label}</td></tr>"
            )
        rows.append("</table>")
        rows.append(
            "<p style='color:gray'>Arrow keys pan the page when zoomed past "
            "the window.</p>"
        )

        body = QLabel("".join(rows))
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setMargin(12)

        scroll = QScrollArea()
        scroll.setWidget(body)
        scroll.setWidgetResizable(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(buttons)
