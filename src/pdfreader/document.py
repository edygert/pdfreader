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

    def page_size(self, index: int) -> tuple[float, float]:
        """Return (width, height) of a page in points (1/72 inch)."""
        return self._pdf[index].get_size()

    def render(self, index: int, scale: float) -> Image.Image:
        """Render ``index`` at ``scale`` (1.0 = 72 DPI) to a PIL image.

        At scale 1.0 a point maps to one pixel, so a page's pixel width equals
        its width in points — which is what the fit-to-width/height math relies
        on.
        """
        page = self._pdf[index]
        return page.render(scale=scale).to_pil()
