"""In-window file browser for picking a PDF.

A native file dialog would route through the desktop portal, which the ChromeOS
Wayland proxy (Sommelier) mishandles — it breaks the connection. This is a plain
Tk ``Toplevel`` (X11/XWayland), the same approach the comic viewer uses, so it
is stable on a Chromebook.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

# Left margin before each entry (replaces the old icon column).
_INDENT = "   "


class FileBrowser:
    """Modal directory navigator that returns the chosen ``.pdf`` path."""

    def __init__(self, parent: tk.Misc, initial_dir: Path, scaler=None) -> None:
        self.parent = parent
        self.current_dir = initial_dir.resolve()
        self.selected_file: str | None = None
        self._entries: list[Path] = []
        # Optional object exposing ui_scale_up/down/reset so the user can resize
        # the (modal) browser's text while it is open.
        self.scaler = scaler

        self.win = tk.Toplevel(parent)
        self.win.title("Open PDF")
        self.win.configure(bg="#2b2b2b")
        # ~70% of the screen, centered over the app window (which excludes the
        # ChromeOS shelf, so it looks properly centred).
        self.win.update_idletasks()
        parent.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = int(sw * 0.7), int(sh * 0.75)
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
        except (AttributeError, tk.TclError):
            px, py, pw, ph = 0, 0, sw, sh
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.transient(parent)
        self.win.grab_set()

        self.path_label = tk.Label(
            self.win, bg="#1e1e1e", fg="#bbbbbb", anchor="w", padx=8, pady=4,
            font="DialogSmall",
        )
        self.path_label.pack(fill="x")

        frame = tk.Frame(self.win, bg="#2b2b2b")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
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
        )
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        tk.Label(
            self.win,
            text="Enter / double-click: open · Backspace: up · Esc: cancel",
            bg="#2b2b2b",
            fg="#888888",
            font="DialogSmall",
        ).pack(pady=(0, 8))

        self.listbox.bind("<Double-Button-1>", lambda e: self._activate())
        self.listbox.bind("<Return>", lambda e: self._activate())
        self.win.bind("<Return>", lambda e: self._activate())
        self.win.bind("<BackSpace>", lambda e: self._go_up())
        self.win.bind("<Escape>", lambda e: self._cancel())

        if self.scaler is not None:
            for key in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_up())
            for key in ("<Control-minus>", "<Control-KP_Subtract>"):
                self.win.bind(key, lambda e: self.scaler.ui_scale_down())
            self.win.bind("<Control-Key-0>", lambda e: self.scaler.ui_scale_reset())

        self._populate()
        self.listbox.focus_set()
        if self.listbox.size():
            self.listbox.selection_set(0)

    def _populate(self) -> None:
        self.path_label.config(text=str(self.current_dir))
        self.listbox.delete(0, tk.END)
        self._entries = []

        try:
            children = list(self.current_dir.iterdir())
        except OSError:
            children = []
        dirs = sorted(
            (p for p in children if p.is_dir()), key=lambda p: p.name.lower()
        )
        pdfs = sorted(
            (
                p
                for p in children
                if p.is_file() and p.suffix.lower() == ".pdf"
            ),
            key=lambda p: p.name.lower(),
        )

        # Left margin (no icons); folders carry a trailing slash to set them
        # apart from files.
        parent = self.current_dir.parent
        if parent != self.current_dir:
            self.listbox.insert(tk.END, f"{_INDENT}../")
            self._entries.append(parent)
        for d in dirs:
            self.listbox.insert(tk.END, f"{_INDENT}{d.name}/")
            self._entries.append(d)
        for f in pdfs:
            self.listbox.insert(tk.END, f"{_INDENT}{f.name}")
            self._entries.append(f)

    def _activate(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        target = self._entries[sel[0]]
        if target.is_dir():
            self.current_dir = target.resolve()
            self._populate()
            if self.listbox.size():
                self.listbox.selection_set(0)
        else:
            self.selected_file = str(target.resolve())
            self.win.destroy()

    def _go_up(self) -> None:
        parent = self.current_dir.parent
        if parent != self.current_dir:
            self.current_dir = parent
            self._populate()
            if self.listbox.size():
                self.listbox.selection_set(0)

    def _cancel(self) -> None:
        self.selected_file = None
        self.win.destroy()

    def choose(self) -> str | None:
        """Run modally and return the selected path, or None if cancelled."""
        self.parent.wait_window(self.win)
        return self.selected_file
