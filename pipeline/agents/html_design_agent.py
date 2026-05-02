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
<body style="width: 1280px; height: 720px;">  (16:9, 96 DPI)

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

## 颜色 semantic（必须遵守）
accent 色（橙 #FF6B35）仅用于：① takeaway 标题 ② 关键数字/指标值 ③ 1个 callout。
禁止将 accent 用于：背景色、装饰条、次要文本、普通 bullet、分隔线。
普通文本用 #333333/#666666，标题用 primary（深蓝 #003D6E）。
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

        # Pre-extract section info for agenda/section_divider templates
        self._sections_list: List[Dict] = [
            {"title": sd.get("title") or sd.get("takeaway_message", ""),
             "summary": sd.get("section_summary", "")}
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

            # Inject section name into footer (skip cover/section_divider/agenda)
            if sd.get("slide_type") not in ("title", "section_divider", "agenda"):
                html = self._inject_section_footer(html, sd, idx, total)

            # H6 density guard (after footer injection, before write)
            html = self._enforce_density_guard(html, sd, theme_colors, total)

            html_path = os.path.join(html_dir, f"slide_{idx:02d}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            chart_data = {"slide_type": sd.get("slide_type", "content")}
            if sd.get("chart_suggestion"):
                chart_data["chart_spec"] = sd["chart_suggestion"]
                chart_data["theme"] = None

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
                intermediate_path, placeholders, chart_slides_data, output_path,
                render_errors=render_result.get("errors", []),
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

        rendered_count = render_result.get("rendered_count", render_result.get("slide_count", total))
        errors = render_result.get("errors", [])
        if errors:
            for err in errors:
                logger.error(
                    "Slide %s (%s) render error: %s",
                    err.get("slide_index", "?"), err.get("file", "?"), err.get("error", "unknown"),
                )
        dropped = total - rendered_count
        if dropped > 0:
            logger.error(
                "HTMLDesignAgent: %d of %d slides dropped during Node render",
                dropped, total,
            )

        result = {
            "output_file": final_path,
            "slide_count": rendered_count,
            "chart_count": chart_count,
            "diagram_count": sum(1 for sd in slides_data if sd.get("diagram_spec")),
            "render_errors": errors,
        }

        logger.info(
            "HTMLDesignAgent: %d/%d slides rendered, %d charts, %d errors",
            rendered_count, total, chart_count, len(errors),
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
            sec_titles = [s.get("title", s) if isinstance(s, dict) else s for s in sections]
            sec_num = (sec_titles.index(sec_name) + 1) if sec_name in sec_titles else 1
            return self.special_pages.section_divider_html(slide_index, slide_data, theme_colors, total_slides, task, sec_num)

        if slide_data.get("slide_type") == "agenda":
            return self.special_pages.agenda_slide_html(slide_index, slide_data, theme_colors, total_slides, task, self._sections_list)

        if self.llm is None:
            html = self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)
            from pipeline.layer6_output.html_dup_check import detect_dup_prefix as _dp
            if _dp(html):
                logger.warning("Slide %d: no-LLM fallback dup-prefix — minimal safe HTML", slide_index)
                return _minimal_safe_html(slide_data, theme_colors, slide_index + 1, total_slides)
            return html

        # Registry-typed layouts bypass LLM entirely (system-assembled HTML).
        from pipeline.layouts import LayoutRegistry
        hint = slide_data.get("layout_hint", "")
        if hint in LayoutRegistry.names():
            try:
                layout = LayoutRegistry.get(hint)
                content = layout.from_slide_data(slide_data)
                html = layout.build_html(content, theme_colors, slide_index + 1, total_slides)
                # Dup-prefix guard: registry HTML is deterministic — degrade if bad
                from pipeline.layer6_output.html_dup_check import detect_dup_prefix as _dp
                dup_err = _dp(html)
                if dup_err:
                    logger.error(
                        "Slide %d: registry layout '%s' produced dup-prefix — degrading to text_only: %s",
                        slide_index, hint, dup_err,
                    )
                    return self.fallback.heuristic_template_html(
                        slide_index, slide_data, theme_colors, total_slides,
                    )
                return html
            except Exception as e:
                logger.warning(
                    "Slide %d: registry layout '%s' failed, falling through to LLM: %s",
                    slide_index, hint, e,
                )

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

            # Enforce chart_focus when primary_visual=chart
            pv = slide_data.get("primary_visual", "text_only") or "text_only"
            if pv == "chart" and template_id != "chart_focus":
                logger.warning(
                    "Slide %d: LLM picked %s but primary_visual=chart, forcing chart_focus",
                    slide_index, template_id,
                )
                template_id = "chart_focus"
                slots = {
                    "title": slide_data.get("takeaway_message", ""),
                    "annotations": slots.get("annotations", []),
                }

            from pipeline.layer6_output.slide_templates import render_template
            # Inject source_note from slide data for chart/data slides
            if "source_note" not in slots:
                source = slide_data.get("source_note", "") or slide_data.get("data_source", "")
                if source:
                    slots["source_note"] = source
            html = render_template(
                template_id=template_id,
                slots=slots,
                theme_colors=theme_colors,
                page_number=slide_index + 1,
                total_slides=total_slides,
            )

            # Dup-prefix check: detect if LLM filled same text into two slots
            from pipeline.layer6_output.html_dup_check import detect_dup_prefix
            dup_err = detect_dup_prefix(html)
            if dup_err:
                logger.warning(
                    "Slide %d: dup-prefix detected, retrying once: %s",
                    slide_index, dup_err,
                )
                retry_messages = [
                    ChatMessage(role="system", content=_get_slot_system_prompt()),
                    ChatMessage(role="user", content=user_msg),
                    ChatMessage(role="assistant", content=raw),
                    ChatMessage(role="user", content=dup_err),
                ]
                retry_resp = self.llm.chat(messages=retry_messages, temperature=0.2, max_tokens=800)
                if retry_resp.success:
                    retry_raw = (retry_resp.content or "").strip()
                    if retry_raw.startswith("```"):
                        retry_raw = retry_raw.split("\n", 1)[-1]
                    if retry_raw.endswith("```"):
                        retry_raw = retry_raw.rsplit("```", 1)[0]
                    try:
                        rm = re.search(r"\{[\s\S]*\}", retry_raw)
                        if rm:
                            rdata = json.loads(rm.group(0))
                            rtid = rdata.get("template_id", "content_bullets")
                            rslots = rdata.get("slots", {})
                            # Re-enforce chart_focus
                            if pv == "chart" and rtid != "chart_focus":
                                rtid = "chart_focus"
                                rslots = {"title": slide_data.get("takeaway_message", ""), "annotations": []}
                            retry_html = render_template(
                                template_id=rtid, slots=rslots,
                                theme_colors=theme_colors,
                                page_number=slide_index + 1, total_slides=total_slides,
                            )
                            if not detect_dup_prefix(retry_html):
                                return retry_html
                            logger.warning("Slide %d: retry still has dup-prefix, using fallback", slide_index)
                    except Exception:
                        logger.warning("Slide %d: retry parse failed, using fallback", slide_index)

                # Fallback to heuristic template
                return self.fallback.heuristic_template_html(
                    slide_index, slide_data, theme_colors, total_slides,
                )

            return html

        except Exception as e:
            if isinstance(e, (TypeError, AttributeError, NameError)):
                logger.error("Slide %d: code error in slot generation: %s", slide_index, e, exc_info=True)
                raise
            logger.warning("Slot generation failed for slide %d: %s, using heuristic fallback", slide_index, e)
            # Even in fallback, enforce chart_focus if primary_visual=chart
            pv = slide_data.get("primary_visual", "text_only") or "text_only"
            if pv == "chart":
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
            html = self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)
            # Dup-prefix check even on heuristic fallback — degrade if detected
            from pipeline.layer6_output.html_dup_check import detect_dup_prefix as _dp
            dup = _dp(html)
            if dup:
                logger.warning(
                    "Slide %d: heuristic fallback dup-prefix — returning minimal safe HTML: %s",
                    slide_index, dup,
                )
                return _minimal_safe_html(slide_data, theme_colors, slide_index + 1, total_slides)
            return html

    def _enforce_density_guard(
        self, html: str, slide_data: Dict, theme_colors: Dict, total_slides: int,
    ) -> str:
        """H6: reject sparse layouts and placeholder chars on content slides."""
        slide_type = slide_data.get("slide_type", "content")
        if slide_type in ("title", "agenda", "section_divider"):
            return html

        from pipeline.layer6_output.html_density_check import (
            detect_sparse, detect_placeholder_char,
        )

        err = detect_sparse(html, min_visible=8)
        if err:
            logger.warning(
                "Slide %d density violation: %s. Forcing dense fallback.",
                slide_data.get("page_number"), err,
            )
            return _force_dense_fallback(slide_data, theme_colors, total_slides)

        err = detect_placeholder_char(html)
        if err:
            logger.error(
                "Slide %d placeholder char violation: %s.",
                slide_data.get("page_number"), err,
            )
            return _force_dense_fallback(slide_data, theme_colors, total_slides)

        return html

    @staticmethod
    def _inject_section_footer(html: str, slide_data: Dict, slide_index: int, total_slides: int) -> str:
        """Replace the default footer with section_name + page_number format."""
        import html as _html_module
        section = slide_data.get("section", "")
        pn = slide_index + 1
        # Find the section name from the current slide's section field,
        # strip any "第X章" prefix for display
        from pipeline.agents.plan_agent import _strip_chapter_prefix
        clean_section = _strip_chapter_prefix(section)
        section_display = _html_module.escape(clean_section) if clean_section else ""
        page_display = _html_module.escape(f"P{pn} / {total_slides}")

        # Build new footer content: section name (left) + page number (right)
        new_footer = (
            f'<p style="font-size:9px; color:#FFFFFF; margin:4px 24px; '
            f'display:flex; justify-content:space-between;">'
            f'<span>{section_display}</span>'
            f'<span>{page_display}</span>'
            f'</p>'
        )

        # Replace the existing footer <p> tag inside the footer <div>
        # Pattern 1: standard registry/slot footer <p>
        old_footer_pattern = (
            f'<p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">'
            f'第 {_html_module.escape(str(pn))} 页 / 共 {_html_module.escape(str(total_slides))} 页</p>'
        )
        if old_footer_pattern in html:
            html = html.replace(old_footer_pattern, new_footer)
        else:
            # Pattern 2: any standard footer <p> (registry layouts use "PX / Y")
            replaced = re.sub(
                r'<p style="font-size:9px; color:#FFFFFF; margin:4px 24px;">.*?</p>',
                new_footer,
                html, count=1, flags=re.DOTALL,
            )
            if replaced != html:
                html = replaced
            else:
                # Pattern 3: hero/special template footer (different style)
                pn_escaped = _html_module.escape(str(pn))
                total_escaped = _html_module.escape(str(total_slides))
                hero_pattern = f'>P{pn_escaped} / {total_escaped}</p>'
                if hero_pattern in html:
                    html = html.replace(
                        f'P{pn_escaped} / {total_escaped}',
                        f'{section_display} | P{pn_escaped} / {total_escaped}' if section_display else f'P{pn_escaped} / {total_escaped}',
                    )
        return html

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

        # Dup-prefix check on final output (after all fixes applied)
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix as _dp_check

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
                "- body 必须是 1280x720px，不能有溢出\n"
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
                    dup = _dp_check(fixed_html)
                    if dup:
                        logger.warning("Slide %d: LLM fix has dup-prefix: %s", slide_index, dup)
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
        html = self.fallback.heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)
        dup = _dp_check(html)
        if dup:
            logger.warning("Slide %d: heuristic fallback has dup-prefix: %s", slide_index, dup)
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
                slide_data["primary_visual"] = content.get("primary_visual", "") or (
                    item.get("primary_visual", "") if isinstance(item, dict) else getattr(item, "primary_visual", "")
                )
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
                slide_data["primary_visual"] = getattr(content, "primary_visual", "") or (
                    item.get("primary_visual", "") if isinstance(item, dict) else getattr(item, "primary_visual", "")
                )
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

        # Defensive assert: upstream ContentSlideSchema guarantees mutual exclusion
        for sd in slides_data:
            pv = sd.get("primary_visual", "text_only") or "text_only"
            visual_count = sum(1 for k in ("chart_suggestion", "diagram_spec", "visual_block")
                               if sd.get(k) is not None)
            if pv in ("chart", "diagram", "visual_block") and visual_count != 1:
                logger.warning("Slide %s: schema guarantee violated — pv=%s, %d visual fields",
                               sd.get("page_number"), pv, visual_count)
            elif pv == "text_only" and visual_count > 0:
                logger.warning("Slide %s: text_only but %d visual fields (upstream leak?)",
                               sd.get("page_number"), visual_count)

        return slides_data


