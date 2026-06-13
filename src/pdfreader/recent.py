"""In-window 'recent files' popup.

Lists the most-recently-opened PDFs as filename rows — name on the left, file
size on the right — mirroring the PWA's recent-files card. Choosing one returns
its path so the viewer can reopen it.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

# Colours mirror the web popup (.toc-card / .recent-row in styles.css).
_BG = "#2b2b2b"
_SEL_BG = "#3d6fa5"
_HOVER_BG = "#37414e"
_NAME_FG = "#dddddd"
_NAME_SEL_FG = "#ffffff"
_META_FG = "#88aabb"
_META_SEL_FG = "#cceeff"


def _fmt_size(num_bytes: int) -> str:
    """Human-readable file size, matching the PWA's fmtSize()."""
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, round(num_bytes / 1024))} KB"


class RecentPopup:
    """Modal recent-files browser. ``choose()`` returns a file path or None."""

    def __init__(self, parent: tk.Misc, paths, scaler=None) -> None:
        # paths: list of absolute file paths, newest first.
        self.parent = parent
        self.paths = list(paths)
        self.selected_path: str | None = None
        self.scaler = scaler
        self.sel = 0
        self._rows: list[tuple[tk.Label, tk.Label]] = []  # (name, meta) per file

        self.win = tk.Toplevel(parent)
        self.win.title("Recent Files")
        self.win.configure(bg=_BG)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.minsize(520, 0)  # width like the PWA card; height fits content

        tk.Label(
            self.win, text="Recent Files", bg=_BG, fg="#ffffff",
            font="DialogTitle",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # One grid row per file: name expands (column 0), size sits at the right
        # (column 1). No scrollbar — the window grows to show all ten.
        rows = tk.Frame(self.win, bg=_BG)
        rows.pack(fill="both", expand=True, padx=8)
        rows.columnconfigure(0, weight=1)

        for i, p in enumerate(self.paths):
            path = Path(p)
            try:
                meta = _fmt_size(path.stat().st_size)
            except OSError:
                meta = ""
            name = tk.Label(
                rows, text=path.name, bg=_BG, fg=_NAME_FG, anchor="w",
                font="DialogFont", padx=8, pady=4,
            )
            size = tk.Label(
                rows, text=meta, bg=_BG, fg=_META_FG, anchor="e",
                font="DialogFont", padx=8, pady=4,
            )
            name.grid(row=i, column=0, sticky="ew")
            size.grid(row=i, column=1, sticky="e")
            self._rows.append((name, size))
            for w in (name, size):
                w.bind("<Button-1>", lambda e, idx=i: self._activate(idx))
                w.bind("<Enter>", lambda e, idx=i: self._hover(idx, True))
                w.bind("<Leave>", lambda e, idx=i: self._hover(idx, False))

        tk.Label(
            self.win,
            text="↑/↓ or j/k · Enter / click: open · Esc: close",
            bg=_BG, fg="#888888", font="DialogSmall",
        ).pack(pady=(8, 10))

        self.win.bind("<Up>", lambda e: self._move(-1))
        self.win.bind("<Down>", lambda e: self._move(1))
        self.win.bind("k", lambda e: self._move(-1))
        self.win.bind("j", lambda e: self._move(1))
        self.win.bind("<Home>", lambda e: self._select(0))
        self.win.bind("<End>", lambda e: self._select(len(self.paths) - 1))
        self.win.bind("<Return>", lambda e: self._activate(self.sel))
        self.win.bind("<Escape>", lambda e: self._cancel())

        if self.scaler is not None:
            for key in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_up())
            for key in ("<Control-minus>", "<Control-KP_Subtract>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_down())
            self.win.bind("<Control-Key-0>", lambda e: self.scaler.ui_scale_reset())

        self.win.focus_set()
        self._paint()

    # ----- row appearance ---------------------------------------------
    def _colors(self, idx: int, hovering: bool) -> tuple[str, str, str]:
        if idx == self.sel:
            return _SEL_BG, _NAME_SEL_FG, _META_SEL_FG
        if hovering:
            return _HOVER_BG, _NAME_FG, _META_FG
        return _BG, _NAME_FG, _META_FG

    def _apply(self, idx: int, hovering: bool = False) -> None:
        bg, nfg, mfg = self._colors(idx, hovering)
        name, size = self._rows[idx]
        name.config(bg=bg, fg=nfg)
        size.config(bg=bg, fg=mfg)

    def _paint(self) -> None:
        for i in range(len(self._rows)):
            self._apply(i)

    def _hover(self, idx: int, entering: bool) -> None:
        if idx != self.sel:
            self._apply(idx, hovering=entering)

    # ----- selection / activation -------------------------------------
    def _move(self, delta: int) -> None:
        if self._rows:
            self._select(self.sel + delta)

    def _select(self, idx: int) -> None:
        idx = min(max(idx, 0), len(self._rows) - 1)
        old, self.sel = self.sel, idx
        self._apply(old)
        self._apply(idx)

    def _activate(self, idx: int) -> None:
        if 0 <= idx < len(self.paths):
            self.selected_path = self.paths[idx]
            self.win.destroy()

    def _cancel(self) -> None:
        self.win.destroy()

    def choose(self) -> str | None:
        self.parent.wait_window(self.win)
        return self.selected_path
