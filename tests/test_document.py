"""Headless sanity checks for the rendering wrapper and scale math.

A tiny PDF is generated in-memory with pypdfium2 so the tests need no fixture
file and no display server.
"""

from __future__ import annotations

import pypdfium2 as pdfium
import pytest


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("pdf") / "sample.pdf"
    pdf = pdfium.PdfDocument.new()
    # Two pages of distinct sizes (US Letter then A5-ish) in points.
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
        img = doc.render(0, scale=2.0)
        # 612pt * 2.0 = 1224 px wide (allow ±1 for rounding).
        assert abs(img.width - 1224) <= 1
        assert abs(img.height - 1584) <= 1
    finally:
        doc.close()


def test_rotation_swaps_dimensions(sample_pdf: str) -> None:
    from pdfreader.document import Document

    doc = Document(sample_pdf)
    try:
        # page_size swaps for 90/270.
        assert doc.page_size(0, 0) == pytest.approx((612, 792))
        assert doc.page_size(0, 90) == pytest.approx((792, 612))
        assert doc.page_size(0, 180) == pytest.approx((612, 792))
        # render swaps the raster too.
        img = doc.render(0, scale=1.0, rotation=90)
        assert abs(img.width - 792) <= 1 and abs(img.height - 612) <= 1
    finally:
        doc.close()


def test_fit_width_scale_math() -> None:
    # Mirrors viewer._effective_scale for FIT_WIDTH: scale = viewport / w_pt.
    w_pt = 612
    viewport_w = 918
    scale = viewport_w / w_pt
    assert scale == pytest.approx(1.5)


def test_state_roundtrip_per_file(tmp_path, monkeypatch) -> None:
    from pdfreader import state as st

    cfg = tmp_path / "cfg"
    monkeypatch.setattr(st, "_config_dir", lambda: cfg)

    s = st.State()
    a = s.for_file("/docs/a.pdf")
    a.page, a.scale_mode, a.custom_factor, a.ui_scale, a.rotation = (
        5, st.CUSTOM, 0.5, 1.4, 90,
    )
    b = s.for_file("/docs/b.pdf")
    b.page, b.scale_mode, b.ui_scale = 8, st.FIT_HEIGHT, 0.8
    s.last_file = "/docs/b.pdf"
    st.save(s)

    loaded = st.load()
    assert loaded.last_file == "/docs/b.pdf"
    assert loaded.for_file("/docs/a.pdf").page == 5
    assert loaded.for_file("/docs/a.pdf").custom_factor == pytest.approx(0.5)
    assert loaded.for_file("/docs/a.pdf").ui_scale == pytest.approx(1.4)
    assert loaded.for_file("/docs/a.pdf").rotation == 90
    assert loaded.for_file("/docs/b.pdf").scale_mode == st.FIT_HEIGHT
    assert loaded.for_file("/docs/b.pdf").ui_scale == pytest.approx(0.8)
    assert loaded.for_file("/docs/b.pdf").rotation == 0