def _minimal_safe_html(slide_data: Dict, theme_colors: Dict, page_number: int, total_slides: int) -> str:
    """Last-resort HTML when all layout paths produce dup-prefix. Content-only, no visual slots."""
    import html as _html
    title = _html.escape(slide_data.get("takeaway_message", slide_data.get("title", "")))
    bg = theme_colors.get("bg", "#FFFFFF")
    text = theme_colors.get("text", "#1A1A1A")
    muted = theme_colors.get("muted", "#666666")
    primary = theme_colors.get("primary", "#003D6E")
    paragraphs = ""
    for tb in (slide_data.get("text_blocks") or []):
        content = _html.escape(tb.get("content", tb.get("text", "")))
        level = tb.get("level", 0)
        if level == 0:
            paragraphs += f'<p style="font-size:13pt;color:{text};margin:4px 0">{content}</p>'
        else:
            paragraphs += f'<p style="font-size:11pt;color:{muted};margin:2px 0 2px 16px">{content}</p>'
    footer = f'<div style="position:absolute;bottom:8px;right:24px;font-size:8pt;color:{muted}">P{page_number}/{total_slides}</div>'
    return (
        f'<div style="width:1280px;height:720px;background:{bg};padding:32px 53px;box-sizing:border-box;'
        f'font-family:Microsoft YaHei,sans-serif;position:relative">'
        f'<h2 style="font-size:18pt;color:{primary};margin:0 0 16px 0">{title}</h2>'
        f'{paragraphs}'
        f'{footer}'
        f'</div>'
    )


