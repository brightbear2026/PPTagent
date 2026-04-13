"""
Chrome 装饰原语：把页面顶部色条 / 底部色带 / 侧边强调条 / 页脚底色等重复出现
的视觉元素抽象成可复用的小函数，避免在 _add_xxx_decorations 中重复硬编码。
所有坐标单位均为 EMU。
"""
from pptx.util import Emu
from pptx.dml.color import RGBColor


# python-pptx 的 RECTANGLE auto_shape_type
RECT = 1


def _solid_rect(slide, left: int, top: int, width: int, height: int, rgb: RGBColor):
    """添加无边框纯色矩形"""
    shape = slide.shapes.add_shape(RECT, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()
    return shape


def add_top_bar(slide, slide_width: int, color: RGBColor, thickness_emu: int = 36000):
    """页面顶部细色条"""
    return _solid_rect(slide, 0, 0, slide_width, thickness_emu, color)


def add_top_band(slide, slide_width: int, slide_height: int, color: RGBColor,
                 ratio: float = 0.08):
    """页面顶部宽色带（封面用）"""
    return _solid_rect(slide, 0, 0, slide_width, int(slide_height * ratio), color)


def add_bottom_band(slide, slide_width: int, slide_height: int, color: RGBColor,
                    ratio: float = 0.12):
    """页面底部宽色带（封面用）"""
    top = int(slide_height * (1 - ratio))
    return _solid_rect(slide, 0, top, slide_width, slide_height - top, color)


def add_accent_underline(slide, slide_width: int, slide_height: int, color: RGBColor,
                         y_ratio: float = 0.88, thickness_emu: int = 45720):
    """底部色带上沿的强调细线（封面用）"""
    return _solid_rect(slide, 0, int(slide_height * y_ratio), slide_width,
                       thickness_emu, color)


def add_left_accent_bar(slide, slide_height: int, color: RGBColor,
                        width_emu: int = 54864, top_emu: int = 36000,
                        height_ratio: float = 0.85):
    """内容页左侧强调竖条"""
    return _solid_rect(slide, 0, top_emu, width_emu,
                       int(slide_height * height_ratio), color)


def add_footer_panel(slide, slide_width: int, slide_height: int,
                     bg_rgb: RGBColor, ratio: float = 0.06):
    """底部页脚浅色背景"""
    top = int(slide_height * (1 - ratio))
    return _solid_rect(slide, 0, top, slide_width, slide_height - top, bg_rgb)


def add_left_panel(slide, slide_height: int, color: RGBColor, width_ratio: float):
    """左侧大色块（章节过渡页）"""
    return _solid_rect(slide, 0, 0, int(width_ratio), slide_height, color)
