"""Thin wrapper over pypdfium2 that renders pages to PIL images."""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


class Document:
    """An open PDF. Renders one page at a time, on demand."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._pdf = pdfium.PdfDocument(self.path)

    def close(self) -> None:
        try:
            self._pdf.close()
        except Exception:
            pass

    @property
    def page_count(self) -> int:
        return len(self._pdf)

    def page_size(self, index: int, rotation: int = 0) -> tuple[float, float]:
        """Return displayed (width, height) in points (1/72 inch).

        ``rotation`` is degrees clockwise; 90/270 swap width and height.
        """
        w, h = self._pdf[index].get_size()
        if rotation in (90, 270):
            return h, w
        return w, h

    def render(self, index: int, scale: float, rotation: int = 0) -> Image.Image:
        """Render ``index`` at ``scale`` (1.0 = 72 DPI), rotated ``rotation``
        degrees clockwise, to a PIL image.

        At scale 1.0 a point maps to one pixel, so a page's pixel width equals
        its width in points — which is what the fit-to-width/height math relies
        on.
        """
        page = self._pdf[index]
        return page.render(scale=scale, rotation=rotation).to_pil()
