"""
FallbackBuilder — heuristic and last-resort HTML generation.

Extracted from HTMLDesignAgent so the agent class stays focused on orchestration.
"""

from __future__ import annotations

import logging
from typing import Dict

from pipeline.agents.design_strategies.templates import TemplatePicker

logger = logging.getLogger(__name__)

# Fixed chrome template injected into every slide
_CHROME_TEMPLATE = """
<!-- Chrome: top accent bar -->
<div style="position:absolute; top:0; left:0; width:960px; height:6px; background-color:{accent};"></div>
<!-- Chrome: bottom footer -->
<div style="position:absolute; bottom:0; left:0; width:960px; height:24px; background-color:{primary};">
  <p style="color:#FFFFFF; font-size:9px; margin:4px 24px;">{footer}</p>
</div>
"""


class FallbackBuilder:
    """Generates HTML when LLM is unavailable or fails."""

    @staticmethod
    def heuristic_template_html(
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
    ) -> str:
        """Select template purely from slide_data structure — no LLM needed."""
        try:
            title = slide_data.get("takeaway_message", "")
            text_blocks = slide_data.get("text_blocks", [])

            # Separate bold / body blocks
            bold_blocks = []
            body_blocks = []
            for b in text_blocks:
                if not isinstance(b, dict):
                    body_blocks.append({"content": str(b)})
                    continue
                if b.get("is_bold"):
                    bold_blocks.append(b)
                else:
                    body_blocks.append(b)

            template_id, slots = TemplatePicker.pick(
                slide_data, body_blocks, bold_blocks, title,
            )

            from pipeline.layer6_output.slide_templates import render_template
            html = render_template(
                template_id=template_id,
                slots=slots,
                theme_colors=theme_colors,
                page_number=slide_index + 1,
                total_slides=total_slides,
            )
            logger.info("Slide %d: heuristic picked template=%s", slide_index, template_id)
            return html
        except Exception as e:
            logger.warning("Heuristic template failed for slide %d: %s, using raw fallback", slide_index, e)
            return FallbackBuilder.fallback_html(slide_index, slide_data, theme_colors, total_slides)

    @staticmethod
    def fallback_html(
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
    ) -> str:
        """Fallback HTML when LLM is unavailable — simple but functional."""
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#C9A84C")
        text_color = theme_colors.get("text", "#2D3436")

        takeaway = slide_data.get("takeaway_message", "")
        text_blocks = slide_data.get("text_blocks", [])
        has_chart = bool(slide_data.get("chart_suggestion"))

        # Build text content
        body_parts = []
        for block in text_blocks[:10]:
            content = block.get("content", "") if isinstance(block, dict) else str(block)
            is_bold = block.get("is_bold", False) if isinstance(block, dict) else False
            if is_bold:
                body_parts.append(f'<p style="font-size:14px; font-weight:bold; color:{primary}; margin-bottom:8px;">{content}</p>')
            else:
                body_parts.append(f'<p style="font-size:12px; color:{text_color}; margin-bottom:6px;">{content}</p>')

        text_html = "\n".join(body_parts)

        # Chart placeholder
        chart_placeholder = ""
        if has_chart:
            chart_placeholder = '<div class="placeholder" id="chart-0" style="position:absolute; left:520px; top:80px; width:400px; height:280px;"></div>'

        # Content width
        content_w = "460px" if has_chart else "860px"

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft Yahei',Arial,sans-serif; background-color:#FFFFFF; position:relative;">

{_CHROME_TEMPLATE.format(accent=accent, primary=primary, footer=f'第 {slide_index+1} 页 / 共 {total_slides} 页')}

<!-- Takeaway bar -->
<div style="position:absolute; left:24px; top:36px; width:4px; height:36px; background-color:{primary};"></div>

<!-- Takeaway message -->
<h2 style="position:absolute; left:40px; top:28px; width:{content_w}; height:32px; font-size:16px; color:{primary}; font-weight:bold;">{takeaway}</h2>

<!-- Text content -->
<div style="position:absolute; left:40px; top:70px; width:{content_w}; height:400px;">
{text_html}
</div>

{chart_placeholder}

</body>
</html>"""
