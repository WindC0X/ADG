# -*- coding: utf-8 -*-
"""
openpyxl_cjk_height.py
----------------------
Pillow-based wrapped-text height calculator，面向无 Office / 无 GDI 环境。
核心逻辑：
1. 使用 Pillow.ImageFont 逐字累加，在半角块尾添加零宽空格（U+200B），
   使中英文混排、长半角串换行规则接近 Excel 东亚断行。
2. 先得“行数”，最终高度 = 行数 × 行盒高度（per-line pt）。
3. 行盒高度从 _CALIB_TABLE 获取；若无条目，则 fallback =
   (ascent + descent) × 72 / dpi + 1.5 pt，并对齐 0.75 pt 网格。
4. 提供 safe 策略：若宽度减 1 px 就增行，则额外留 1 行，防止临界溢出。

修复要点：
- 正确的字体尺寸换算：px = pt × 96 / 72（之前误把 11pt 当 11px，导致文字偏小、行数偏少）。
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Tuple

from PIL import ImageFont

# ------------------------ 常量与校准 ------------------------ #
_GRID = 0.75                 # Excel 行高网格
_DEFAULT_SLOPE = 1.0         # 全局微调系数
_SCREEN_DPI = 96             # Pillow 的逻辑 DPI（getlength 基于 96 DPI）

# 已校准行盒高度：(font_name.lower(), size_pt) -> per_line_pt
_CALIB_TABLE: dict[tuple[str, float], float] = {
    ("simsun", 11.0): 13.5,
    ("宋体",   11.0): 13.5,
}

_ZERO_WIDTH_SPACE = "\u200B"
_HALF_WIDTH_BLOCK = re.compile(r"([A-Za-z0-9\-·/]+)")

# ------------------------ 工具函数 ------------------------ #
def _inject_soft_breaks(txt: str) -> str:
    """在连续半角块尾部插入零宽空格，模拟 Excel 东亚断行"""
    return _HALF_WIDTH_BLOCK.sub(lambda m: m.group(1) + _ZERO_WIDTH_SPACE,
                                 txt.rstrip())


def _per_line_pt(font_name: str, size_pt: float,
                 ascent: int, descent: int, dpi: int) -> float:
    """
    返回 Excel-式行盒高度（points）。
    1) 若在 _CALIB_TABLE 则直接取
    2) 否则 fallback = (ascent+descent)*72/dpi + 1.5pt，并对齐 0.75pt
    """
    key = (font_name.lower(), round(size_pt, 1))
    if key in _CALIB_TABLE:
        return _CALIB_TABLE[key]

    raw = (ascent + descent) * 72.0 / dpi + 1.5
    return math.ceil(raw / _GRID) * _GRID


@lru_cache(maxsize=128)
def _load_font(font_path_or_name: str, size_pt: float) -> ImageFont.FreeTypeFont:
    """
    加载字体并缓存。
    注意：Pillow 的 truetype(size=...) 期望的是**像素**大小（基于 96 DPI 的逻辑像素）。
    需将 pt 换算为 px：px = pt * 96 / 72
    """
    px_size = int(round(size_pt * _SCREEN_DPI / 72.0))  # 11pt -> 15px
    px_size = max(px_size, 1)
    return ImageFont.truetype(font_path_or_name, size=px_size)


def _wrap_and_count_lines(text: str, width_px: int,
                          font: ImageFont.FreeTypeFont) -> int:
    """逐字累加测宽，超过 width_px 则换行，返回行数"""
    get_len = font.getlength
    lines, accum = 1, ""
    for ch in text:
        if ch in ("\n", "\r"):
            lines, accum = lines + 1, ""
            continue
        if get_len(accum + ch) <= width_px:
            accum += ch
        else:
            lines, accum = lines + 1, ch
    return lines

# ------------------------ 主外部接口 ------------------------ #
def measure(text: str,
            width_px: int,
            font_path_or_name: str = "simsun.ttc",
            font_size_pt: float = 11.0,
            slope: float | None = None,
            safe: bool = False,
            debug: bool = False) -> Tuple[float, int]:
    """
    计算文本在指定像素宽度下的 Excel 行高（points）与行数。

    参数
    ----
    text : str
    width_px : int
        列宽对应的像素宽度（屏幕 96 DPI 或打印像素均可，但要与 Excel 一致）
    font_path_or_name : str
    font_size_pt : float
    slope : float | None
        全局微调系数；留 None 使用 _DEFAULT_SLOPE
    safe : bool
        True → 临界宽度自动 +1 行保护
    debug : bool
        True → 输出内部调试信息
    """
    if slope is None:
        slope = _DEFAULT_SLOPE

    # 1) 预处理文本：半角块加软断
    processed = _inject_soft_breaks(text)

    # 2) 加载字体（pt→px） & 计算行数
    font = _load_font(font_path_or_name, font_size_pt)
    lines = _wrap_and_count_lines(processed, width_px, font)

    # 3) 行盒高度
    ascent, descent = font.getmetrics()  # 单位：px @ 96DPI
    per_line_pt = _per_line_pt(font.getname()[0], font_size_pt,
                               ascent, descent, dpi=_SCREEN_DPI)

    height_pt = lines * per_line_pt * slope

    # 4) safe 策略：若缩 1 px 就增行，则多留 1 行
    if safe:
        if _wrap_and_count_lines(processed, max(width_px - 1, 10), font) > lines:
            height_pt += per_line_pt
            lines += 1

    if debug:
        print(f"[DBG] width_px={width_px}, pt={font_size_pt}, px_size={int(round(font_size_pt * _SCREEN_DPI / 72.0))}, "
              f"lines={lines}, per_line_pt={per_line_pt}, height={height_pt:.2f}pt")

    return round(height_pt, 2), lines


# ------------------------ CLI 自测 ------------------------ #
if __name__ == "__main__":
    w_px = 289  # 40.625 字符在 96 DPI 下的屏幕像素
    txt_single = "测试单行文本"
    txt_multi = txt_single * 30  # 约 8 行

    for label, txt in [("single", txt_single), ("8 行", txt_multi)]:
        h, l = measure(txt, w_px, "simsun.ttc", 11.0, debug=True)
        print(f"{label}: {h} pt, {l} 行")