def _force_dense_fallback(slide_data: Dict, theme_colors: Dict, total_slides: int) -> str:
    """Force dense content layout to guarantee ≥8 visible elements."""
    import html as _html
    pn = slide_data.get("page_number", 1)
    title = _html.escape(slide_data.get("takeaway_message", slide_data.get("title", "")))
    primary = theme_colors.get("primary", "#003D6E")
    accent = theme_colors.get("accent", "#FF6B35")
    bg = theme_colors.get("bg", "#FFFFFF")
    text = theme_colors.get("text", "#2D3436")
    muted = theme_colors.get("muted", "#636E72")

    # Collect all text content into grid items
    blocks = slide_data.get("text_blocks", [])
    items_html = ""
    for i, b in enumerate(blocks[:8]):
        c = _html.escape(b.get("content", b.get("text", "")))
        if not c:
            continue
        col = i % 3
        row = i // 3
        x = 53 + col * 400
        y = 80 + row * 107
        items_html += (
            f'<div style="position:absolute;left:{x}px;top:{y}px;width:373px;'
            f'background:{bg};border-left:3px solid {accent};padding:6px 10px;">'
            f'<p style="font-size:12px;color:{text};margin:0;line-height:1.4;">{c}</p>'
            f'</div>\n'
        )

    # If still sparse, pad with takeaway as subtitle
    if not items_html:
        items_html = f'<p style="font-size:13px;color:{text};">{title}</p>'

    return (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head>\n'
        f'<body style="width:1280px;height:720px;font-family:Microsoft YaHei,Arial,sans-serif;'
        f'background-color:#FFFFFF;position:relative;overflow:hidden;">\n'
        f'<div style="position:absolute;top:0;left:0;width:1280px;height:6px;background-color:{accent};"></div>\n'
        f'<div style="position:absolute;bottom:0;left:0;width:1280px;height:24px;background-color:{primary};">\n'
        f'  <p style="font-size:9px;color:#FFFFFF;margin:4px 24px;">P{pn} / {total_slides}</p>\n'
        f'</div>\n'
        f'<div style="position:absolute;left:32px;top:28px;width:5px;height:36px;background-color:{primary};"></div>\n'
        f'<h2 style="position:absolute;left:53px;top:22px;width:1173px;font-size:16px;color:{primary};'
        f'font-weight:bold;line-height:1.35;overflow:hidden;height:44px;">{title}</h2>\n'
        f'{items_html}'
        '</body></html>'
    )
