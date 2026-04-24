"""
HTMLDesignAgent — HTML-first visual design + rendering

Replaces DesignAgent + RenderAgent for the HTML rendering path.
LLM generates HTML/CSS per slide → html2pptx.js renders to native PPTX elements.
Chart placeholders are filled by the existing ChartRenderer (python-pptx).

Output: {"output_file": str, "slide_count": int, "chart_count": int, ...}
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# System prompt for the LLM
_SYSTEM_PROMPT = """你是一位 PPT 视觉设计师。为每张幻灯片生成完整的 HTML 文档。

## 画布尺寸（必须严格遵守）
<body style="width: 960px; height: 540px;">  (16:9, 96 DPI)

## 内容区域
内容必须在 margin-top:20px, margin-bottom:34px, margin-left:48px, margin-right:48px 的范围内。
左侧 4px takeaway 竖条已由系统固定渲染，内容区从 left:48px 开始。

## CSS 白名单（必须遵守）
- 字体：只允许 "Microsoft YaHei", Arial, Verdana, Tahoma, Georgia, Impact
- background/border/box-shadow 只在 <div> 上用
- 禁止：linear-gradient, radial-gradient, inset box-shadow
- 禁止在 <p>/<h1>-<h6>/<ul>/<ol>/<li> 上用 background/border/box-shadow
- 文本必须包在语义标签内（<p>/<h1>-<h6>/<ul>/<ol>），禁止裸文本
- 禁止 <iframe>, <video>, <form>, <canvas>, <svg>

## 图表占位
如果 slide 包含图表数据，在内容区留一个：
<div class="placeholder" id="chart-0" style="position:absolute; left:Xpx; top:Ypx; width:Wpx; height:Hpx;"></div>

## 输入格式
每张 slide 接收 JSON 数据：
- slide_type: 页面类型
- takeaway_message: 核心信息（一句话）
- text_blocks: [{title, content, is_bold}] 文本内容
- chart_suggestion: {chart_type, title, data}（如果有，用 placeholder 占位）
- diagram_spec: 概念图规格（如果有，用 CSS flex/grid 渲染）
- visual_block: 视觉块规格（如果有，用 CSS 渲染）

