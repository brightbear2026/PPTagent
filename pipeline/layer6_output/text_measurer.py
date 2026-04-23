"""
文本预测量工具

使用 PIL.ImageFont 预先测量文本渲染尺寸，
在放置到PPT之前判断是否会溢出，从而避免重叠。
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MeasuredText:
    """文本测量结果"""
    width_emu: int           # 渲染宽度 (EMU)
    height_emu: int          # 渲染高度 (EMU)
    line_count: int          # 行数
    overflows: bool          # 是否溢出
    suggested_font_pt: float # 建议字号（溢出时自动缩小）


# EMU 转换常量
EMU_PER_INCH = 914400
EMU_PER_PT = 12700
EMU_PER_PX = 9525  # 近似值 (96 DPI)

# 字体文件路径搜索顺序
_FONT_SEARCH_PATHS = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Linux (common)
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/arial.ttf",
]


def _find_font_path() -> str:
    """查找系统中可用的字体文件"""
    for path in _FONT_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    return None


# 全局字体缓存
_cached_font_path = None


def _get_font_path() -> str:
    global _cached_font_path
    if _cached_font_path is None:
        _cached_font_path = _find_font_path()
    return _cached_font_path


class TextMeasurer:
    """
    文本渲染尺寸预测量。

    在放置文本到PPT之前，使用 PIL 预先计算渲染尺寸，
    判断是否会超出目标区域的边界。
    """

    def __init__(self, default_font_path: str = None):
        self.font_path = default_font_path or _get_font_path()
        self._font_cache = {}

    def measure(
        self,
        text: str,
        font_size_pt: float,
        max_width_emu: int,
        max_height_emu: int = 0,
        line_spacing: float = 1.2,
    ) -> MeasuredText:
        """
        测量文本在指定字号下的渲染尺寸。

        Args:
            text: 要测量的文本（可能包含多行）
            font_size_pt: 字号（磅）
            max_width_emu: 容器最大宽度 (EMU)
            max_height_emu: 容器最大高度 (EMU)，0表示不限
            line_spacing: 行间距倍数

        Returns:
            MeasuredText 测量结果
        """
        if not text:
            return MeasuredText(0, 0, 0, False, font_size_pt)

        try:
            font = self._get_font(font_size_pt)
        except Exception:
            # PIL不可用时，用估算
            return self._estimate(text, font_size_pt, max_width_emu, max_height_emu)

        max_width_px = max_width_emu / EMU_PER_PX

        lines = text.split('\n')
        total_height_px = 0
        max_line_width_px = 0

        for line in lines:
            if not line:
                # 空行高度约等于字号
                total_height_px += font_size_pt * line_spacing
                continue

            # 计算换行后的实际行数
            line_width_px = self._measure_line_width(line, font)
            max_line_width_px = max(max_line_width_px, line_width_px)

            if line_width_px <= max_width_px:
                total_height_px += font_size_pt * line_spacing
            else:
                # 需要换行
                wrapped_lines = self._estimate_wrap_lines(
                    line, font, max_width_px
                )
                total_height_px += wrapped_lines * font_size_pt * line_spacing

        width_emu = int(max_line_width_px * EMU_PER_PX)
        height_emu = int(total_height_px * EMU_PER_PX)

        overflows = False
        if max_width_emu > 0 and width_emu > max_width_emu:
            overflows = True
        if max_height_emu > 0 and height_emu > max_height_emu:
            overflows = True

        suggested_pt = font_size_pt
        if overflows and max_height_emu > 0:
            # 估算能让文本fit的字号
            ratio = max_height_emu / max(height_emu, 1)
            suggested_pt = max(8.0, font_size_pt * ratio)

        return MeasuredText(
            width_emu=width_emu,
            height_emu=height_emu,
            line_count=max(1, int(total_height_px / (font_size_pt * line_spacing))),
            overflows=overflows,
            suggested_font_pt=round(suggested_pt, 1),
        )

    def measure_text_blocks(
        self,
        text_blocks: list,
        font_size_pt: float,
        max_width_emu: int,
        max_height_emu: int,
    ) -> MeasuredText:
        """
        测量多个TextBlock的合计渲染尺寸。
        """
        # 拼接所有block内容
        full_text = "\n".join(
            getattr(tb, 'content', str(tb)) for tb in text_blocks
        )
        return self.measure(full_text, font_size_pt, max_width_emu, max_height_emu)

    def _get_font(self, size_pt: float):
        """获取指定大小的字体对象"""
        size_pt = max(8.0, min(size_pt, 72.0))
        key = round(size_pt, 1)
        if key not in self._font_cache:
            try:
                from PIL import ImageFont
                if self.font_path:
                    self._font_cache[key] = ImageFont.truetype(
                        self.font_path, size=size_pt
                    )
                else:
                    self._font_cache[key] = ImageFont.load_default()
            except ImportError:
                raise
        return self._font_cache[key]

    def _measure_line_width(self, line: str, font) -> float:
        """测量单行文本的渲染宽度（像素）"""
        try:
            bbox = font.getbbox(line)
            return bbox[2] - bbox[0]
        except AttributeError:
            try:
                return font.getlength(line)
            except AttributeError:
                # 最后的fallback
                return len(line) * 10

    def _estimate_wrap_lines(self, line: str, font, max_width_px: float) -> int:
        """估算一行文本换行后占用的行数"""
        try:
            line_width = self._measure_line_width(line, font)
            return max(1, int(line_width / max_width_px) + 1)
        except Exception:
            return max(1, len(line) // 20 + 1)

    @staticmethod
    def _estimate(
        text: str, font_size_pt: float, max_width_emu: int, max_height_emu: int
    ) -> MeasuredText:
        """PIL不可用时的纯估算"""
        # 中文字符约等于字号宽，英文约0.5字号宽
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_count = len(text) - cjk_count
        char_width_emu = int(font_size_pt * EMU_PER_PT)
        total_width_emu = cjk_count * char_width_emu + ascii_count * char_width_emu // 2

        lines = max(1, total_width_emu // max(max_width_emu, 1) + text.count('\n'))
        height_emu = int(lines * font_size_pt * 1.2 * EMU_PER_PT)

        overflows = max_height_emu > 0 and height_emu > max_height_emu

        return MeasuredText(
            width_emu=min(total_width_emu, max_width_emu),
            height_emu=height_emu,
            line_count=lines,
            overflows=overflows,
            suggested_font_pt=font_size_pt,
        )
