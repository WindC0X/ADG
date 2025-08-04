# -*- coding: utf-8 -*-
"""
gdi_height_measure.py  (2025-08-03)
-----------------------------------
GDI-based row-height measurer that matches Excel printed layout.

- Keep Excel 'column width (chars)' -> **printer pixels** conversion.
- Use DrawText(DT_CALCRECT|DT_EDITCONTROL|DT_WORDBREAK|DT_NOPREFIX) for line count.
- Per-line height from calib table (SimSun 11pt -> 13.5pt).
- 'safe' strategy: probe width-1..4 px; if line count increases, add one line.
- Swallow 'row_info' kwarg for compatibility with callers.
"""

from __future__ import annotations
import contextlib, math, re
from dataclasses import dataclass

import win32con
import win32gui
import win32print
import win32ui


# ------------------------- public types ------------------------- #
@dataclass
class FontSpec:
    name: str = "SimSun"
    size_pt: float = 11.0
    weight: int = 400
    italic: bool = False
    charset: int = win32con.DEFAULT_CHARSET


# ------------------------- main class --------------------------- #
class PrinterTextMeasurer:
    """Owns a printer HDC and caches HFONT objects."""
    _CALIB_TABLE: dict[tuple[str, float], float] = {
        ("simsun", 11.0): 13.5,
    }
    # Edge probes: try shrinking width by these px; if lines increase -> reserve 1 line
    SAFE_OFFSETS = (1, 2, 3, 4)

    def __init__(self, printer: str | None = None):
        self._printer_name = printer or win32print.GetDefaultPrinter()
        self._h_printer = None
        self._hdc = None
        self._font_cache: dict[tuple, int] = {}

    # ---- context mgmt ----
    def __enter__(self):
        self._h_printer = win32print.OpenPrinter(self._printer_name)
        self._hdc = win32gui.CreateDC("WINSPOOL", self._printer_name, None)
        return self

    def __exit__(self, exc_type, exc, tb):
        for h in self._font_cache.values():
            with contextlib.suppress(Exception):
                win32gui.DeleteObject(h)
        if self._hdc:
            with contextlib.suppress(Exception):
                win32gui.DeleteDC(self._hdc)
        if self._h_printer:
            with contextlib.suppress(Exception):
                win32print.ClosePrinter(self._h_printer)

    # ---- DPI helpers ----
    def _dpi_x(self) -> int:
        return win32ui.GetDeviceCaps(self._hdc, win32con.LOGPIXELSX)

    def _dpi_y(self) -> int:
        return win32ui.GetDeviceCaps(self._hdc, win32con.LOGPIXELSY)

    # ---- font cache ----
    def _hfont_for(self, spec: FontSpec) -> int:
        key = (spec.name.lower(), spec.size_pt, spec.weight, spec.italic, spec.charset)
        if key in self._font_cache:
            return self._font_cache[key]
        lf = win32gui.LOGFONT()
        # Negative lfHeight -> char height in logical units (device pixels for MM_TEXT)
        lf.lfHeight  = -round(spec.size_pt * self._dpi_y() / 72)
        lf.lfWeight  = spec.weight
        lf.lfItalic  = int(spec.italic)
        lf.lfCharSet = spec.charset
        lf.lfFaceName = spec.name
        hfont = win32gui.CreateFontIndirect(lf)
        self._font_cache[key] = hfont
        return hfont

    # ---- Excel column width (chars) -> **printer pixels** ----
    def excel_width_to_printer_px(self, col_chars: float) -> int:
        """
        Excel column width to effective text rendering width in printer pixels.
        This is the actual usable area for text, excluding Excel's internal margins.
        Formula: chars * 7 (no +5, as that's Excel's display width including margins)
        """
        px_screen = (col_chars * 12.0) if col_chars < 1.0 else (col_chars * 7.0)
        return int(round(px_screen * self._dpi_x() / 96.0))

    # ---- core measurement ----
    def measure(self,
                text: str,
                width_px: int,
                spec: FontSpec | None = None,
                *,
                strategy: str = "exact",
                debug: bool = False,
                soft_break: bool = True
                ) -> tuple[float, int, bool]:
        """
        Measure height in points and line count for given device-pixel width.
        Returns: (height_pt, line_count, is_edge)
        """
        spec = spec or FontSpec()
        hfont = self._hfont_for(spec)
        old = win32gui.SelectObject(self._hdc, hfont)

        try:
            # Inject zero-width space after ASCII runs to mimic East Asian wrapping
            processed = (re.sub(r'([A-Za-z0-9\-·/]+)', lambda m: m.group(1) + "\u200B",
                                text.rstrip()) if soft_break else text.rstrip())

            def _count_lines(w_px: int) -> int:
                rect = (0, 0, max(w_px, 1), 0)
                flags = (win32con.DT_CALCRECT | win32con.DT_WORDBREAK |
                         win32con.DT_EDITCONTROL | win32con.DT_NOPREFIX)
                rc = win32gui.DrawText(self._hdc, processed, -1, rect, flags)
                # pywin32 may return [height, (l,t,r,b)] or a tuple; normalize
                if isinstance(rc, list) and len(rc) == 2:
                    height_px = rc[1][3] - rc[1][1]
                else:
                    # (l, t, r, b)
                    height_px = rc[3] - rc[1]
                tm = win32gui.GetTextMetrics(self._hdc)
                h_line = tm.get("tmHeight", tm.get("Height", 1))
                ext    = tm.get("tmExternalLeading", tm.get("ExternalLeading", 0))
                # Each visual row roughly occupies (tmHeight + tmExternalLeading)
                return max(1, math.ceil((height_px + ext) / (h_line + ext)))

            lines = _count_lines(width_px)

            is_edge = False
            if strategy == "safe":
                # Probe –1/–2/–3/–4 px. If any causes an extra line, reserve 1 line.
                for offs in self.SAFE_OFFSETS:
                    if _count_lines(max(50, width_px - offs)) > lines:
                        lines += 1
                        is_edge = True
                        break

            # per-line height (pt)
            per_line_pt = self._CALIB_TABLE.get(
                (spec.name.lower(), round(spec.size_pt, 2)), 13.5
            )
            height_pt = lines * per_line_pt

            return height_pt, lines, is_edge

        finally:
            win32gui.SelectObject(self._hdc, old)

    # ---- convenience wrapper: column width (chars) ----
    def measure_for_excel_col(self,
                              text: str,
                              col_width_chars: float,
                              spec: FontSpec | None = None,
                              **kw) -> tuple[float, int]:
        """
        Accepts Excel column width in characters; converts to **printer pixels**,
        then calls measure(). Swallows 'row_info' if provided by caller.
        """
        kw.pop("row_info", None)  # compatibility: do not forward to measure()
        w_px = self.excel_width_to_printer_px(col_width_chars)
        h_pt, lines, _ = self.measure(text, w_px, spec, **kw)
        return h_pt, lines


# ---- CLI sanity test ----
if __name__ == "__main__":
    sample = ("［厦门市海沧区］征拆工作专题会议的纪要［2022年８月２５日，厦门市海沧区东孚街道党工委书记赖大庆主持召开会议，"
              "研究关于鼎美村原房屋权证登记时误采用谐音字或方言谐音导致与身份证名字不一致的相关问题］")
    with PrinterTextMeasurer() as m:
        h, n, _ = m.measure_for_excel_col(sample, 40.625, FontSpec("SimSun", 11),
                                          strategy="safe", debug=False)
        # 生产环境移除调试输出