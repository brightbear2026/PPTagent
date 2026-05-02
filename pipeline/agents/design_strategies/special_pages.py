"""
SpecialPageBuilder — fixed HTML templates for structural slides (cover, agenda, section divider).

Extracted from HTMLDesignAgent so the agent class stays focused on orchestration.
"""

from __future__ import annotations

from typing import Dict, List


class SpecialPageBuilder:
    """Generates fixed HTML for structural slides that bypass LLM entirely."""

    @staticmethod
    def cover_slide_html(
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
        task: Dict,
    ) -> str:
        """Fixed cover/title slide template — dark primary background with centered title."""
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        title = slide_data.get("title", "") or task.get("title", "演示文稿")
        subtitle = slide_data.get("takeaway_message", "") or ""
        # Use text_blocks first block as subtitle if takeaway_message is empty
        if not subtitle:
            blocks = slide_data.get("text_blocks", [])
            if blocks:
                b = blocks[0]
                subtitle = b.get("content", "") if isinstance(b, dict) else str(b)

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:1280px; height:720px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:{primary}; position:relative;">

<!-- Left accent stripe -->
<div style="position:absolute; top:0; left:0; width:11px; height:720px; background-color:{accent};"></div>

<!-- Bottom accent band -->
<div style="position:absolute; bottom:0; left:0; width:1280px; height:6px; background-color:{accent};"></div>

<!-- Title -->
<h1 style="position:absolute; left:107px; top:200px; width:1067px; height:187px; font-size:36px; color:#FFFFFF; font-weight:bold; line-height:1.4;">{title}</h1>

<!-- Subtitle / root claim -->
<p style="position:absolute; left:107px; top:413px; width:960px; height:80px; font-size:16px; color:#AECCE0;">{subtitle}</p>

<!-- Divider line -->
<div style="position:absolute; left:107px; top:387px; width:800px; height:2px; background-color:{accent};"></div>

</body>
</html>"""

    @staticmethod
    def agenda_slide_html(
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
        task: Dict,
        sections: List[str],
    ) -> str:
        """Fixed agenda/TOC slide — left panel with 目录 title, right panel with numbered chapters."""
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        text_color = theme_colors.get("text", "#2D3436")

        items_html = ""
        for i, sec in enumerate(sections[:8]):
            top_px = 50 + i * 77
            items_html += (
                f'<div style="position:absolute; left:373px; top:{top_px}px;'
                f' width:43px; height:43px; background-color:{primary};">'
                f'<p style="color:#FFFFFF; font-size:13px; font-weight:bold;'
                f' text-align:center; margin:8px 0;">{i + 1:02d}</p>'
                f'</div>'
                f'<p style="position:absolute; left:436px; top:{top_px + 8}px;'
                f' width:747px; font-size:14px; color:{text_color}; font-weight:500;">{sec}</p>'
                f'<div style="position:absolute; left:373px; top:{top_px + 67}px;'
                f' width:853px; height:1px; background-color:#E8E8E8;"></div>'
            )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:1280px; height:720px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative;">

<div style="position:absolute; top:0; left:0; width:320px; height:720px; background-color:{primary};"></div>
<div style="position:absolute; top:0; left:320px; width:960px; height:4px; background-color:{accent};"></div>
<h1 style="position:absolute; left:0; top:277px; width:320px; font-size:24px; color:#FFFFFF; font-weight:bold; text-align:center; letter-spacing:6px;">目录</h1>
<div style="position:absolute; left:128px; top:349px; width:64px; height:3px; background-color:{accent};"></div>
{items_html}
<div style="position:absolute; bottom:0; left:320px; width:960px; height:20px; background-color:{primary};"></div>

</body>
</html>"""

    @staticmethod
    def section_divider_html(
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
        task: Dict,
        sec_num: int,
    ) -> str:
        """Fixed section-divider slide — dark primary background with chapter number and title."""
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        sec_name = slide_data.get("title") or slide_data.get("takeaway_message", "")
        cn_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        cn_num = cn_nums[sec_num - 1] if 1 <= sec_num <= len(cn_nums) else str(sec_num)

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:1280px; height:720px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:{primary}; position:relative;">

<div style="position:absolute; top:0; left:0; width:11px; height:720px; background-color:{accent};"></div>
<div style="position:absolute; bottom:0; left:0; width:1280px; height:6px; background-color:{accent};"></div>
<p style="position:absolute; left:107px; top:224px; font-size:13px; color:{accent}; font-weight:600; letter-spacing:4px;">第 {cn_num} 章</p>
<div style="position:absolute; left:107px; top:267px; width:640px; height:2px; background-color:{accent};"></div>
<h1 style="position:absolute; left:107px; top:291px; width:1067px; font-size:30px; color:#FFFFFF; font-weight:bold; line-height:1.5;">{sec_name}</h1>

</body>
</html>"""
