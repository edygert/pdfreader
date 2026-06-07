"""Main window: page display, scaling, navigation and keybindings (Tkinter)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from PIL import ImageTk

from . import fonts
from . import state as state_mod
from .browser import FileBrowser
from .document import Document
from .help import CHEATS, show_help
from .state import CUSTOM, FIT_HEIGHT, FIT_WIDTH, FileState, State

_MARGIN = 4  # px shaved off the viewport so fit modes avoid a stray scrollbar
_PAN_STEP = 60  # px moved per arrow-key pan


class Viewer:
    def __init__(self, root: tk.Tk, state: State) -> None:
        self.root = root
        self.state = state
        self.doc: Document | None = None
        self.page = 0
        # Per-file reading position; replaced on open_path with the file's own.
        self.fstate: FileState = FileState()
        self._photo: ImageTk.PhotoImage | None = None
        self._last_canvas_size = (0, 0)
        self._resize_job: str | None = None
        # Currently applied UI text scale (per-file; restored on open_path).
        self.ui_scale = 1.0

        root.title("pdfreader")
        root.geometry("900x1100")
        root.configure(bg="#1e1e1e")

        self.canvas = tk.Canvas(root, bg="#3a3a3a", highlightthickness=0)
        self.vbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.hbar = tk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(
            yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set
        )
        self.status = tk.Label(
            root, bg="#1e1e1e", fg="#cccccc", anchor="w", padx=8, pady=3,
            font="UiFont",
        )

        self.status.pack(side="bottom", fill="x")
        self.hbar.pack(side="bottom", fill="x")
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill="#dddddd",
            text="Press  o  to open a PDF   ·   ?  for help",
            font="UiTitle",
        )
        self._set_status(f"No document open        {CHEATS}")

        self._bind_keys()
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    # ----- key bindings ------------------------------------------------
    def _bind_keys(self) -> None:
        r = self.root
        r.bind("o", lambda e: self.open_dialog())
        r.bind("g", lambda e: self.goto_dialog())

        for key in ("<space>", "<Next>", "j"):
            r.bind(key, lambda e: self.next_page())
        for key in ("<Prior>", "k"):
            r.bind(key, lambda e: self.prev_page())
        r.bind("<Home>", lambda e: self.first_page())
        r.bind("<End>", lambda e: self.last_page())

        for key in ("<plus>", "<equal>", "<KP_Add>"):
            r.bind(key, lambda e: self.zoom_in())
        for key in ("<minus>", "<KP_Subtract>"):
            r.bind(key, lambda e: self.zoom_out())
        r.bind("w", lambda e: self.fit_width())
        r.bind("h", lambda e: self.fit_height())
        r.bind("f", lambda e: self.custom_scale_dialog())

        # Left/Right flip pages; Up/Down pan the page vertically (canvas scroll).
        r.bind("<Right>", lambda e: self.next_page())
        r.bind("<Left>", lambda e: self.prev_page())
        r.bind("<Up>", lambda e: self.canvas.yview_scroll(-1, "units"))
        r.bind("<Down>", lambda e: self.canvas.yview_scroll(1, "units"))
        # Mouse wheel vertical scroll (Linux sends Button-4/5).
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"),
        )

        # UI text scaling (chrome only, separate from page zoom +/-/=).
        for key in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            r.bind(key, lambda e: self.ui_scale_up())
        for key in ("<Control-minus>", "<Control-KP_Subtract>"):
            r.bind(key, lambda e: self.ui_scale_down())
        r.bind("<Control-Key-0>", lambda e: self.ui_scale_reset())

        r.bind("?", lambda e: show_help(self.root))
        r.bind("<F1>", lambda e: show_help(self.root))
        r.bind("q", lambda e: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ----- document lifecycle -----------------------------------------
    def open_path(self, path: str) -> bool:
        try:
            doc = Document(path)
        except Exception as exc:  # noqa: BLE001 - surface any load failure
            messagebox.showerror("Cannot open PDF", f"{path}\n\n{exc}")
            return False

        # Resolve to absolute so the same file keys the same saved record.
        path = str(Path(path).resolve())
        if self.doc is not None:
            self.doc.close()
        self.doc = doc
        self.state.last_file = path
        self.fstate = self.state.for_file(path)
        # Restore this file's saved UI text size.
        self.ui_scale = fonts.apply_scale(self.fstate.ui_scale)
        self.root.title(f"{Path(path).name} — pdfreader")

        count = self.doc.page_count
        self.page = min(max(self.fstate.page, 0), max(count - 1, 0))
        self._render_current()
        self._save()
        return True

    # ----- navigation --------------------------------------------------
    def _goto(self, index: int) -> None:
        if not self.doc:
            return
        index = min(max(index, 0), self.doc.page_count - 1)
        if index != self.page:
            self.page = index
            self._render_current()
            self._save()
        self.canvas.yview_moveto(0.0)
        self.canvas.xview_moveto(0.0)

    def next_page(self) -> None:
        self._goto(self.page + 1)

    def prev_page(self) -> None:
        self._goto(self.page - 1)

    def first_page(self) -> None:
        self._goto(0)

    def last_page(self) -> None:
        if self.doc:
            self._goto(self.doc.page_count - 1)

    def goto_dialog(self) -> None:
        if not self.doc:
            return
        page = simpledialog.askinteger(
            "Go to page",
            f"Page (1–{self.doc.page_count}):",
            parent=self.root,
            initialvalue=self.page + 1,
            minvalue=1,
            maxvalue=self.doc.page_count,
        )
        if page is not None:
            self._goto(page - 1)

    # ----- scaling -----------------------------------------------------
    def _viewport(self) -> tuple[int, int]:
        return self.canvas.winfo_width(), self.canvas.winfo_height()

    def _effective_scale(self) -> float:
        assert self.doc is not None
        w_pt, h_pt = self.doc.page_size(self.page)
        vw, vh = self._viewport()
        if self.fstate.scale_mode == FIT_WIDTH:
            return max(0.05, (vw - _MARGIN) / w_pt)
        if self.fstate.scale_mode == FIT_HEIGHT:
            return max(0.05, (vh - _MARGIN) / h_pt)
        return self.fstate.custom_factor

    def _current_factor(self) -> float:
        if self.fstate.scale_mode == CUSTOM:
            return self.fstate.custom_factor
        return self._effective_scale()

    def _set_custom(self, factor: float) -> None:
        self.fstate.scale_mode = CUSTOM
        self.fstate.custom_factor = max(0.05, min(factor, 12.0))
        self._render_current()
        self._save()

    def zoom_in(self) -> None:
        if self.doc:
            self._set_custom(self._current_factor() * 1.25)

    def zoom_out(self) -> None:
        if self.doc:
            self._set_custom(self._current_factor() * 0.8)

    def fit_width(self) -> None:
        if self.doc:
            self.fstate.scale_mode = FIT_WIDTH
            self._render_current()
            self._save()

    def fit_height(self) -> None:
        if self.doc:
            self.fstate.scale_mode = FIT_HEIGHT
            self._render_current()
            self._save()

    def custom_scale_dialog(self) -> None:
        if not self.doc:
            return
        percent = simpledialog.askfloat(
            "Custom scale",
            "Scale (%):",
            parent=self.root,
            initialvalue=round(self._current_factor() * 100, 1),
            minvalue=5.0,
            maxvalue=1200.0,
        )
        if percent is not None:
            self._set_custom(percent / 100.0)

    # ----- rendering ---------------------------------------------------
    def _render_current(self) -> None:
        if not self.doc:
            return
        scale = self._effective_scale()
        image = self.doc.render(self.page, scale)
        self._photo = ImageTk.PhotoImage(image)

        self.canvas.delete("all")
        vw, _ = self._viewport()
        # Centre horizontally when the page is narrower than the viewport.
        x = max(vw, image.width) // 2
        self.canvas.create_image(x, 0, anchor="n", image=self._photo)
        self.canvas.configure(
            scrollregion=(0, 0, max(vw, image.width), image.height)
        )
        self._update_status()

    def _update_status(self) -> None:
        if not self.doc:
            self._set_status(f"No document open        {CHEATS}")
            return
        percent = round(self._effective_scale() * 100)
        mode = self.fstate.scale_mode
        if mode == FIT_WIDTH:
            scale_text = f"Fit width ({percent}%)"
        elif mode == FIT_HEIGHT:
            scale_text = f"Fit height ({percent}%)"
        else:
            scale_text = f"{percent}%"
        self._set_status(
            f"Page {self.page + 1} / {self.doc.page_count}    ·    {scale_text}"
            f"        {CHEATS}"
        )

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    # ----- resize handling --------------------------------------------
    def _on_canvas_configure(self, event) -> None:
        size = (event.width, event.height)
        if size == self._last_canvas_size:
            return
        self._last_canvas_size = size
        if not self.doc or self.fstate.scale_mode not in (FIT_WIDTH, FIT_HEIGHT):
            return
        # Debounce: re-render fit modes only once resizing settles.
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self._render_current)

    # ----- UI text scaling --------------------------------------------
    def _apply_ui_scale(self, scale: float) -> None:
        self.ui_scale = fonts.apply_scale(scale)
        if self.doc:
            # Remember per file, like page and page-scale.
            self.fstate.ui_scale = self.ui_scale
            state_mod.save(self.state)
        self.status.config(text=f"UI text {round(self.ui_scale * 100)}%")
        # Restore the normal status line shortly after.
        self.root.after(1200, self._update_status)

    def ui_scale_up(self) -> None:
        self._apply_ui_scale(self.ui_scale * 1.1)

    def ui_scale_down(self) -> None:
        self._apply_ui_scale(self.ui_scale * 0.9)

    def ui_scale_reset(self) -> None:
        self._apply_ui_scale(1.0)

    # ----- misc handlers ----------------------------------------------
    def open_dialog(self) -> None:
        start = Path.home()
        if self.state.last_file:
            parent = Path(self.state.last_file).parent
            if parent.is_dir():
                start = parent
        path = FileBrowser(self.root, start, scaler=self).choose()
        if path:
            self.open_path(path)

    def _save(self) -> None:
        self.fstate.page = self.page
        state_mod.save(self.state)

    def quit(self) -> None:
        self._save()
        if self.doc:
            self.doc.close()
        self.root.destroy()
