"""Named, scalable Tk fonts for all UI chrome.

Every chrome widget (file browser, help window, status bar) references one of
these named fonts. Tk updates such widgets live when the named font is
reconfigured, so changing the scale resizes the whole UI instantly and
uniformly. The PDF page image is rendered separately and is unaffected.
"""

from __future__ import annotations

import tkinter.font as tkfont

# Custom named fonts and their readable base sizes (at scale 1.0).
_CUSTOM: dict[str, dict] = {
    "UiFont": {"size": 12, "weight": "normal"},
    "UiBold": {"size": 12, "weight": "bold"},
    "UiMono": {"size": 11, "weight": "normal", "family": "TkFixedFont"},
    "UiTitle": {"size": 15, "weight": "bold"},
    "UiSmall": {"size": 10, "weight": "normal"},
}

# Standard Tk fonts to scale too, so simpledialog and any default-font widget
# grow/shrink along with our own.
_STANDARD = (
    "TkDefaultFont",
    "TkTextFont",
    "TkFixedFont",
    "TkMenuFont",
    "TkHeadingFont",
    "TkCaptionFont",
    "TkSmallCaptionFont",
    "TkIconFont",
    "TkTooltipFont",
)

_MIN_SCALE = 0.6
_MAX_SCALE = 3.0

# Base (scale-1.0) point sizes, captured once in init_fonts.
_base: dict[str, int] = {}
# Retain the custom Font objects: a tkfont.Font deletes its underlying named
# font on garbage collection, so dropping the reference would erase it.
_fonts: dict[str, "tkfont.Font"] = {}
_initialised = False


def init_fonts(root) -> None:
    """Create the custom fonts and record base sizes. Idempotent."""
    global _initialised
    if _initialised:
        return

    for name, spec in _CUSTOM.items():
        family = spec.get("family", "TkDefaultFont")
        _fonts[name] = tkfont.Font(
            root=root,
            name=name,
            family=family,
            size=spec["size"],
            weight=spec["weight"],
            exists=False,
        )
        _base[name] = spec["size"]

    for name in _STANDARD:
        try:
            f = tkfont.nametofont(name)
        except Exception:
            continue
        size = f.cget("size")
        # Tk reports negative sizes in pixels; normalise to a positive baseline.
        _base[name] = abs(size) if size else 10

    _initialised = True


def apply_scale(scale: float) -> float:
    """Set every managed font to base*scale. Returns the clamped scale used."""
    scale = max(_MIN_SCALE, min(scale, _MAX_SCALE))
    for name, base in _base.items():
        try:
            tkfont.nametofont(name).configure(size=max(1, round(base * scale)))
        except Exception:
            continue
    return scale
