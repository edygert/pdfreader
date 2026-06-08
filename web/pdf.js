// Thin wrapper over PDF.js that renders one page at a time to a canvas.
// Mirrors the standalone document.py: scale 1.0 == 72 DPI == 1px per point.

import * as pdfjsLib from "./vendor/pdfjs/pdf.js";

const VENDOR = new URL("./vendor/pdfjs/", import.meta.url);
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL("pdf.worker.js", VENDOR).href;

export class PdfDoc {
  static async open(data) {
    // data: ArrayBuffer. PDF.js may detach it; we keep the parsed doc, not data.
    const task = pdfjsLib.getDocument({
      data,
      standardFontDataUrl: new URL("standard_fonts/", VENDOR).href,
    });
    const doc = await task.promise;
    return new PdfDoc(doc);
  }

  constructor(doc) {
    this._doc = doc;
    this._pages = new Map(); // index (0-based) -> PDFPageProxy
    this._sizes = new Map(); // index -> [wPt, hPt]
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

  async pageSize(index) {
    let s = this._sizes.get(index);
    if (!s) {
      const vp = (await this._page(index)).getViewport({ scale: 1 });
      s = [vp.width, vp.height];
      this._sizes.set(index, s);
    }
    return s;
  }

  // Render page `index` at `scale` (1.0 = 72 DPI) into `canvas`, sharp on HiDPI
  // via `dpr`. Returns the logical {width, height} in CSS pixels.
  async render(index, scale, dpr, canvas) {
    const page = await this._page(index);
    const viewport = page.getViewport({ scale });
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
