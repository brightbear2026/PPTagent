"""VisualPlannerAgent — per-slide visual structure planning.

Runs between content and design stages. Uses LLM to decide the best layout
for each content slide and fills the layout's content schema. Outputs a
VisualPlanResult that HTMLDesignAgent consumes directly.

Does NOT generate HTML — only structured layout decisions.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from llm_client.base import ChatMessage
from models.visual_plan_schema import VisualPlan, VisualPlanResult
from pipeline.layouts import LayoutRegistry

logger = logging.getLogger(__name__)

MAX_CONCURRENT = int(os.environ.get("VISUAL_PLAN_MAX_CONCURRENT", "4"))
MAX_RETRIES = 3


class VisualPlannerAgent:

    def __init__(self, llm_client):
        self.llm = llm_client

    def run(
        self,
        content_slides: List[Dict],
        outline: Dict,
        analysis: Dict,
        theme: Dict,
        deck_context: Dict,
        report_progress=None,
    ) -> Dict:
        """Plan visual layout for each content slide.

        Returns a dict matching VisualPlanResult, persisted to pipeline_stages.
        """
        content_only = [s for s in content_slides if s.get("slide_type") not in ("title", "agenda", "section_divider")]
        total = len(content_only)
        logger.info("VisualPlannerAgent: planning %d content slides", total)

        # Load system prompt
        system_prompt = self._load_prompt()

        # Build deck-level context
        all_layouts = sorted(LayoutRegistry.names())
        neighbor_plans: Dict[int, str] = {}  # page_number -> layout_id
        results: Dict[int, Dict] = {}
        fallback_pages: List[int] = []

        def _plan_one(idx: int, slide: Dict) -> tuple:
            page = slide.get("page_number", idx + 1)
            slide_idx = idx

            # Build exclude list from neighbors (no 3+ consecutive same layout)
            exclude = self._neighbor_excludes(neighbor_plans, page, content_only)

            for attempt in range(MAX_RETRIES):
                try:
                    user_msg = self._build_user_msg(slide, deck_context, all_layouts, exclude, neighbor_plans)
                    messages = [
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content=user_msg),
                    ]

                    if report_progress:
                        pct = int(70 + (idx / max(total, 1)) * 8)
                        report_progress(pct, f"正在规划第 {page} 页视觉布局...")

                    response = self.llm.chat(
                        messages=messages,
                        temperature=0.4,
                        max_tokens=2000,
                    )
                    if not response.success:
                        raise RuntimeError(f"LLM call failed: {response.error}")

                    raw = response.content or ""
                    plan_dict = self._parse_json(raw)
                    if not plan_dict:
                        raise ValueError("Failed to parse JSON from LLM output")

                    # Validate
                    plan = VisualPlan.model_validate(plan_dict)
                    neighbor_plans[page] = plan.layout_id
                    return (slide_idx, page, plan.model_dump(), None)

                except Exception as e:
                    logger.warning(
                        "VisualPlanner slide %d attempt %d/%d failed: %s",
                        page, attempt + 1, MAX_RETRIES, str(e)[:200],
                    )
                    if attempt == MAX_RETRIES - 1:
                        # Fallback: use layout_hint
                        fallback_layout = slide.get("layout_hint", "parallel_points")
                        if fallback_layout not in LayoutRegistry.names():
                            fallback_layout = "parallel_points"
                        layout = LayoutRegistry.get(fallback_layout)
                        try:
                            content_obj = layout.from_slide_data(slide)
                            fallback_plan = {
                                "page_number": page,
                                "layout_id": fallback_layout,
                                "layout_content": content_obj.model_dump(),
                                "emphasis": None,
                                "rationale": f"Fallback: visual planner failed ({str(e)[:80]})",
                                "confidence": 0.3,
                            }
                            VisualPlan.model_validate(fallback_plan)
                        except Exception:
                            fallback_plan = {
                                "page_number": page,
                                "layout_id": "parallel_points",
                                "layout_content": {"title": slide.get("takeaway_message", ""), "bullets": ["内容加载中"] * 4},
                                "rationale": "Emergency fallback",
                                "confidence": 0.1,
                            }
                        return (slide_idx, page, fallback_plan, "fallback")

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            futures = {
                pool.submit(_plan_one, idx, slide): idx
                for idx, slide in enumerate(content_only)
            }
            for future in as_completed(futures):
                try:
                    idx, page, plan_dict, fallback_flag = future.result()
                    results[page] = plan_dict
                    if fallback_flag:
                        fallback_pages.append(page)
                except Exception as e:
                    logger.error("VisualPlanner page failed completely: %s", e)

        # Enforce diversity post-process
        results = self._enforce_diversity(results, content_only, system_prompt)

        # Sort by page number
        sorted_plans = [results[p] for p in sorted(results.keys()) if p in results]

        result = VisualPlanResult(
            plans=[VisualPlan.model_validate(p) for p in sorted_plans],
            fallback_pages=sorted(fallback_pages),
        )

        logger.info(
            "VisualPlannerAgent: %d plans, %d fallbacks",
            len(result.plans), len(result.fallback_pages),
        )

        return result.model_dump()

    def _build_user_msg(
        self,
        slide: Dict,
        deck_context: Dict,
        all_layouts: List[str],
        exclude_layouts: List[str],
        neighbor_plans: Dict[int, str],
    ) -> str:
        page = slide.get("page_number", 0)
        takeaway = slide.get("takeaway_message", "")
        section = slide.get("section", "")
        hint = slide.get("layout_hint", "")
        text_blocks = slide.get("text_blocks", [])
        visual_block = slide.get("visual_block") or {}
        chart_suggestion = slide.get("chart_suggestion") or {}

        # Text blocks summary
        blocks_text = ""
        for b in text_blocks[:8]:
            c = b.get("content", b.get("text", ""))
            if c:
                blocks_text += f"  - {c[:100]}\n"

        # Neighbor context
        neighbors_text = ""
        for pn, lid in sorted(neighbor_plans.items()):
            if abs(pn - page) <= 2:
                neighbors_text += f"  P{pn}: {lid}\n"

        exclude_text = ""
        if exclude_layouts:
            exclude_text = f"\n⚠️ 禁止使用以下 layout: {', '.join(exclude_layouts)}\n"

        return f"""请为第 {page} 页选择最合适的 layout 并填充内容。

