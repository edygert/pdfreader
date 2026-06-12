"""In-window table-of-contents (outline) popup.

Shows the PDF's bookmarks as an indented, keyboard-navigable list; choosing an
entry returns its 0-based page index so the viewer can jump there.
"""

from __future__ import annotations

import tkinter as tk

_INDENT = "   "  # per nesting level


class TocPopup:
    """Modal outline browser. ``choose()`` returns a page index or None."""

    def __init__(self, parent: tk.Misc, items, scaler=None) -> None:
        # items: list of (level, title, page_index)
        self.parent = parent
        self.items = items
        self.selected_page: int | None = None
        self.scaler = scaler

        self.win = tk.Toplevel(parent)
        self.win.title("Table of Contents")
        self.win.configure(bg="#2b2b2b")
        self.win.transient(parent)
        self.win.grab_set()

        tk.Label(
            self.win, text="Table of Contents", bg="#2b2b2b", fg="#ffffff",
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
            width=56,
            height=24,
        )
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        tk.Label(
            self.win,
            text="Enter / double-click: go to page · Esc: close",
            bg="#2b2b2b", fg="#888888", font="DialogSmall",
        ).pack(pady=(0, 8))

        for level, title, page in self.items:
            num = f"   ({page + 1})" if page is not None else ""
            self.listbox.insert(tk.END, f"{_INDENT * level}{title}{num}")

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
        page = self.items[sel[0]][2]
        if page is None:
            return  # entry without a destination: keep the popup open
        self.selected_page = page
        self.win.destroy()

    def _cancel(self) -> None:
        self.win.destroy()

    def choose(self) -> int | None:
        self.parent.wait_window(self.win)
        return self.selected_page
