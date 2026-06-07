"""Thin wrapper over pypdfium2 that renders pages to ``QImage``."""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PySide6.QtGui import QImage


class Document:
    """An open PDF. Renders one page at a time, on demand."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._pdf = pdfium.PdfDocument(self.path)
        # Hold a reference to the numpy buffer backing the most recent QImage;
        # QImage does not copy the data, so the array must outlive it.
        self._buf = None

    def close(self) -> None:
        try:
            self._pdf.close()
        except Exception:
            pass

    @property
    def page_count(self) -> int:
        return len(self._pdf)

    def page_size(self, index: int) -> tuple[float, float]:
        """Return (width, height) of a page in points (1/72 inch)."""
        return self._pdf[index].get_size()

    def render(self, index: int, scale: float, dpr: float = 1.0) -> QImage:
        """Render ``index`` at ``scale`` (1.0 = 72 DPI), accounting for ``dpr``.

        The returned QImage carries the device-pixel-ratio so Qt downscales it
        to logical size on HiDPI displays, keeping text crisp.
        """
        page = self._pdf[index]
        bitmap = page.render(scale=scale * dpr, rev_byteorder=True)
        arr = bitmap.to_numpy()  # (h, w, 3 or 4), uint8 — RGB(A) byte order
        self._buf = arr  # keep alive: QImage does not copy the buffer
        height, width = arr.shape[0], arr.shape[1]
        channels = arr.shape[2] if arr.ndim == 3 else 1
        # pypdfium2 emits RGB for opaque pages and RGBA when alpha is present.
        fmt = (
            QImage.Format.Format_RGBA8888
            if channels == 4
            else QImage.Format.Format_RGB888
        )
        image = QImage(arr.data, width, height, arr.strides[0], fmt)
        image.setDevicePixelRatio(dpr)
        return image
