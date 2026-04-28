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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from llm_client.base import ChatMessage
from pipeline.agents.design_strategies.templates import TemplatePicker
from pipeline.agents.design_strategies.special_pages import SpecialPageBuilder
from pipeline.agents.design_strategies.fallback import FallbackBuilder

logger = logging.getLogger(__name__)

MAX_CONCURRENT = int(os.environ.get("DESIGN_MAX_CONCURRENT", "4"))

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
        self.template_picker = TemplatePicker()
        self.special_pages = SpecialPageBuilder()
        self.fallback = FallbackBuilder()

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

        chart_slides_data = [{}] * len(slides_data)

        total = len(slides_data)

        def _design_one_slide(idx, sd):
            """Design a single slide (thread-safe). Returns (idx, html, chart_data)."""
            if report_progress:
                pct = int(70 + (idx / max(total, 1)) * 15)
                report_progress(pct, f"正在设计第 {idx+1}/{total} 页...")

            html = self._generate_slide_html(
                slide_index=idx,
                slide_data=sd,
                theme_colors=theme_colors,
                total_slides=total,
                task=task,
            )

            from pipeline.layer6_output.css_linter import CSSLinter
            linter = CSSLinter()
            html, warnings = linter.fix(html)
            if warnings:
                logger.info("Slide %d linter warnings: %s", idx, warnings)

            html = self._inspect_and_fix(
                html=html,
                slide_index=idx,
                slide_data=sd,
                theme_colors=theme_colors,
                total_slides=total,
                task=task,
                linter=linter,
            )

            html_path = os.path.join(html_dir, f"slide_{idx:02d}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            chart_data = {}
            if sd.get("chart_suggestion"):
                chart_data = {"chart_spec": sd["chart_suggestion"], "theme": None}

            return idx, html, chart_data

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            futures = {
                pool.submit(_design_one_slide, i, sd): i
                for i, sd in enumerate(slides_data)
            }
            for future in as_completed(futures):
                idx, html, chart_data = future.result()
                chart_slides_data[idx] = chart_data

        # Render all slides via Node.js
        from pipeline.layer6_output.node_bridge import get_bridge

        intermediate_path = os.path.join(tmp_dir, "intermediate.pptx")
        output_path = os.path.join(tmp_dir, "output.pptx")

        bridge = get_bridge()
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
            return self.special_pages.cover_slide_html(slide_index, slide_data, theme_colors, total_slides, task)

        if slide_data.get("slide_type") == "section_divider":
            sec_name = slide_data.get("title") or slide_data.get("takeaway_message", "")
            sections = getattr(self, "_sections_list", [])
            sec_num = (sections.index(sec_name) + 1) if sec_name in sections else 1
            return self.special_pages.section_divider_html(slide_index, slide_data, theme_colors, total_slides, task, sec_num)

        if slide_data.get("slide_type") == "agenda":
            return self.special_pages.agenda_slide_html(slide_index, slide_data, theme_colors, total_slides, task, self._sections_list)

        if self.llm is None:
            return self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

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
            if TemplatePicker._chart_has_data(slide_data) and template_id != "chart_focus":
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
            if TemplatePicker._chart_has_data(slide_data):
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
            return self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

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
            from pipeline.layer6_output.node_bridge import get_bridge
            bridge = get_bridge()
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
        return self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)

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
