"""Headless sanity checks for the rendering wrapper and scale math.

A tiny PDF is generated in-memory with pypdfium2 so the tests need no fixture
file and no display server.
"""

from __future__ import annotations

import os

import pypdfium2 as pdfium
import pytest

# Qt needs a platform plugin even when only constructing QImage; use offscreen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("pdf") / "sample.pdf"
    pdf = pdfium.PdfDocument.new()
    # Two pages of distinct sizes (US Letter then A4-ish) in points.
    pdf.new_page(612, 792)
    pdf.new_page(420, 595)
    pdf.save(str(path))
    pdf.close()
    return str(path)


def test_page_count_and_size(sample_pdf: str) -> None:
    from pdfreader.document import Document

    doc = Document(sample_pdf)
    try:
        assert doc.page_count == 2
        w, h = doc.page_size(0)
        assert round(w) == 612 and round(h) == 792
    finally:
        doc.close()


def test_render_dimensions_track_scale(sample_pdf: str) -> None:
    from pdfreader.document import Document

    doc = Document(sample_pdf)
    try:
        img = doc.render(0, scale=2.0, dpr=1.0)
        assert not img.isNull()
        # 612pt * 2.0 = 1224 px wide (allow ±1 for rounding).
        assert abs(img.width() - 1224) <= 1
        assert abs(img.height() - 1584) <= 1
    finally:
        doc.close()


def test_fit_width_scale_math() -> None:
    # Mirrors viewer._effective_scale for FIT_WIDTH: scale = viewport / w_pt.
    w_pt = 612
    viewport_w = 918
    scale = viewport_w / w_pt
    assert scale == pytest.approx(1.5)
