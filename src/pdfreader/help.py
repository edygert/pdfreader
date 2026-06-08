"""Canonical shortcut definitions and the help window."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Shortcut:
    label: str
    keys: list[str] = field(default_factory=list)


# Single source of truth: the viewer binds these and the help window lists them.
SHORTCUTS: list[Shortcut] = [
    Shortcut("Open file", ["o"]),
    Shortcut("Go to page", [":"]),
    Shortcut("Next page", ["Ctrl f", "Ctrl →", "Space", "PageDown"]),
    Shortcut("Previous page", ["Ctrl b", "Ctrl ←", "PageUp"]),
    Shortcut("First page", ["gg", "Home"]),
    Shortcut("Last page", ["G", "End"]),
    Shortcut("Zoom in", ["+", "="]),
    Shortcut("Zoom out", ["-"]),
    Shortcut("Fit to width", ["Shift W"]),
    Shortcut("Fit to height", ["Shift H"]),
    Shortcut("Custom scale (enter %)", ["f"]),
    Shortcut("Rotate clockwise / counter", ["r", "Shift R"]),
    Shortcut("Page color: white / off-white / dark", ["t"]),
    Shortcut("UI text bigger / smaller / reset", ["Ctrl +", "Ctrl -", "Ctrl 0"]),
    Shortcut("Pan (when zoomed)", ["h j k l", "← → ↑ ↓"]),
    Shortcut("Show this help", ["?", "F1"]),
    Shortcut("Quit", ["q"]),
]

# Abbreviated one-line cheat sheet shown along the bottom of the window.
CHEATS = (
    "o open · : goto · Ctrl-f/b page · hjkl pan · "
    "W/H fit · f scale · +/- zoom · r/R rotate · ? help · q quit"
)


def show_help(parent: tk.Misc) -> None:
    """Open a simple modal window listing every shortcut."""
    win = tk.Toplevel(parent)
    win.title("Keyboard Shortcuts")
    win.configure(bg="#2b2b2b")
    win.transient(parent)
    # No fixed geometry: let Tk size the window to fit the title, every row, and
    # the Close button, so nothing is clipped at any font scale.

    tk.Label(
        win,
        text="Keyboard Shortcuts",
        bg="#2b2b2b",
        fg="#ffffff",
        font="DialogTitle",
    ).pack(anchor="w", padx=16, pady=(14, 8))

    grid = tk.Frame(win, bg="#2b2b2b")
    grid.pack(fill="both", expand=True, padx=16)
    for row, sc in enumerate(SHORTCUTS):
        tk.Label(
            grid,
            text="   /   ".join(sc.keys),
            bg="#2b2b2b",
            fg="#7fd1ff",
            font="DialogMono",
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=2, padx=(0, 16))
        tk.Label(
            grid, text=sc.label, bg="#2b2b2b", fg="#dddddd", anchor="w",
            font="DialogFont",
        ).grid(row=row, column=1, sticky="w", pady=2)

    tk.Button(win, text="Close", command=win.destroy).pack(pady=12)

    win.bind("<Escape>", lambda e: win.destroy())
    win.bind("<Key-question>", lambda e: win.destroy())
    win.focus_set()
