"""
ContentAgent — per-slide 并行内容生成
每个大纲页面独立调用 LLM，最多 MAX_CONCURRENT 并发。

优势：
- 单页 ≤1800 token 输出，finish_reason=length 几乎不触发
- 单页失败只影响该页，不影响其他页面
- _generate_one_slide 可直接复用于 /rerun-page，消除重复代码
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .base import ReActAgent, Tool, ValidationResult
from llm_client.base import ChatMessage

logger = logging.getLogger(__name__)


class ContentAgent(ReActAgent):
    """
    内容填充 Agent — per-slide 并行架构。

    每个 PPT 页面独立调用 LLM，MAX_CONCURRENT 并发上限。
    消除批次 JSON 截断风险；单页失败不影响其他页面。
    """

    MAX_CONCURRENT = 4
    max_iterations = 3
    max_validation_retries = 2
    temperature = 0.6
    max_tokens = 1800  # 单页输出，不触发 finish_reason=length

    def __init__(self, llm_client):
        super().__init__(llm_client)
        self._context: Dict[str, Any] = {}
        self._page_contents: Dict[int, Dict] = {}
        self._lock = threading.Lock()

    @property
    def system_prompt(self) -> str:
        return """你是专业PPT内容填充师。为指定的单个PPT页面生成内容。

直接输出单个页面的 JSON 对象，放在 ```json ... ``` 代码块中。不要说废话，直接输出 JSON。

格式：
{"page_number":1,"text_blocks":[{"type":"heading","text":"标题"},{"type":"bullet","text":"要点","level":1}],"chart_suggestion":{"chart_type":"bar","title":"图表标题","categories":["A","B","C"],"series":[{"name":"系列","values":[1,2,3]}]},"diagram_spec":null,"visual_block":null,"visual_hint":"布局建议"}

visual_block 示例（kpi_cards）：{"type":"kpi_cards","items":[{"title":"营收","value":"32%","description":"同比增长","trend":"up"}]}
visual_block 示例（stat_highlight）：{"type":"stat_highlight","items":[{"value":"1.56亿","title":"年度营收","description":"创历史新高"}]}