## 输出格式
严格输出完整 HTML 文档，以 <!DOCTYPE html> 开头。
只输出 HTML，不要输出任何解释或 markdown 代码块标记。
"""


class HTMLDesignAgent:
    """
    HTML-first design + render agent.

    1. Receives content from ContentAgent
    2. Calls LLM to generate HTML/CSS per slide
    3. CSS linter auto-fixes violations
    4. html2pptx.js renders to native PPTX elements
    5. ChartRenderer injects native charts at placeholder positions
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def run(self, context: Dict[str, Any]) -> Dict:
        from models.slide_spec import (
            OutlineResult, ContentResult, AnalysisResult,
        )

        task = context.get("task", {})
        outline_data = context.get("outline", {})
        content_data = context.get("content", {})
        analysis_data = context.get("analysis", {})

        if not outline_data or not content_data:
            raise RuntimeError("缺少大纲或内容结果，无法构建PPT")

        outline = OutlineResult.from_dict(outline_data) if isinstance(outline_data, dict) else outline_data
        content = ContentResult.from_dict(content_data) if isinstance(content_data, dict) else content_data

        # Get theme colors
        theme_colors = self._get_theme_colors(analysis_data)
        report_progress = context.get("report_progress")

        # Build slides data
        outline_items = outline.items if hasattr(outline, 'items') else outline_data.get("items", [])
        content_slides = content.slides if hasattr(content, 'slides') else content_data.get("slides", [])

        slides_data = self._match_slides(outline_items, content_slides)

        # Create temp dir for HTML files
        tmp_dir = tempfile.mkdtemp(prefix="pptagent_html_")
        html_dir = os.path.join(tmp_dir, "slides")
        os.makedirs(html_dir, exist_ok=True)

        chart_slides_data = []

        total = len(slides_data)
        for i, sd in enumerate(slides_data):
            if report_progress:
                pct = int(70 + (i / max(total, 1)) * 15)
                report_progress(pct, f"正在设计第 {i+1}/{total} 页...")

            html = self._generate_slide_html(
                slide_index=i,
                slide_data=sd,
                theme_colors=theme_colors,
                total_slides=total,
                task=task,
            )

            # CSS linter
            from pipeline.layer6_output.css_linter import CSSLinter
            linter = CSSLinter()
            html, warnings = linter.fix(html)
            if warnings:
                logger.info("Slide %d linter warnings: %s", i, warnings)

            # Inspect loop: pre-validate, regenerate if needed (max 1 retry)
            html = self._inspect_and_fix(
                html=html,
                slide_index=i,
                slide_data=sd,
                theme_colors=theme_colors,
                total_slides=total,
                task=task,
                linter=linter,
            )

            html_path = os.path.join(html_dir, f"slide_{i:02d}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            # Collect chart data for this slide
            if sd.get("chart_suggestion"):
                chart_slides_data.append({
                    "chart_spec": sd["chart_suggestion"],
                    "theme": None,
                })
            else:
                chart_slides_data.append({})

        # Render all slides via Node.js
        from pipeline.layer6_output.node_bridge import NodeRenderBridge

        intermediate_path = os.path.join(tmp_dir, "intermediate.pptx")
        output_path = os.path.join(tmp_dir, "output.pptx")

        bridge = NodeRenderBridge()
        render_result = bridge.render_slides(html_dir, intermediate_path)

        # Inject charts
        placeholders = render_result.get("placeholders", [])
        chart_count = 0
        if placeholders:
            from pipeline.layer6_output.chart_renderer import ChartRenderer
            chart_renderer = ChartRenderer()
            chart_renderer.render_into_pptx(
                intermediate_path, placeholders, chart_slides_data, output_path
            )
            chart_count = sum(len(p.get("items", [])) for p in placeholders)
        else:
            # No charts, just rename
            import shutil
            shutil.copy2(intermediate_path, output_path)

        # Copy output to final location
        task_id = context.get("task_id", "unknown")
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        final_path = os.path.join(output_dir, f"{task_id}.pptx")
        import shutil
        shutil.copy2(output_path, final_path)

        slide_count = render_result.get("slide_count", total)
        errors = render_result.get("errors", [])

        result = {
            "output_file": final_path,
            "slide_count": slide_count,
            "chart_count": chart_count,
            "diagram_count": sum(1 for sd in slides_data if sd.get("diagram_spec")),
            "render_errors": errors,
        }

        logger.info(
            "HTMLDesignAgent: %d slides, %d charts, %d errors",
            slide_count, chart_count, len(errors),
        )

        return result

    def _generate_slide_html(
        self,
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
        task: Dict,
    ) -> str:
        """Generate HTML for a single slide via LLM."""

        if self.llm is None:
            return self._fallback_html(slide_index, slide_data, theme_colors, total_slides)

        # Build user message
        user_msg = json.dumps({
            "slide_number": slide_index + 1,
            "total_slides": total_slides,
            **slide_data,
        }, ensure_ascii=False, indent=2)

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self._build_system_prompt(theme_colors)},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            html = response.strip()
            # Strip markdown code block if present
            if html.startswith("```"):
                html = html.split("\n", 1)[-1]
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]

            if "<!DOCTYPE html>" not in html and "<html" not in html:
                html = f"<!DOCTYPE html>\n<html>\n{html}\n</html>"

            return html

        except Exception as e:
            logger.warning("LLM generation failed for slide %d: %s, using fallback", slide_index, e)
            return self._fallback_html(slide_index, slide_data, theme_colors, total_slides)

    def _inspect_and_fix(
        self, html, slide_index, slide_data, theme_colors, total_slides, task, linter,
    ) -> str:
        """Pre-validate HTML with a single-slide Node.js render. Regenerate on failure."""
        # Fast check: CSS linter validate (no Node.js needed)
        errors = linter.validate(html)
        if not errors:
            return html

        logger.warning("Slide %d validation errors: %s", slide_index, errors)

        if not self.llm:
            # No LLM to retry with, return as-is (html2pptx will skip or best-effort)
            return html

        # Retry: feed errors back to LLM
        fix_prompt = (
            f"你刚才生成的第{slide_index + 1}页 HTML 存在以下问题：\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\n请修正这些问题并重新输出完整的 HTML 文档。只输出 HTML。"
        )

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self._build_system_prompt(theme_colors)},
                    {"role": "user", "content": json.dumps(slide_data, ensure_ascii=False)},
                    {"role": "assistant", "content": html},
                    {"role": "user", "content": fix_prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
            )

            fixed_html = response.strip()
            if fixed_html.startswith("```"):
                fixed_html = fixed_html.split("\n", 1)[-1]
            if fixed_html.endswith("```"):
                fixed_html = fixed_html.rsplit("```", 1)[0]

            # Re-lint the fix
            fixed_html, fix_warnings = linter.fix(fixed_html)
            remaining = linter.validate(fixed_html)

            if len(remaining) < len(errors):
                logger.info("Slide %d: fix reduced errors %d→%d", slide_index, len(errors), len(remaining))
                return fixed_html
            else:
                logger.warning("Slide %d: fix didn't help, keeping original", slide_index)
                return html

        except Exception as e:
            logger.warning("Slide %d inspect-loop retry failed: %s", slide_index, e)
            return html

    def _build_system_prompt(self, theme_colors: Dict[str, str]) -> str:
        accent = theme_colors.get("accent", "#C9A84C")
        primary = theme_colors.get("primary", "#003D6E")
        bg = theme_colors.get("bg", "#EEF4FA")
        text = theme_colors.get("text", "#2D3436")
        muted = theme_colors.get("muted", "#8B9DAF")

        return _SYSTEM_PROMPT + f"""

## 主题色板
- primary: {primary}（标题、强调）
- accent: {accent}（装饰、高亮）
- bg: {bg}（卡片背景）
- text: {text}（正文）
- muted: {muted}（次要文字）

## Chrome 装饰（自动注入，不需要你生成）
系统会自动在每页添加：
- 顶部 {accent} 色装饰条（6px高）
- 底部 {primary} 色页脚（24px高，含页码）
- 左侧 takeaway 竖条（4px宽，{primary}色）
"""

    def _fallback_html(
        self,
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
        for block in text_blocks[:6]:
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

    @staticmethod
    def _get_theme_colors(analysis_data: Dict) -> Dict[str, str]:
        """Extract theme colors. Maps from ThemeRegistry or analysis strategy."""
        from pipeline.layer4_visual.theme_registry import ThemeRegistry

        # Map analysis-detected style to theme
        style_theme_map = {
            "consulting_formal": "consulting_formal",
            "tech_modern": "tech_modern",
            "business_minimalist": "business_minimalist",
            "finance_stable": "finance_stable",
            "creative_vibrant": "creative_vibrant",
        }

        theme_id = "consulting_formal"  # default
        if analysis_data:
            strategy = analysis_data.get("strategy", {})
            style = strategy.get("visual_style", "")
            theme_id = style_theme_map.get(style, "consulting_formal")

        registry = ThemeRegistry()
        theme = registry.get_theme(theme_id)

        return {
            "primary": theme.colors.get("primary", "#003D6E"),
            "secondary": theme.colors.get("secondary", "#005A9E"),
            "accent": theme.colors.get("accent", "#FF6B35"),
            "text": theme.colors.get("text_dark", "#2D3436"),
            "muted": theme.colors.get("text_light", "#636E72"),
            "bg": "#EEF4FA",
            "border": "#C8D8E8",
            "theme_id": theme_id,
            "font_title": theme.fonts.get("title", "Arial"),
            "font_body": theme.fonts.get("body", "Calibri"),
        }

    @staticmethod
    def _match_slides(outline_items: list, content_slides: list) -> list:
        """Match outline items with content slides by page_number."""
        slides_data = []
        content_by_page = {}
        for cs in content_slides:
            pn = cs.get("page_number", 0) if isinstance(cs, dict) else getattr(cs, "page_number", 0)
            content_by_page[pn] = cs

        for i, item in enumerate(outline_items):
            pn = item.get("page_number", i + 1) if isinstance(item, dict) else getattr(item, "page_number", i + 1)
            content = content_by_page.get(pn, {})

            slide_data = {
                "page_number": pn,
                "slide_type": item.get("slide_type", "content") if isinstance(item, dict) else getattr(item, "slide_type", "content"),
                "takeaway_message": item.get("takeaway_message", "") if isinstance(item, dict) else getattr(item, "takeaway_message", ""),
                "title": item.get("title", "") if isinstance(item, dict) else getattr(item, "title", ""),
            }

            if isinstance(content, dict):
                slide_data["text_blocks"] = content.get("text_blocks", [])
                slide_data["chart_suggestion"] = content.get("chart_suggestion")
                slide_data["diagram_spec"] = content.get("diagram_spec")
                slide_data["visual_block"] = content.get("visual_block")
            elif hasattr(content, "text_blocks"):
                slide_data["text_blocks"] = content.text_blocks
                slide_data["chart_suggestion"] = getattr(content, "chart_suggestion", None)
                slide_data["diagram_spec"] = getattr(content, "diagram_spec", None)
                slide_data["visual_block"] = getattr(content, "visual_block", None)

            slides_data.append(slide_data)

        return slides_data
