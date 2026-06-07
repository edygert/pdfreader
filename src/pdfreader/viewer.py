"""Main window: page display, scaling, navigation and keybindings."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
)

from . import state as state_mod
from .document import Document
from .help import SHORTCUTS, HelpDialog
from .state import CUSTOM, FIT_HEIGHT, FIT_WIDTH, FileState, State

_MARGIN = 4  # px shaved off the viewport so fit modes avoid a stray scrollbar


class MainWindow(QMainWindow):
    def __init__(self, state: State) -> None:
        super().__init__()
        self.setWindowTitle("pdfreader")
        self.resize(900, 1100)

        self.state = state
        self.doc: Document | None = None
        self.page = 0
        # Per-file reading position (page + scale). Replaced on open_path with
        # the record for the actual file; a transient default until then.
        self.fstate: FileState = FileState()

        self.label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.label.setText("Press  O  to open a PDF   ·   ?  for help")

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.label)
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self.scroll)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)
        self._resize_timer.timeout.connect(self._on_resize_settled)

        self._handlers = {
            "open": self.open_dialog,
            "goto": self.goto_dialog,
            "next": self.next_page,
            "prev": self.prev_page,
            "first": self.first_page,
            "last": self.last_page,
            "zoom_in": self.zoom_in,
            "zoom_out": self.zoom_out,
            "fit_width": self.fit_width,
            "fit_height": self.fit_height,
            "custom_scale": self.custom_scale_dialog,
            "help": self.show_help,
            "quit": self.close,
        }
        self._install_shortcuts()
        self._build_menu()
        self.statusBar().showMessage("No document open")

    # ----- setup -------------------------------------------------------
    def _install_shortcuts(self) -> None:
        for sc in SHORTCUTS:
            handler = self._handlers[sc.action]
            for key in sc.keys:
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(handler)

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._action("Open…", self.open_dialog, "O"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Quit", self.close, "Q"))

        view = bar.addMenu("&View")
        view.addAction(self._action("Fit width", self.fit_width, "W"))
        view.addAction(self._action("Fit height", self.fit_height, "H"))
        view.addAction(self._action("Custom scale…", self.custom_scale_dialog, "F"))
        view.addSeparator()
        view.addAction(self._action("Zoom in", self.zoom_in, "+"))
        view.addAction(self._action("Zoom out", self.zoom_out, "-"))

        go = bar.addMenu("&Go")
        go.addAction(self._action("Go to page…", self.goto_dialog, "G"))
        go.addAction(self._action("Next page", self.next_page, "J"))
        go.addAction(self._action("Previous page", self.prev_page, "K"))
        go.addAction(self._action("First page", self.first_page, "Home"))
        go.addAction(self._action("Last page", self.last_page, "End"))

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._action("Shortcuts…", self.show_help, "F1"))

    def _action(self, text: str, slot, shortcut_hint: str) -> QAction:
        action = QAction(text, self)
        # Hint only — real shortcuts are the global QShortcuts so each action
        # can have several keys. Showing one keeps the menu readable.
        action.setShortcut(QKeySequence(shortcut_hint))
        action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        action.triggered.connect(slot)
        return action

    # ----- document lifecycle -----------------------------------------
    def open_path(self, path: str) -> bool:
        try:
            doc = Document(path)
        except Exception as exc:  # noqa: BLE001 - surface any load failure
            QMessageBox.critical(self, "Cannot open PDF", f"{path}\n\n{exc}")
            return False

        # Resolve to an absolute path so the same file keys the same record
        # regardless of how it was opened (CLI, dialog, relative path).
        path = str(Path(path).resolve())

        if self.doc is not None:
            self.doc.close()
        self.doc = doc
        self.state.last_file = path
        # Restore this file's remembered page and scale (new files default).
        self.fstate = self.state.for_file(path)
        self.setWindowTitle(f"{Path(path).name} — pdfreader")

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
        # Reset scroll to top of the new page.
        self.scroll.verticalScrollBar().setValue(0)

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
        page, ok = QInputDialog.getInt(
            self,
            "Go to page",
            f"Page (1–{self.doc.page_count}):",
            value=self.page + 1,
            minValue=1,
            maxValue=self.doc.page_count,
        )
        if ok:
            self._goto(page - 1)

    # ----- scaling -----------------------------------------------------
    def _effective_scale(self) -> float:
        assert self.doc is not None
        w_pt, h_pt = self.doc.page_size(self.page)
        vp = self.scroll.viewport().size()
        if self.fstate.scale_mode == FIT_WIDTH:
            return max(0.05, (vp.width() - _MARGIN) / w_pt)
        if self.fstate.scale_mode == FIT_HEIGHT:
            return max(0.05, (vp.height() - _MARGIN) / h_pt)
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
        self._set_custom(self._current_factor() * 1.25)

    def zoom_out(self) -> None:
        self._set_custom(self._current_factor() * 0.8)

    def fit_width(self) -> None:
        self.fstate.scale_mode = FIT_WIDTH
        self._render_current()
        self._save()

    def fit_height(self) -> None:
        self.fstate.scale_mode = FIT_HEIGHT
        self._render_current()
        self._save()

    def custom_scale_dialog(self) -> None:
        if not self.doc:
            return
        percent, ok = QInputDialog.getDouble(
            self,
            "Custom scale",
            "Scale (%):",
            value=round(self._current_factor() * 100, 1),
            minValue=5.0,
            maxValue=1200.0,
            decimals=1,
        )
        if ok:
            self._set_custom(percent / 100.0)

    # ----- rendering ---------------------------------------------------
    def _render_current(self) -> None:
        if not self.doc:
            return
        scale = self._effective_scale()
        dpr = self.devicePixelRatioF() or 1.0
        image = self.doc.render(self.page, scale, dpr)
        self.label.setPixmap(QPixmap.fromImage(image))
        # For fit modes the page fills a dimension and should hug the viewport;
        # for custom/zoom the label must grow so the scroll area can pan it.
        resizable = self.fstate.scale_mode in (FIT_WIDTH, FIT_HEIGHT)
        self.scroll.setWidgetResizable(resizable)
        if not resizable:
            self.label.adjustSize()
        self._update_status()

    def _update_status(self) -> None:
        if not self.doc:
            self.statusBar().showMessage("No document open")
            return
        percent = round(self._effective_scale() * 100)
        mode = self.fstate.scale_mode
        if mode == FIT_WIDTH:
            scale_text = f"Fit width ({percent}%)"
        elif mode == FIT_HEIGHT:
            scale_text = f"Fit height ({percent}%)"
        else:
            scale_text = f"{percent}%"
        self.statusBar().showMessage(
            f"Page {self.page + 1} / {self.doc.page_count}    ·    {scale_text}"
        )

    # ----- misc handlers ----------------------------------------------
    def open_dialog(self) -> None:
        start_dir = ""
        if self.state.last_file:
            start_dir = str(Path(self.state.last_file).parent)
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", start_dir, "PDF files (*.pdf);;All files (*)"
        )
        if path:
            self.open_path(path)

    def show_help(self) -> None:
        HelpDialog(self).exec()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt signature
        super().resizeEvent(event)
        # Re-render fit modes only after resizing settles, to avoid thrashing.
        if self.doc and self.fstate.scale_mode in (FIT_WIDTH, FIT_HEIGHT):
            self._resize_timer.start()

    def _on_resize_settled(self) -> None:
        if self.doc:
            self._render_current()

    def _save(self) -> None:
        self.fstate.page = self.page
        state_mod.save(self.state)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt signature
        self._save()
        if self.doc:
            self.doc.close()
        super().closeEvent(event)