要求：
- text_blocks 包含1个 heading 和至少4个 bullet 项，每条bullet提炼一个独立论点或数据点
- bullet 内容必须来自原文材料，禁止编造；每条≥20字，避免泛泛而谈
- chart_type 必须是用户消息中"可用图表类型"列出的值之一
- chart 数据只用原文中明确存在的数字，禁止编造
- 输出单个 JSON 对象（不是数组），完整且有效"""

    @property
    def tools(self) -> List[Tool]:
        return []

    # ------------------------------------------------------------------
    # 主执行入口（完全覆盖基类 run，不进 ReAct 循环）
    # ------------------------------------------------------------------

    def run(self, context: Dict[str, Any]) -> Dict:
        self._context = context
        self._page_contents = {}

        outline = context.get("outline", {})
        all_slides = outline.get("items", outline.get("slides", []))

        if not all_slides:
            raise ValueError("大纲为空，无法生成内容")

        shared = self._build_shared_context(context)
        logger.info(
            f"[ContentAgent] per-slide并行，共{len(all_slides)}页，最多{self.MAX_CONCURRENT}并发"
        )

        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT) as executor:
            futures: Dict = {
                executor.submit(
                    self._generate_one_slide,
                    slide,
                    all_slides[i - 1] if i > 0 else None,
                    shared,
                ): slide
                for i, slide in enumerate(all_slides)
            }

            for fut in as_completed(futures):
                slide = futures[fut]
                pn = slide.get("page_number", "?")
                try:
                    result = fut.result()
                    if result:
                        with self._lock:
                            self._page_contents[result.get("page_number", pn)] = result
                        logger.debug(f"[ContentAgent] P{pn} 完成")
                    else:
                        logger.warning(f"[ContentAgent] P{pn} 解析失败，使用占位内容")
                        with self._lock:
                            self._page_contents[pn] = self._make_placeholder(slide)
                except Exception as e:
                    logger.warning(f"[ContentAgent] P{pn} 异常: {e}，使用占位内容")
                    with self._lock:
                        self._page_contents[pn] = self._make_placeholder(slide)

        if not self._page_contents:
            raise ValueError("内容填充失败：所有页面均未生成内容")

        result = self._build_content_result()
        validation = self.validate(result)
        if not validation.valid:
            logger.warning(f"[ContentAgent] 验证警告: {validation.errors}")

        return result

    # ------------------------------------------------------------------
    # 共享上下文（一次性预计算，多线程只读）
    # ------------------------------------------------------------------

    def _build_shared_context(self, context: Dict[str, Any]) -> Dict:
        task = context.get("task", {})
        raw = context.get("raw_content", {})
        outline = context.get("outline", {})
        slides = outline.get("items", outline.get("slides", []))
        source_pages = raw.get("source_pages", [])
        tables = raw.get("_tables", [])

        # 表格清单摘要
        tables_text = ""
        if tables:
            lines = []
            for i, t in enumerate(tables[:6]):
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                sample = " | ".join(str(c) for c in (rows[0] if rows else [])[:6])
                lines.append(
                    f"  表格{i}: {t.get('source_sheet', '表格')} ({len(rows)}行) "
                    f"| 字段: {', '.join(str(h) for h in headers[:6])}"
                    f"\n    首行: {sample}"
                )
            tables_text = "\n".join(lines)

        # 技能指导（一次性加载，注入所有页面）
        skill_section = ""
        try:
            import pipeline.skills.charts        # noqa: F401
            import pipeline.skills.diagrams      # noqa: F401
            import pipeline.skills.visual_blocks  # noqa: F401
            from pipeline.skills import SkillRegistry
            registry = SkillRegistry.get()

            has_chart   = any(s.get("primary_visual") == "chart"   for s in slides)
            has_diagram = any(s.get("primary_visual") == "diagram" for s in slides)

            parts = []
            if has_chart:
                g = registry.get_prompt_fragments("chart")
                if g:
                    parts.append(f"### 可用图表类型（chart_suggestion.chart_type）\n{g}")
            if has_diagram:
                g = registry.get_prompt_fragments("diagram")
                if g:
                    parts.append(f"### 可用图示类型（diagram_spec.diagram_type）\n{g}")
            g = registry.get_prompt_fragments("visual_block")
            if g:
                parts.append(f"### 可用视觉块类型（visual_block.type）\n{g}")
            if parts:
                skill_section = "\n## 可用视觉类型（必须使用以下合法值）\n\n" + "\n\n".join(parts) + "\n"
        except Exception as _e:
            logger.debug(f"[ContentAgent] SkillRegistry 加载失败（非致命）: {_e}")

        # 始终准备 raw_text fallback（关键词匹配全部失败时的最后保底）
        raw_text_fallback = (raw.get("raw_text", "") or "")[:4000]

        return {
            "task": task,
            "source_pages": source_pages,
            "tables": tables,
            "tables_text": tables_text,
            "skill_section": skill_section,
            "raw_text_fallback": raw_text_fallback,
        }

    # ------------------------------------------------------------------
    # 单页生成（线程安全，无共享状态写入）
    # ------------------------------------------------------------------

    def _build_slide_messages(
        self, slide: Dict, prev_slide: Optional[Dict], shared: Dict
    ) -> List[ChatMessage]:
        """为单个页面构建 LLM 消息（无状态，可多线程并发调用）。"""
        pn = slide.get("page_number", "?")
        st = slide.get("slide_type", "content")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        pv = slide.get("primary_visual", "text")
        title = slide.get("title", (takeaway[:20] if takeaway else ""))
        task = shared["task"]

        # 上一页叙事接续（防止内容重复）
        prev_ctx = ""
        if prev_slide:
            prev_title = prev_slide.get("title", "")
            prev_kw = prev_slide.get("takeaway_message", prev_slide.get("takeaway", ""))
            prev_ctx = (
                f"\n## 上一页（叙事接续参考，勿重复）\n"
                f"P{prev_slide.get('page_number')}: {prev_title} | {prev_kw}\n"
            )

        # 材料注入：chart 页优先注入表格；无表格或非 chart 页改用章节文本；均无则 raw_text 保底
        material_text = ""
        if pv == "chart" and shared["tables"]:
            chart_data = self._find_chart_table(slide, shared["tables"])
            if chart_data:
                material_text = f"\n## 数据表格（直接使用，禁止编造数字）\n{chart_data}\n"
        if not material_text:
            section_text = self._find_best_section(slide, shared["source_pages"])
            if section_text:
                material_text = f"\n## 相关原文材料\n{section_text}\n"
            elif shared.get("raw_text_fallback"):
                material_text = f"\n## 原文材料（节选）\n{shared['raw_text_fallback']}\n"

        # 视觉要求
        has_table_data = bool(pv == "chart" and shared["tables"] and material_text.startswith("\n## 数据表格"))
        if pv == "chart":
            visual_req = (
                "⚠️ chart_suggestion 必须填写（使用上方表格数据，chart_type 使用合法值）"
                if has_table_data
                else "⚠️ chart_suggestion 必须填写（从原文材料中提炼数据，chart_type 使用合法值）"
            )
        elif pv == "diagram":
            visual_req = "⚠️ diagram_spec 必须填写（diagram_type 使用合法值）"
        elif pv == "visual_block":
            visual_req = "⚠️ visual_block 必须填写（type 使用合法值）"
        else:
            visual_req = "chart_suggestion、diagram_spec、visual_block 均设为 null"

        user_msg = f"""请为以下单个PPT页面生成内容。

