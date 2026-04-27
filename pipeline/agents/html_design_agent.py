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
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from llm_client.base import ChatMessage

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

_AUTO_ICONS = ["🎯", "💡", "📊", "⚙️", "🔍", "🚀", "🌟", "📈", "🛡️", "🤝"]
_COMPARISON_KEYWORDS = ("vs", " v.s.", "对比", "相比", "相较", "vs.", "对照", "差异", "区别")
_NUMERIC_TOKENS = ("%", "％", "亿", "万", "千", "倍", "x", "X", "k", "K", "M", "B")

# System prompt for the slot-based template approach (primary path)
def _load_slot_prompt() -> str:
    from .base import load_prompt
    return load_prompt("html_design_slot", "v1")

_SLOT_SYSTEM_PROMPT: str = ""  # lazy-loaded on first use


def _get_slot_system_prompt() -> str:
    global _SLOT_SYSTEM_PROMPT
    if not _SLOT_SYSTEM_PROMPT:
        _SLOT_SYSTEM_PROMPT = _load_slot_prompt()
    return _SLOT_SYSTEM_PROMPT

# Legacy free-HTML system prompt (kept for fallback inspect-loop)
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
- layout_hint: 布局建议（如果有，优先遵循此建议进行排版）

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

        # Pre-extract section names for agenda/section_divider templates
        self._sections_list: List[str] = [
            sd.get("title") or sd.get("takeaway_message", "")
            for sd in slides_data if sd.get("slide_type") == "section_divider"
        ]

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

        # Structural slides use fixed templates — bypass LLM entirely.
        if slide_data.get("slide_type") == "title":
            return self._cover_slide_html(slide_index, slide_data, theme_colors, total_slides, task)

        if slide_data.get("slide_type") == "section_divider":
            sec_name = slide_data.get("title") or slide_data.get("takeaway_message", "")
            sections = getattr(self, "_sections_list", [])
            sec_num = (sections.index(sec_name) + 1) if sec_name in sections else 1
            return self._section_divider_html(slide_index, slide_data, theme_colors, total_slides, task, sec_num)

        if slide_data.get("slide_type") == "agenda":
            return self._agenda_slide_html(slide_index, slide_data, theme_colors, total_slides, task)

        if self.llm is None:
            return self._heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

        user_msg = json.dumps({
            "slide_number": slide_index + 1,
            **slide_data,
        }, ensure_ascii=False)

        from llm_client.base import ChatMessage

        try:
            response = self.llm.chat(
                messages=[
                    ChatMessage(role="system", content=_get_slot_system_prompt()),
                    ChatMessage(role="user", content=user_msg),
                ],
                temperature=0.2,
                max_tokens=800,
            )

            if not response.success:
                raise RuntimeError(f"LLM error: {response.error}")
            raw = (response.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]

            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                raise ValueError("LLM returned no JSON")
            data = json.loads(m.group(0))
            template_id = data.get("template_id", "content_bullets")
            slots = data.get("slots", {})

            # Enforce chart_focus when chart_suggestion has data
            if self._chart_has_data(slide_data) and template_id != "chart_focus":
                logger.warning(
                    "Slide %d: LLM picked %s but chart_suggestion exists, forcing chart_focus",
                    slide_index, template_id,
                )
                template_id = "chart_focus"
                slots = {
                    "title": slide_data.get("takeaway_message", ""),
                    "annotations": slots.get("annotations", []),
                }

            from pipeline.layer6_output.slide_templates import render_template
            return render_template(
                template_id=template_id,
                slots=slots,
                theme_colors=theme_colors,
                page_number=slide_index + 1,
                total_slides=total_slides,
            )

        except Exception as e:
            if isinstance(e, (TypeError, AttributeError, NameError)):
                logger.error("Slide %d: code error in slot generation: %s", slide_index, e, exc_info=True)
                raise
            logger.warning("Slot generation failed for slide %d: %s, using heuristic fallback", slide_index, e)
            # Even in fallback, enforce chart_focus if chart data exists
            if self._chart_has_data(slide_data):
                logger.info("Slide %d: heuristic fallback with chart data, forcing chart_focus", slide_index)
                from pipeline.layer6_output.slide_templates import render_template
                return render_template(
                    template_id="chart_focus",
                    slots={
                        "title": slide_data.get("takeaway_message", ""),
                        "annotations": [],
                    },
                    theme_colors=theme_colors,
                    page_number=slide_index + 1,
                    total_slides=total_slides,
                )
            return self._heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

    def _inspect_and_fix(
        self, html, slide_index, slide_data, theme_colors, total_slides, task, linter,
    ) -> str:
        """Pre-validate HTML with CSS lint + real Node.js dry-run render. Regenerate on failure."""

        # Collect errors from both lint and real render
        all_errors = []

        # 1. CSS lint check (fast, no browser)
        pw = slide_data.get("page_weight", "")
        lint_errors = linter.validate(html, page_weight=pw)
        all_errors.extend(lint_errors)

        # 2. Real Node.js dry-run render check
        render_ok = True
        render_errors = []
        try:
            from pipeline.layer6_output.node_bridge import NodeRenderBridge
            bridge = NodeRenderBridge()
            # Write html to a temp file for the validator
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                suffix=".html", mode="w", delete=False, encoding="utf-8",
            )
            tmp.write(html)
            tmp.close()
            try:
                result = bridge.validate_single_slide(tmp.name)
                render_ok = result.get("ok", False)
                render_errors = result.get("errors", [])
                all_errors.extend(render_errors)
            finally:
                os.unlink(tmp.name)
        except Exception as e:
            logger.warning("Slide %d: Node validate unavailable (%s), skipping render check", slide_index, e)

        if not all_errors:
            return html

        logger.warning(
            "Slide %d: inspect errors (lint=%d, render=%d): %s",
            slide_index, len(lint_errors), len(render_errors),
            all_errors[:5],
        )

        # 3. If LLM available, try one fix pass
        if self.llm:
            fix_prompt = (
                f"你刚才生成的第{slide_index + 1}页 HTML 存在以下问题：\n"
                + "\n".join(f"- {e}" for e in all_errors)
                + "\n\n请修正这些问题并重新输出完整的 HTML 文档。只输出 HTML。\n"
                "注意约束：\n"
                "- body 必须是 960x540px，不能有溢出\n"
                "- 不要使用 <svg>、<iframe>、<video>、<canvas> 标签\n"
                "- P/H1-H6/UL/OL/LI 标签不能有 background/border/box-shadow\n"
                "- DIV 不能有 background-image\n"
                "- 所有文字必须放在 P/H1-H6/UL/OL/LI 标签内，DIV 不能包含裸文字\n"
            )

            try:
                response = self.llm.chat(
                    messages=[
                        ChatMessage(role="system", content=self._build_system_prompt(theme_colors)),
                        ChatMessage(role="user", content=json.dumps(slide_data, ensure_ascii=False)),
                        ChatMessage(role="assistant", content=html),
                        ChatMessage(role="user", content=fix_prompt),
                    ],
                    temperature=0.2,
                    max_tokens=4000,
                )

                fixed_html = (response.content if hasattr(response, "content") and response.content else str(response) or "").strip()
                if fixed_html.startswith("```"):
                    fixed_html = fixed_html.split("\n", 1)[-1]
                if fixed_html.endswith("```"):
                    fixed_html = fixed_html.rsplit("```", 1)[0]

                # Re-validate the fix
                fixed_html, _ = linter.fix(fixed_html)
                remaining_lint = linter.validate(fixed_html, page_weight=pw)

                # Re-run Node validation on fix
                remaining_render = []
                try:
                    tmp2 = tempfile.NamedTemporaryFile(
                        suffix=".html", mode="w", delete=False, encoding="utf-8",
                    )
                    tmp2.write(fixed_html)
                    tmp2.close()
                    try:
                        r2 = bridge.validate_single_slide(tmp2.name)
                        if not r2.get("ok", False):
                            remaining_render = r2.get("errors", [])
                    finally:
                        os.unlink(tmp2.name)
                except Exception:
                    pass  # Node unavailable, accept lint-only result

                remaining = remaining_lint + remaining_render
                if len(remaining) < len(all_errors):
                    logger.info(
                        "Slide %d: fix reduced errors %d→%d",
                        slide_index, len(all_errors), len(remaining),
                    )
                    # Preserve chart placeholder if original had one but fix removed it
                    if '<div class="placeholder"' in html and '<div class="placeholder"' not in fixed_html:
                        logger.warning("Slide %d: LLM fix removed chart placeholder, restoring", slide_index)
                        # Re-inject the original placeholder into fixed_html before </body>
                        import re as _re
                        orig_ph = _re.search(r'<div class="placeholder"[^>]*>.*?</div>', html, _re.DOTALL)
                        if orig_ph:
                            fixed_html = fixed_html.replace('</body>', orig_ph.group(0) + '</body>')
                    return fixed_html
                else:
                    logger.warning("Slide %d: LLM fix didn't help (%d→%d), using heuristic fallback",
                                   slide_index, len(all_errors), len(remaining))
            except Exception as e:
                if isinstance(e, (TypeError, AttributeError, NameError)):
                    logger.error("Slide %d: code error in inspect-loop: %s", slide_index, e, exc_info=True)
                    raise
                logger.warning("Slide %d inspect-loop LLM retry failed: %s", slide_index, e)

        # 4. Fix failed or no LLM — use heuristic template fallback
        logger.info("Slide %d: falling back to heuristic template", slide_index)
        return self._heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

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

    def _cover_slide_html(
        self,
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
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:{primary}; position:relative;">

<!-- Left accent stripe -->
<div style="position:absolute; top:0; left:0; width:8px; height:540px; background-color:{accent};"></div>

<!-- Bottom accent band -->
<div style="position:absolute; bottom:0; left:0; width:960px; height:6px; background-color:{accent};"></div>

<!-- Title -->
<h1 style="position:absolute; left:80px; top:150px; width:800px; height:140px; font-size:36px; color:#FFFFFF; font-weight:bold; line-height:1.4;">{title}</h1>

<!-- Subtitle / root claim -->
<p style="position:absolute; left:80px; top:310px; width:720px; height:60px; font-size:16px; color:#AECCE0;">{subtitle}</p>

<!-- Divider line -->
<div style="position:absolute; left:80px; top:290px; width:600px; height:2px; background-color:{accent};"></div>

</body>
</html>"""

    def _agenda_slide_html(
        self,
        slide_index: int,
        slide_data: Dict,
        theme_colors: Dict[str, str],
        total_slides: int,
        task: Dict,
    ) -> str:
        """Fixed agenda/TOC slide — left panel with 目录 title, right panel with numbered chapters."""
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        text_color = theme_colors.get("text", "#2D3436")
        sections = getattr(self, "_sections_list", [])

        items_html = ""
        for i, sec in enumerate(sections[:8]):
            top_px = 50 + i * 58
            items_html += (
                f'<div style="position:absolute; left:280px; top:{top_px}px;'
                f' width:32px; height:32px; background-color:{primary};">'
                f'<p style="color:#FFFFFF; font-size:13px; font-weight:bold;'
                f' text-align:center; margin:6px 0;">{i + 1:02d}</p>'
                f'</div>'
                f'<p style="position:absolute; left:328px; top:{top_px + 6}px;'
                f' width:560px; font-size:14px; color:{text_color}; font-weight:500;">{sec}</p>'
                f'<div style="position:absolute; left:280px; top:{top_px + 50}px;'
                f' width:640px; height:1px; background-color:#E8E8E8;"></div>'
            )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:#FFFFFF; position:relative;">

<div style="position:absolute; top:0; left:0; width:240px; height:540px; background-color:{primary};"></div>
<div style="position:absolute; top:0; left:240px; width:720px; height:4px; background-color:{accent};"></div>
<h1 style="position:absolute; left:0; top:208px; width:240px; font-size:24px; color:#FFFFFF; font-weight:bold; text-align:center; letter-spacing:6px;">目录</h1>
<div style="position:absolute; left:96px; top:262px; width:48px; height:3px; background-color:{accent};"></div>
{items_html}
<div style="position:absolute; bottom:0; left:240px; width:720px; height:20px; background-color:{primary};"></div>

</body>
</html>"""

    def _section_divider_html(
        self,
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
<body style="width:960px; height:540px; font-family:'Microsoft YaHei',Arial,sans-serif; background-color:{primary}; position:relative;">

<div style="position:absolute; top:0; left:0; width:8px; height:540px; background-color:{accent};"></div>
<div style="position:absolute; bottom:0; left:0; width:960px; height:6px; background-color:{accent};"></div>
<p style="position:absolute; left:80px; top:168px; font-size:13px; color:{accent}; font-weight:600; letter-spacing:4px;">第 {cn_num} 章</p>
<div style="position:absolute; left:80px; top:200px; width:480px; height:2px; background-color:{accent};"></div>
<h1 style="position:absolute; left:80px; top:218px; width:800px; font-size:30px; color:#FFFFFF; font-weight:bold; line-height:1.5;">{sec_name}</h1>

</body>
</html>"""

    # ------------------------------------------------------------------ #
    # Heuristic template picker — pure code, no LLM
    # ------------------------------------------------------------------ #

    @staticmethod
    def _chart_has_data(slide_data: Dict) -> bool:
        """Check whether chart_suggestion contains real data rows."""
        chart = slide_data.get("chart_suggestion") or {}
        if isinstance(chart, dict):
            series = chart.get("series") or chart.get("data")
            if isinstance(series, list) and len(series) > 0:
                return True
            labels = chart.get("labels") or chart.get("categories")
            if isinstance(labels, list) and len(labels) > 0:
                return True
        return False

    @staticmethod
    def _looks_like_comparison(title: str, blocks: List[Dict]) -> bool:
        """Detect comparison intent from title or block content."""
        text = title.lower()
        for block in blocks[:4]:
            text += " " + (block.get("content", "") if isinstance(block, dict) else str(block)).lower()
        for kw in _COMPARISON_KEYWORDS:
            if kw.lower() in text:
                return True
        return False

    @staticmethod
    def _split_comparison(blocks: List[Dict]) -> Tuple[List[str], List[str]]:
        """Split text blocks into two groups at a comparison keyword boundary."""
        left, right = [], []
        flipped = False
        for block in blocks:
            content = block.get("content", "") if isinstance(block, dict) else str(block)
            if not flipped:
                for kw in _COMPARISON_KEYWORDS:
                    if kw in content:
                        flipped = True
                        break
                if not flipped:
                    left.append(content)
            else:
                right.append(content)
        # If no keyword found, split in half
        if not right and len(blocks) >= 4:
            mid = len(blocks) // 2
            left = [b.get("content", "") if isinstance(b, dict) else str(b) for b in blocks[:mid]]
            right = [b.get("content", "") if isinstance(b, dict) else str(b) for b in blocks[mid:]]
        return left[:4], right[:4]

    @staticmethod
    def _infer_column_label(items: List[str], fallback: str) -> str:
        """Try to extract a short label from the first item, else use fallback."""
        if not items:
            return fallback
        first = items[0]
        # Take first 12 chars as label
        if len(first) <= 12:
            return first.rstrip("：: ")
        return first[:12].rstrip("：: ") + "…"

    @staticmethod
    def _has_numeric(text: str) -> bool:
        """Check if text contains numeric indicators."""
        for tok in _NUMERIC_TOKENS:
            if tok in text:
                return True
        # Also check for plain digits
        import re as _re
        return bool(_re.search(r"\d+\.?\d*", text))

    @staticmethod
    def _extract_metric(block: Dict) -> Optional[Dict[str, str]]:
        """Try to extract {label, value, unit, note} from a text block."""
        content = block.get("content", "") if isinstance(block, dict) else str(block)
        if not content:
            return None
        # Find the first numeric token
        import re as _re
        m = _re.search(r"([\d,]+\.?\d*)\s*(%|％|亿|万|倍|元|美元|k|K|M|B)?", content)
        if not m:
            return None
        value = m.group(1)
        unit = m.group(2) or ""
        # Label: text before the number (up to 15 chars)
        prefix = content[:m.start()].strip().rstrip("：:，,、是为达约超近")
        label = prefix[-15:] if len(prefix) > 15 else prefix
        if not label:
            label = "指标"
        # Note: text after the number
        rest = content[m.end():].strip().lstrip("，,。.、 ")
        note = rest[:60] if rest else ""
        return {"label": label, "value": value, "unit": unit, "note": note}

    # layout_hint → template_id mapping
    _LAYOUT_HINT_MAP: Dict[str, str] = {
        "parallel_points": "content_bullets",
        "comparison": "content_two_column",
        "metrics": "content_key_metrics",
        "chart_focus": "chart_focus",
        "quote_emphasis": "quote_highlight",
        "framework_grid": "icon_grid",
        "narrative": "timeline_horizontal",
    }

    def _pick_template_and_slots(
        self,
        slide_data: Dict,
        body_blocks: List[Dict],
        bold_blocks: List[Dict],
        title: str,
    ) -> Tuple[str, Dict]:
        """Decision tree → (template_id, slots)."""

        # 0. hero pages → force hero_splash template
        if slide_data.get("page_weight") == "hero":
            return self._build_slots_for_template(
                "hero_splash", slide_data, body_blocks, bold_blocks, title
            )

        # 1. layout_hint short-circuit: if set, trust it directly
        hint = slide_data.get("layout_hint", "")
        if hint and hint in self._LAYOUT_HINT_MAP:
            forced_template = self._LAYOUT_HINT_MAP[hint]
            logger.info("layout_hint=%s → forcing template=%s", hint, forced_template)
            # Build slots for the forced template
            return self._build_slots_for_template(
                forced_template, slide_data, body_blocks, bold_blocks, title
            )

        # 1. Chart with real data → chart_focus
        if self._chart_has_data(slide_data):
            annotations = []
            for b in body_blocks[:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    annotations.append(c[:80])
            return "chart_focus", {
                "title": title,
                "annotations": annotations or ["关键趋势"],
            }

        # 1b. Diagram with structure → map diagram_type to template
        diagram = slide_data.get("diagram_spec")
        if isinstance(diagram, dict) and diagram.get("diagram_type"):
            dt = diagram["diagram_type"]
            _DIAGRAM_TEMPLATE_MAP = {
                "process_flow": "timeline_horizontal",
                "architecture": "architecture_stack",
                "framework": "quadrant_matrix",
                "relationship": "role_columns",
                # IT diagram types
                "tech_architecture": "tech_stack_layers",
                "component_topology": "component_network",
                "data_flow": "data_pipeline",
                "tech_stack_matrix": "tech_comparison",
            }
            tmpl = _DIAGRAM_TEMPLATE_MAP.get(dt, "framework_grid")
            logger.info("diagram_type=%s → template=%s", dt, tmpl)
            return self._build_slots_for_template(tmpl, slide_data, body_blocks, bold_blocks, title)

        # 1c. Visual block with data → map type to template
        vblock = slide_data.get("visual_block")
        if isinstance(vblock, dict) and vblock.get("type"):
            vb_type = vblock["type"]
            items = vblock.get("items", [])
            if vb_type in ("kpi_cards", "stat_highlight") and items:
                metrics = []
                for item in items[:4]:
                    metrics.append({
                        "label": item.get("title", item.get("description", "")),
                        "value": item.get("value", ""),
                        "unit": "",
                        "note": item.get("description", item.get("trend", "")),
                    })
                logger.info("visual_block type=%s → content_key_metrics (%d items)", vb_type, len(metrics))
                return "content_key_metrics", {"title": title, "metrics": metrics}
            elif vb_type == "icon_text_grid" and items:
                logger.info("visual_block type=icon_text_grid → icon_grid (%d items)", len(items))
                return "icon_grid", {"title": title, "items": items}
            elif vb_type == "step_cards" and items:
                logger.info("visual_block type=step_cards → timeline_horizontal (%d items)", len(items))
                phases = []
                for idx, item in enumerate(items[:6]):
                    phases.append({
                        "label": item.get("label", f"步骤{idx+1}"),
                        "title": item.get("title", item.get("name", ""))[:30],
                        "desc": item.get("description", item.get("desc", ""))[:60],
                    })
                return "timeline_horizontal", {"title": title, "phases": phases}
            elif vb_type == "comparison_columns" and items:
                logger.info("visual_block type=comparison_columns → content_two_column")
                return self._build_slots_for_template("content_two_column", slide_data, body_blocks, bold_blocks, title)

        n_blocks = len(body_blocks)

        # 2. Comparison intent → content_two_column
        if self._looks_like_comparison(title, body_blocks) and n_blocks >= 2:
            left, right = self._split_comparison(body_blocks)
            return "content_two_column", {
                "title": title,
                "left_label": self._infer_column_label(left, "方案A"),
                "left_bullets": left,
                "right_label": self._infer_column_label(right, "方案B"),
                "right_bullets": right,
            }

        # 3. Numeric-heavy blocks → content_key_metrics
        numeric_blocks = [b for b in body_blocks if self._has_numeric(
            b.get("content", "") if isinstance(b, dict) else str(b)
        )]
        if len(numeric_blocks) >= 2:
            metrics = []
            for b in numeric_blocks[:4]:
                m = self._extract_metric(b)
                if m:
                    metrics.append(m)
            if len(metrics) >= 2:
                sub_bullets = []
                for b in body_blocks:
                    if b not in numeric_blocks:
                        c = b.get("content", "") if isinstance(b, dict) else str(b)
                        if c:
                            sub_bullets.append(c[:60])
                return "content_key_metrics", {
                    "title": title,
                    "metrics": metrics,
                    "sub_bullets": sub_bullets[:3],
                }

        # 4. 3-6 short parallel blocks → icon_grid
        if 3 <= n_blocks <= 6:
            max_len = max(len(b.get("content", "") if isinstance(b, dict) else str(b)) for b in body_blocks)
            if max_len <= 60:
                items = []
                for idx, b in enumerate(body_blocks):
                    content = b.get("content", "") if isinstance(b, dict) else str(b)
                    icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                    if len(content) <= 15:
                        items.append({"icon": icon, "title": content, "desc": ""})
                    else:
                        mid = min(len(content), 20)
                        # Try to split at a punctuation
                        for sep in ["：", ":", "—", "-", "，", ","]:
                            pos = content.find(sep)
                            if 0 < pos < 40:
                                mid = pos
                                break
                        items.append({
                            "icon": icon,
                            "title": content[:mid].rstrip("：:—-，, "),
                            "desc": content[mid:].lstrip("：:—-，, ")[:60],
                        })
                return "icon_grid", {"title": title, "items": items}

        # 5. Everything else → content_bullets
        bullets = []
        for b in body_blocks[:8]:
            c = b.get("content", "") if isinstance(b, dict) else str(b)
            if c:
                bullets.append(c[:80])
        return "content_bullets", {
            "title": title,
            "bullets": bullets,
            "has_chart": bool(slide_data.get("chart_suggestion")),
        }

    def _build_slots_for_template(
        self,
        template_id: str,
        slide_data: Dict,
        body_blocks: List[Dict],
        bold_blocks: List[Dict],
        title: str,
    ) -> Tuple[str, Dict]:
        """Build minimal slots for a forced template_id (layout_hint path)."""
        if template_id == "chart_focus":
            annotations = []
            for b in body_blocks[:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    annotations.append(c[:80])
            return template_id, {"title": title, "annotations": annotations or ["关键趋势"]}

        if template_id == "content_two_column":
            left, right = self._split_comparison(body_blocks)
            return template_id, {
                "title": title,
                "left_label": self._infer_column_label(left, "方案A"),
                "left_bullets": left,
                "right_label": self._infer_column_label(right, "方案B"),
                "right_bullets": right,
            }

        if template_id == "content_key_metrics":
            metrics = []
            for b in body_blocks[:4]:
                m = self._extract_metric(b)
                if m:
                    metrics.append(m)
            if not metrics:
                metrics = [{"label": "指标", "value": "-", "unit": "", "note": ""}]
            return template_id, {"title": title, "metrics": metrics}

        if template_id == "quote_highlight":
            quote = body_blocks[0].get("content", "")[:120] if body_blocks else title[:120]
            sub_bullets = []
            for b in body_blocks[1:6]:
                c = b.get("content", "") if isinstance(b, dict) else str(b)
                if c:
                    sub_bullets.append(c[:60])
            return template_id, {"title": title, "quote_text": quote, "sub_bullets": sub_bullets}

        if template_id == "icon_grid":
            items = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                icon = _AUTO_ICONS[idx % len(_AUTO_ICONS)]
                if len(content) <= 20:
                    items.append({"icon": icon, "title": content, "desc": ""})
                else:
                    mid = min(len(content), 30)
                    for sep in ["：", ":", "—", "-"]:
                        pos = content.find(sep)
                        if 0 < pos < 50:
                            mid = pos
                            break
                    items.append({
                        "icon": icon,
                        "title": content[:mid].rstrip("：:—-，, "),
                        "desc": content[mid:].lstrip("：:—-，, ")[:60],
                    })
            return template_id, {"title": title, "items": items or [{"icon": "📊", "title": title, "desc": ""}]}

        if template_id == "timeline_horizontal":
            phases = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                phases.append({"label": f"阶段{idx+1}", "title": content[:30], "desc": content[:60]})
            return template_id, {"title": title, "phases": phases or [{"label": "阶段1", "title": title, "desc": ""}]}

        if template_id == "architecture_stack":
            layers = []
            for idx, b in enumerate(body_blocks[:6]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                layers.append({"name": content[:20], "desc": content[:60]})
            return template_id, {"title": title, "layers": layers or [{"name": "Layer 1", "desc": ""}]}

        if template_id == "quadrant_matrix":
            cells = []
            for idx, b in enumerate(body_blocks[:4]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                cells.append({"label": f"象限{idx+1}", "items": [content[:50]]})
            while len(cells) < 4:
                cells.append({"label": "", "items": []})
            return template_id, {"title": title, "x_label": "维度A", "y_label": "维度B", "cells": cells}

        if template_id == "role_columns":
            roles = []
            for idx, b in enumerate(body_blocks[:4]):
                content = b.get("content", "") if isinstance(b, dict) else str(b)
                roles.append({"name": content[:20], "subtitle": "", "bullets": [content[:50]]})
            return template_id, {"title": title, "roles": roles or [{"name": "角色1", "subtitle": "", "bullets": []}]}

        if template_id == "hero_splash":
            # Extract the most impactful number from text blocks
            import re
            all_text = " ".join(
                b.get("content", "") if isinstance(b, dict) else str(b)
                for b in body_blocks
            )
            # Find numbers with units (亿, 万, %, etc.)
            num_match = re.search(r'(\d+\.?\d*)\s*(亿|万|%|亿元|万元|个|家|人|美元)', all_text)
            big_number = ""
            number_caption = ""
            if num_match:
                big_number = num_match.group(1) + num_match.group(2)
                # Try to find context before the number
                prefix = all_text[:num_match.start()].rstrip("，。、：: ")
                # Find last meaningful phrase
                for sep in ["，", "。", "、", "：", "："]:
                    idx = prefix.rfind(sep)
                    if idx >= 0:
                        prefix = prefix[idx+1:]
                        break
                number_caption = prefix[:30] if prefix else ""
            if not big_number:
                big_number = title[:10] if title else "—"
            # Subtitle: second text block or takeaway
            subtitle = ""
            if len(body_blocks) > 1:
                subtitle = (body_blocks[1].get("content", "") if isinstance(body_blocks[1], dict) else str(body_blocks[1]))[:40]
            if not subtitle:
                subtitle = slide_data.get("takeaway_message", "")[:40]
            return template_id, {
                "headline": slide_data.get("takeaway_message", title),
                "big_number": big_number,
                "number_caption": number_caption,
                "subtitle": subtitle,
            }

        # ── IT diagram slot builders (prefer diagram_spec data, fallback body_blocks) ──

        if template_id == "tech_stack_layers":
            diagram = slide_data.get("diagram_spec", {})
            layers_raw = diagram.get("layers", [])
            if layers_raw:
                layers = []
                for l in layers_raw[:7]:
                    items = l.get("items", [])
                    desc = ", ".join(str(i) for i in items) if isinstance(items, list) else str(items)
                    layer = {"name": str(l.get("label", ""))[:20], "desc": desc[:60]}
                    if l.get("color"):
                        layer["color"] = l["color"]
                    layers.append(layer)
            else:
                layers = [{"name": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20], "desc": ""}
                          for b in body_blocks[:7]]
            return template_id, {"title": title, "layers": layers or [{"name": "Layer 1", "desc": ""}]}

        if template_id == "component_network":
            diagram = slide_data.get("diagram_spec", {})
            groups_raw = diagram.get("groups", [])
            if groups_raw:
                groups = []
                for g in groups_raw[:6]:
                    comps = g.get("components", [])
                    groups.append({"name": str(g.get("name", ""))[:20],
                                   "components": [str(c) for c in comps[:6]]})
            else:
                groups = [{"name": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20],
                           "components": []} for b in body_blocks[:6]]
            connections = diagram.get("connections", []) if isinstance(diagram, dict) else []
            return template_id, {"title": title, "groups": groups, "connections": connections}

        if template_id == "data_pipeline":
            diagram = slide_data.get("diagram_spec", {})
            stages_raw = diagram.get("stages", [])
            if stages_raw:
                stages = []
                for s in stages_raw[:8]:
                    stages.append({"label": str(s.get("label", ""))[:20],
                                   "type": str(s.get("type", "")),
                                   "desc": str(s.get("desc", ""))[:30]})
            else:
                stages = [{"label": b.get("content", "")[:20] if isinstance(b, dict) else str(b)[:20],
                           "type": "", "desc": ""} for b in body_blocks[:8]]
            flows = diagram.get("flows", []) if isinstance(diagram, dict) else []
            return template_id, {"title": title, "stages": stages, "flows": flows}

        if template_id == "tech_comparison":
            diagram = slide_data.get("diagram_spec", {})
            cats_raw = diagram.get("categories", [])
            if cats_raw:
                categories = []
                for c in cats_raw[:6]:
                    opts = c.get("options", [])
                    categories.append({"name": str(c.get("name", ""))[:15],
                                       "options": opts})
            else:
                categories = [{"name": b.get("content", "")[:15] if isinstance(b, dict) else str(b)[:15],
                               "options": []} for b in body_blocks[:6]]
            return template_id, {"title": title, "categories": categories}

        # Default: content_bullets
        bullets = []
        for b in body_blocks[:8]:
            c = b.get("content", "") if isinstance(b, dict) else str(b)
            if c:
                bullets.append(c[:80])
        return template_id, {
            "title": title,
            "bullets": bullets,
            "has_chart": bool(slide_data.get("chart_suggestion")),
        }

    def _heuristic_template_html(
        self,
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

            template_id, slots = self._pick_template_and_slots(
                slide_data, body_blocks, bold_blocks, title
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
            return self._fallback_html(slide_index, slide_data, theme_colors, total_slides)

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
                # layout_hint: prefer ContentAgent's pass-through, fall back to outline item
                lh = content.get("layout_hint", "") or (
                    item.get("layout_hint", "") if isinstance(item, dict) else getattr(item, "layout_hint", "")
                )
                if lh:
                    slide_data["layout_hint"] = lh
                # page_weight: prefer ContentAgent's pass-through, fall back to outline item
                pw = content.get("page_weight", "") or (
                    item.get("page_weight", "") if isinstance(item, dict) else getattr(item, "page_weight", "")
                )
                if pw:
                    slide_data["page_weight"] = pw
            elif hasattr(content, "text_blocks"):
                # Convert dataclass objects to plain dicts for template/JSON consumption
                from dataclasses import asdict as _asdict

                def _to_dict(obj):
                    if obj is None:
                        return None
                    if isinstance(obj, dict):
                        return obj
                    if hasattr(obj, "to_dict"):
                        return obj.to_dict()
                    if hasattr(obj, "__dataclass_fields__"):
                        return _asdict(obj)
                    return obj

                raw_blocks = content.text_blocks
                slide_data["text_blocks"] = [
                    {"content": b.content, "is_bold": b.is_bold, "level": b.level}
                    if hasattr(b, "content") else b
                    for b in raw_blocks
                ]
                slide_data["chart_suggestion"] = _to_dict(getattr(content, "chart_suggestion", None))
                slide_data["diagram_spec"] = _to_dict(getattr(content, "diagram_spec", None))
                slide_data["visual_block"] = _to_dict(getattr(content, "visual_block", None))
                # layout_hint & page_weight: prefer ContentAgent pass-through, fall back to outline item
                lh = getattr(content, "layout_hint", "") or (
                    item.get("layout_hint", "") if isinstance(item, dict) else getattr(item, "layout_hint", "")
                )
                if lh:
                    slide_data["layout_hint"] = lh
                pw = getattr(content, "page_weight", "") or (
                    item.get("page_weight", "") if isinstance(item, dict) else getattr(item, "page_weight", "")
                )
                if pw:
                    slide_data["page_weight"] = pw

            slides_data.append(slide_data)

        return slides_data
