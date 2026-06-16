// Thin wrapper over PDF.js that renders one page at a time to a canvas.
// Mirrors the standalone document.py: scale 1.0 == 72 DPI == 1px per point.

import * as pdfjsLib from "./vendor/pdfjs/pdf.js";

const { TextLayer } = pdfjsLib;
const VENDOR = new URL("./vendor/pdfjs/", import.meta.url);
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL("pdf.worker.js", VENDOR).href;

// Heuristic: is a page's extracted text real, copyable Unicode — or glyph-index
// garbage? PDFs whose fonts use Identity-H encoding with no ToUnicode map (a
// common CJK case) yield text that renders fine but extracts as nonsense: the
// codes are raw glyph indices, so they land on scattered, unrelated scripts and
// C0/C1 control codes. Building a text layer from that gives garbage copies and
// erratic selection (the junk includes RTL + combining chars), so we detect it
// and skip the layer instead. Thresholds calibrated on known good (Latin + CJK)
// and bad PDFs: garbage pages show ctrl ratio ~0.16+ and 7-9 distinct scripts;
// good pages show ~0 control codes and 1-2 scripts.
const COPY_SCRIPTS = ["Latin", "Han", "Hiragana", "Katakana", "Hangul",
  "Bopomofo", "Cyrillic", "Greek", "Arabic", "Hebrew", "Devanagari",
  "Armenian", "Thai"];
const COPY_SCRIPT_RES = COPY_SCRIPTS.map((s) => [s, new RegExp(`\\p{Script=${s}}`, "u")]);
const COPY_LETTER = /\p{L}/u;

function scriptOf(ch) {
  for (const [name, re] of COPY_SCRIPT_RES) if (re.test(ch)) return name;
  return "Other";
}

function isCopyableText(text) {
  let visible = 0;
  let control = 0;
  const scriptCounts = Object.create(null);
  for (const ch of text) {
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") continue;
    const cp = ch.codePointAt(0);
    visible++;
    if (cp < 0x20 || (cp >= 0x7f && cp <= 0x9f) || cp === 0xfffd) control++;
    if (COPY_LETTER.test(ch)) {
      const s = scriptOf(ch);
      scriptCounts[s] = (scriptCounts[s] || 0) + 1;
    }
  }
  if (visible < 16) return true; // too little text to judge — assume fine
  const controlRatio = control / visible;
  const distinctScripts = Object.values(scriptCounts).filter((c) => c >= 3).length;
  return !(controlRatio > 0.08 || distinctScripts >= 4);
}

export class PdfDoc {
  static async open(data) {
    // data: ArrayBuffer. PDF.js may detach it; we keep the parsed doc, not data.
    const task = pdfjsLib.getDocument({
      data,
      standardFontDataUrl: new URL("standard_fonts/", VENDOR).href,
      // CMaps let PDF.js map CID-keyed CJK fonts (Simplified GB1, Traditional
      // CNS1, JP, KR) to Unicode, so selected text copies correctly. Rendering
      // works without them; text extraction does not.
      cMapUrl: new URL("cmaps/", VENDOR).href,
      cMapPacked: true,
    });
    const doc = await task.promise;
    return new PdfDoc(doc);
  }

  constructor(doc) {
    this._doc = doc;
    this._pages = new Map(); // index (0-based) -> PDFPageProxy
    this._task = null;
  }

  get pageCount() {
    return this._doc.numPages;
  }

  async _page(index) {
    let p = this._pages.get(index);
    if (!p) {
      p = await this._doc.getPage(index + 1); // PDF.js is 1-based
      this._pages.set(index, p);
    }
    return p;
  }

  // Displayed [width, height] in points at the given extra rotation (degrees
  // clockwise, on top of the page's own /Rotate). Swaps for 90/270.
  async pageSize(index, rotation = 0) {
    const page = await this._page(index);
    const vp = page.getViewport({ scale: 1, rotation: page.rotate + rotation });
    return [vp.width, vp.height];
  }

  // Render page `index` at `scale` (1.0 = 72 DPI) into `canvas`, sharp on HiDPI
  // via `dpr`, rotated `rotation` degrees clockwise. Returns the logical
  // {width, height} in CSS pixels.
  async render(index, scale, dpr, canvas, rotation = 0) {
    const page = await this._page(index);
    const viewport = page.getViewport({ scale, rotation: page.rotate + rotation });
    const out = dpr || 1;
    canvas.width = Math.floor(viewport.width * out);
    canvas.height = Math.floor(viewport.height * out);
    canvas.style.width = Math.floor(viewport.width) + "px";
    canvas.style.height = Math.floor(viewport.height) + "px";
    const ctx = canvas.getContext("2d");
    const transform = out !== 1 ? [out, 0, 0, out, 0, 0] : undefined;
    this._task = page.render({ canvasContext: ctx, viewport, transform });
    await this._task.promise;
    return { width: viewport.width, height: viewport.height };
  }

  // Build a selectable text overlay for page `index` matching a render() at the
  // same `scale`/`rotation`. Returns { copyable, container }:
  //   - copyable false  -> the page's text is glyph-index garbage (see
  //     isCopyableText); container is null and the caller should skip selection.
  //   - copyable true   -> container is a *detached* <div class="textLayer"> of
  //     absolutely-positioned transparent spans the browser can select and copy;
  //     the caller sets `--scale-factor` (= scale) on it and swaps it into the
  //     DOM. Built detached (not into a shared node) so overlapping renders
  //     can't interleave their spans — only the latest result gets swapped in.
  async renderText(index, scale, rotation = 0) {
    const page = await this._page(index);
    const source = await page.getTextContent();
    const text = source.items
      .map((it) => (it.str === undefined ? "" : it.str))
      .join("");
    if (!isCopyableText(text)) return { copyable: false, container: null };
    const viewport = page.getViewport({ scale, rotation: page.rotate + rotation });
    const container = document.createElement("div");
    container.className = "textLayer";
    const layer = new TextLayer({ textContentSource: source, container, viewport });
    await layer.render();
    return { copyable: true, container };
  }

  // Resolve a PDF destination (named or explicit) to a 0-based page index.
  async _destToPage(dest) {
    if (!dest) return null;
    let explicit = dest;
    if (typeof dest === "string") {
      explicit = await this._doc.getDestination(dest);
    }
    if (!Array.isArray(explicit) || !explicit[0]) return null;
    try {
      return await this._doc.getPageIndex(explicit[0]);
    } catch (_) {
      return null;
    }
  }

  // Flatten the document outline (bookmarks) to a list of
  // { title, level, page } with page resolved to a 0-based index.
  async getToc() {
    let raw;
    try {
      raw = await this._doc.getOutline();
    } catch (_) {
      return [];
    }
    if (!raw || !raw.length) return [];
    const out = [];
    const walk = async (items, level) => {
      for (const it of items) {
        out.push({
          title: (it.title || "").trim(),
          level,
          page: await this._destToPage(it.dest),
        });
        if (it.items && it.items.length) await walk(it.items, level + 1);
      }
    };
    await walk(raw, 0);
    return out;
  }

  cancel() {
    if (this._task) {
      try {
        this._task.cancel();
      } catch (_) {}
    }
  }

  destroy() {
    try {
      this._doc.destroy();
    } catch (_) {}
  }
}