## 当前页面
- 页码: P{pn} | 类型: {st} | 视觉: {pv}
- 标题: {title}
- 核心观点: {takeaway}
- 目标受众: {task.get('target_audience', '管理层')}
{prev_ctx}{material_text}{shared.get('skill_section', '')}---
{visual_req}
text_blocks 至少2个 bullet 项，内容来自原文材料，不要编造。

请直接输出 JSON 对象，放在 ```json ... ``` 代码块中。"""

        return [ChatMessage(role="user", content=user_msg)]

    def _generate_one_slide(
        self, slide: Dict, prev_slide: Optional[Dict], shared: Dict
    ) -> Optional[Dict]:
        """调用 LLM 生成单页内容，含截断检测和一次重试。线程安全（无写共享状态）。"""
        pn = slide.get("page_number", "?")
        messages = [
            ChatMessage(role="system", content=self.system_prompt),
            *self._build_slide_messages(slide, prev_slide, shared),
        ]

        for attempt in range(2):
            try:
                response = self.llm.chat(
                    messages=messages,
                    tools=None,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                if not response.success:
                    raise RuntimeError(f"LLM调用失败: {response.error}")

                # finish_reason 截断检测（基类 P0 修复的单页版本）
                if response.finish_reason in ("length", "max_tokens") and attempt == 0:
                    logger.warning(f"[ContentAgent] P{pn} 输出截断，要求重新输出...")
                    messages.append(ChatMessage(role="assistant", content=response.content or ""))
                    messages.append(ChatMessage(
                        role="user",
                        content="你的输出被截断了，请重新输出完整的JSON对象，减少text_blocks数量确保输出完整。",
                    ))
                    continue

                result = self._parse_single_page(response.content or "", pn)
                if result:
                    return result

                if attempt == 0:
                    logger.warning(f"[ContentAgent] P{pn} 解析失败，要求重新输出...")
                    messages.append(ChatMessage(role="assistant", content=response.content or ""))
                    messages.append(ChatMessage(
                        role="user",
                        content="请重新输出JSON对象，确保放在 ```json ... ``` 代码块中，格式正确。",
                    ))
                    continue

            except Exception as e:
                if attempt == 0:
                    logger.warning(f"[ContentAgent] P{pn} 第1次失败({e})，重试...")
                    continue
                logger.error(f"[ContentAgent] P{pn} 最终失败: {e}")

        return None

    # ------------------------------------------------------------------
    # 材料匹配（静态，线程安全）
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_kw(text: str) -> List[str]:
        """English word tokens + Chinese bigrams — works without jieba."""
        import re
        words: List[str] = []
        for segment in re.split(r'[\s\W]+', text.lower()):
            if not segment or len(segment) < 2:
                continue
            if all('一' <= c <= '鿿' for c in segment):
                # Chinese: emit overlapping bigrams for fuzzy matching
                words.extend(segment[i:i + 2] for i in range(len(segment) - 1))
            else:
                words.append(segment)
        return words

    @staticmethod
    def _find_best_section(slide: Dict, source_pages: List[Dict]) -> str:
        """关键词匹配原文章节，top-2 动态阈值：最相关必返回，次相关需达最高分60%。"""
        if not source_pages:
            return ""
        title = slide.get("title", "")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        section = slide.get("section", "")
        hint = slide.get("supporting_hint", "")

        # Fast-path: supporting_hint 精确匹配章节标题
        if hint:
            for sp in source_pages:
                if (sp.get("title") or "").strip() == hint.strip():
                    return sp.get("content", "")[:1500]

        kw_list = ContentAgent._extract_kw(f"{title} {section} {takeaway} {hint}")
        if not kw_list:
            return ""

        scored = []
        for sp in source_pages:
            t = (sp.get("title") or "").lower()
            c = (sp.get("content") or "").lower()
            score = sum(3 if w in t else (1 if w in c else 0) for w in kw_list)
            if score > 0:
                scored.append((score, sp))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]
        threshold = best_score * 0.6

        parts = [best.get("content", "")[:1500]]
        if len(scored) > 1 and scored[1][0] >= threshold:
            parts.append(scored[1][1].get("content", "")[:800])

        return "\n---\n".join(parts)

    @staticmethod
    def _find_chart_table(slide: Dict, tables: List[Dict]) -> str:
        """为 chart 页匹配最相关表格，top-2 注入：最相关20行，次相关5行摘要。"""
        if not tables:
            return ""
        title = slide.get("title", "")
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        data_source = slide.get("data_source", "")
        kw_list = ContentAgent._extract_kw(f"{title} {takeaway} {data_source}")

        scored = []
        for i, t in enumerate(tables):
            headers_str = " ".join(str(h) for h in t.get("headers", [])).lower()
            sheet_str = (t.get("source_sheet", "")).lower()
            score = sum(1 for w in kw_list if w in headers_str or w in sheet_str)
            scored.append((score, i, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        result_parts = []

        _, _, t1 = scored[0]
        headers1 = t1.get("headers", [])
        rows1 = t1.get("rows", [])
        lines = [f"📊 主表格「{t1.get('source_sheet', '')}」({len(rows1)}行，直接使用以下数字，禁止编造):"]
        lines.append("| " + " | ".join(str(h) for h in headers1[:8]) + " |")
        for row in rows1[:20]:
            lines.append("| " + " | ".join(str(c) for c in row[:8]) + " |")
        if len(rows1) > 20:
            lines.append(f"（共{len(rows1)}行，已截断）")
        result_parts.append("\n".join(lines))

        if len(scored) > 1 and scored[0][0] > 0 and scored[1][0] >= scored[0][0] * 0.6:
            _, _, t2 = scored[1]
            if t2 is not t1:
                headers2 = t2.get("headers", [])
                rows2 = t2.get("rows", [])
                lines2 = [
                    f"📊 参考表格「{t2.get('source_sheet', '')}」"
                    f"({len(rows2)}行，字段: {', '.join(str(h) for h in headers2[:6])}):"
                ]
                for row in rows2[:5]:
                    lines2.append("  " + " | ".join(str(c) for c in row[:6]))
                result_parts.append("\n".join(lines2))

        return "\n\n".join(result_parts)

    # ------------------------------------------------------------------
    # 解析与组装
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_single_page(text: str, page_number: int) -> Optional[Dict]:
        """从 LLM 输出中提取单个 JSON 对象。"""
        import re

        # 优先从代码块中提取
        for pattern in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1).strip())
                    if isinstance(data, dict) and "text_blocks" in data:
                        data.setdefault("page_number", page_number)
                        return data
                except Exception:
                    continue

        # 回退：找第一个完整 JSON 对象
        try:
            start = text.find('{')
            if start >= 0:
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(text, start)
                if isinstance(data, dict) and "text_blocks" in data:
                    data.setdefault("page_number", page_number)
                    return data
        except Exception:
            pass

        return None

    @staticmethod
    def _parse_pages_from_text(text: str) -> list:
        """从文本中提取 JSON 数组（extract_output 兼容接口）。"""
        import re
        for pattern in [r'```json\s*(\[[\s\S]*?\])\s*```', r'```\s*(\[[\s\S]*?\])\s*```']:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        if "page_number" in data[0] or "text_blocks" in data[0]:
                            return data
                except Exception:
                    continue
        return []

    @staticmethod
    def _make_placeholder(slide: Dict) -> Dict:
        """为失败页面生成占位内容（DesignAgent 会标记 is_failed）。"""
        takeaway = slide.get("takeaway_message", slide.get("takeaway", ""))
        return {
            "page_number": slide.get("page_number"),
            "text_blocks": [
                {"type": "heading", "text": slide.get("title", takeaway[:30] if takeaway else "")},
                {"type": "bullet", "text": takeaway, "level": 1},
            ],
            "chart_suggestion": None,
            "diagram_spec": None,
            "visual_block": None,
            "visual_hint": "",
            "is_failed": True,
            "error": "content_generation_failed",
        }

    def _build_content_result(self) -> Dict:
        """将收集的页面内容组装为 ContentResult.to_dict() 格式。"""
        outline = self._context.get("outline", {})
        outline_slides = {
            s["page_number"]: s
            for s in outline.get("items", outline.get("slides", []))
        }

        slides = []
        for pn in sorted(self._page_contents.keys()):
            page = self._page_contents[pn]
            outline_page = outline_slides.get(pn, {})

            raw_blocks = page.get("text_blocks", [])
            text_blocks = []
            for b in raw_blocks:
                if isinstance(b, dict):
                    text_blocks.append({
                        "content": b.get("text", b.get("content", "")),
                        "level": b.get("level", 0),
                        "is_bold": b.get("type") == "heading",
                    })

            takeaway = (
                outline_page.get("takeaway_message")
                or outline_page.get("takeaway")
                or page.get("takeaway_message", "")
            )

            entry: Dict = {
                "page_number": pn,
                "slide_type": outline_page.get("slide_type", "content"),
                "takeaway_message": takeaway,
                "primary_visual": outline_page.get("primary_visual", "text"),
                "text_blocks": text_blocks,
                "chart_suggestion": page.get("chart_suggestion"),
                "diagram_spec": page.get("diagram_spec"),
                "visual_block": page.get("visual_block"),
                "source_note": page.get("visual_hint", ""),
            }
            if page.get("is_failed"):
                entry["is_failed"] = True
                entry["error"] = page.get("error", "")
            slides.append(entry)

        return {"slides": slides}

    # ------------------------------------------------------------------
    # 抽象方法实现（基类要求；实际执行走 run() 覆盖路径）
    # ------------------------------------------------------------------

    def build_initial_messages(self, context: Dict[str, Any]) -> List[ChatMessage]:
        """供基类 run() 调用的兜底实现（正常路径不走这里）。"""
        slides = context.get("outline", {}).get("items", [])
        if not slides:
            return [ChatMessage(role="user", content="大纲为空")]
        shared = self._build_shared_context(context)
        return self._build_slide_messages(slides[0], None, shared)

    def extract_output(self, messages: List[ChatMessage]) -> Dict:
        if self._page_contents:
            return self._build_content_result()

        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                pages = self._parse_pages_from_text(msg.content)
                if pages:
                    logger.info(f"[ContentAgent] 从文本回复中提取到{len(pages)}页内容")
                    for page in pages:
                        pn = page.get("page_number")
                        if pn:
                            self._page_contents[pn] = page
                    return self._build_content_result()

        raise ValueError("未完成内容填充，请确认 LLM 已输出 JSON")

    def validate(self, output: Dict) -> ValidationResult:
        errors = []
        slides = output.get("slides", [])
        outline = self._context.get("outline", {})
        outline_slides = outline.get("items", outline.get("slides", []))

        if not slides:
            errors.append("内容结果为空")
            return ValidationResult(valid=False, errors=errors)

        if len(slides) < len(outline_slides) * 0.7:
            errors.append(f"内容页数({len(slides)})远少于大纲页数({len(outline_slides)})")

        for s in slides:
            pn = s.get("page_number", "?")
            text_blocks = s.get("text_blocks", [])
            primary_visual = s.get("primary_visual", "text")

            if not text_blocks:
                errors.append(f"第{pn}页 text_blocks 为空")
                continue

            content_blocks = [b for b in text_blocks if b.get("content", "").strip() and not b.get("is_bold")]
            if len(content_blocks) < 1:
                errors.append(f"第{pn}页内容过少（少于1个正文块）")

            if primary_visual == "chart" and not s.get("chart_suggestion"):
                errors.append(f"第{pn}页 primary_visual='chart' 但缺少 chart_suggestion")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    # ------------------------------------------------------------------
    # 工具辅助方法（供调试 / /rerun-page 复用）
    # ------------------------------------------------------------------

    def _tool_read_outline(self) -> str:
        outline = self._context.get("outline", {})
        slides = outline.get("items", outline.get("slides", []))
        lines = [f"=== 大纲（共{len(slides)}页）==="]
        for s in slides:
            pn = s.get("page_number", "?")
            pv = s.get("primary_visual", "text")
            takeaway = s.get("takeaway_message", s.get("takeaway", ""))
            lines.append(
                f"P{pn}: [{s.get('slide_type', '')}] {s.get('title', takeaway[:15])} | "
                f"takeaway: {takeaway} | visual: {pv}"
            )
        return "\n".join(lines)

    def _tool_read_raw_material(self, section: str, max_chars: int = 2000) -> str:
        raw = self._context.get("raw_content", {})
        for sp in raw.get("source_pages", []):
            if section.lower() in (sp.get("title") or "").lower():
                return f"【{sp['title']}】\n{sp.get('content', '')[:max_chars]}"
        text = raw.get("_raw_text", "")
        idx = text.lower().find(section.lower())
        if idx >= 0:
            return text[max(0, idx - 50): idx + max_chars]
        return f"未找到章节 '{section}'"

    def _tool_query_table(self, table_index: int, columns: Optional[List[str]] = None) -> str:
        raw = self._context.get("raw_content", {})
        tables = raw.get("_tables", [])
        if table_index >= len(tables):
            return f"表格{table_index}不存在（共{len(tables)}个）"
        t = tables[table_index]
        headers = t.get("headers", [])
        rows = t.get("rows", [])
        if columns:
            col_indices = [headers.index(c) for c in columns if c in headers]
            selected_headers = [headers[i] for i in col_indices]
            selected_rows = [[row[i] for i in col_indices if i < len(row)] for row in rows]
        else:
            selected_headers = headers
            selected_rows = rows
        lines = [f"表格{table_index}: {t.get('source_sheet', '')}", " | ".join(str(h) for h in selected_headers)]
        for row in selected_rows[:20]:
            lines.append(" | ".join(str(c) for c in row))
        if len(selected_rows) > 20:
            lines.append(f"... 共{len(selected_rows)}行")
        return "\n".join(lines)

    def _tool_read_skill_guidance(self, skill_type: str) -> str:
        try:
            import pipeline.skills.charts        # noqa: F401
            import pipeline.skills.diagrams      # noqa: F401
            import pipeline.skills.visual_blocks  # noqa: F401
            from pipeline.skills import SkillRegistry
            registry = SkillRegistry.get()
            skill = (
                registry.find("chart", skill_type)
                or registry.find("diagram", skill_type)
                or registry.find("visual_block", skill_type)
            )
            if skill:
                return skill.prompt_fragment()
        except Exception:
            pass
        return f"未找到技能 '{skill_type}' 的指导"
