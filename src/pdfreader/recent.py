"""In-window 'recent files' popup.

Lists the most-recently-opened PDFs; choosing one returns its path so the viewer
can reopen it. Mirrors the table-of-contents popup (see toc.py).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path


class RecentPopup:
    """Modal recent-files browser. ``choose()`` returns a file path or None."""

    def __init__(self, parent: tk.Misc, paths, scaler=None) -> None:
        # paths: list of absolute file paths, newest first.
        self.parent = parent
        self.paths = list(paths)
        self.selected_path: str | None = None
        self.scaler = scaler

        self.win = tk.Toplevel(parent)
        self.win.title("Recent Files")
        self.win.configure(bg="#2b2b2b")
        self.win.transient(parent)
        self.win.grab_set()

        tk.Label(
            self.win, text="Recent Files", bg="#2b2b2b", fg="#ffffff",
            font="DialogTitle",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        frame = tk.Frame(self.win, bg="#2b2b2b")
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        scrollbar = tk.Scrollbar(frame, orient="vertical")
        self.listbox = tk.Listbox(
            frame,
            bg="#2b2b2b",
            fg="#eeeeee",
            selectbackground="#3d6fa5",
            highlightthickness=0,
            activestyle="none",
            yscrollcommand=scrollbar.set,
            font="DialogFont",
            width=72,
            height=min(max(len(self.paths), 1), 10),
        )
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        tk.Label(
            self.win,
            text="Enter / double-click: open · Esc: close",
            bg="#2b2b2b", fg="#888888", font="DialogSmall",
        ).pack(pady=(0, 8))

        for p in self.paths:
            path = Path(p)
            self.listbox.insert(tk.END, f"{path.name}    —    {path.parent}")

        self.listbox.bind("<Double-Button-1>", lambda e: self._activate())
        self.listbox.bind("<Return>", lambda e: self._activate())
        self.win.bind("<Return>", lambda e: self._activate())
        self.win.bind("<Escape>", lambda e: self._cancel())

        if self.scaler is not None:
            for key in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_up())
            for key in ("<Control-minus>", "<Control-KP_Subtract>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_down())
            self.win.bind("<Control-Key-0>", lambda e: self.scaler.ui_scale_reset())

        self.listbox.focus_set()
        if self.listbox.size():
            self.listbox.selection_set(0)

    def _activate(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        self.selected_path = self.paths[sel[0]]
        self.win.destroy()

    def _cancel(self) -> None:
        self.win.destroy()

    def choose(self) -> str | None:
        self.parent.wait_window(self.win)
        return self.selected_path