## 当前页面信息
- 页码: P{page}
- 标题: {takeaway}
- 章节: {section}
- 原始 layout_hint: {hint or '无'}
- primary_visual: {slide.get('primary_visual', 'text_only')}

### 文本内容
{blocks_text or '（无）'}

### visual_block
{json.dumps(visual_block, ensure_ascii=False) if visual_block else '无'}

### chart_suggestion
{json.dumps(chart_suggestion, ensure_ascii=False)[:200] if chart_suggestion else '无'}

## 上下文
- 场景: {deck_context.get('scenario', '通用')}
- 总页数: {deck_context.get('total_slides', '?')}
- 框架: {deck_context.get('framework', '未知')[:80]}
- 可选 layout: {', '.join(all_layouts)}

### 相邻页面已选 layout
{neighbors_text or '（首页，暂无邻居）'}
{exclude_text}

请输出 JSON 格式的 VisualPlan。"""

    def _neighbor_excludes(
        self,
        neighbor_plans: Dict[int, str],
        current_page: int,
        slides: List[Dict],
    ) -> List[str]:
        """Return layouts that would create 3+ consecutive same layout."""
        excludes = []
        prev1 = neighbor_plans.get(current_page - 1)
        prev2 = neighbor_plans.get(current_page - 2)
        if prev1 and prev2 and prev1 == prev2:
            excludes.append(prev1)
        return excludes

    def _enforce_diversity(
        self,
        results: Dict[int, Dict],
        slides: List[Dict],
        system_prompt: str,
    ) -> Dict[int, Dict]:
        """Re-plan any page that creates 3+ consecutive same layout."""
        pages = sorted(results.keys())
        for i in range(2, len(pages)):
            p1, p2, p3 = pages[i - 2], pages[i - 1], pages[i]
            lid1 = results[p1].get("layout_id", "")
            lid2 = results[p2].get("layout_id", "")
            lid3 = results[p3].get("layout_id", "")
            if lid1 == lid2 == lid3 and lid1:
                logger.info("Diversity enforcement: re-planning P%d (3 consecutive %s)", p3, lid1)
                # Simple rotation: pick a different SmartArt layout
                smartart = ["tech_architecture", "capability_matrix", "end_to_end_flow", "framework_grid", "comparison", "case_study", "solution_comparison", "metrics"]
                alternatives = [l for l in smartart if l != lid1 and l in LayoutRegistry.names()]
                if alternatives:
                    new_layout_id = alternatives[hash(p3) % len(alternatives)]
                    layout = LayoutRegistry.get(new_layout_id)
                    slide = slides[p3 - 1] if p3 - 1 < len(slides) else slides[0]
                    try:
                        content_obj = layout.from_slide_data(slide)
                        results[p3] = {
                            "page_number": p3,
                            "layout_id": new_layout_id,
                            "layout_content": content_obj.model_dump(),
                            "rationale": f"Diversity enforcement: replaced 3rd consecutive {lid1}",
                            "confidence": 0.6,
                        }
                    except Exception as e:
                        logger.warning("Diversity re-plan failed for P%d: %s", p3, e)
        return results

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict]:
        """Extract JSON from LLM output."""
        # Try fenced code block first
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw JSON
        m = re.search(r'\{[^{}]*"layout_id"[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        # Try full text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _load_prompt(self) -> str:
        from pipeline.agents.base import load_prompt
        return load_prompt("visual_planner", "v1")
