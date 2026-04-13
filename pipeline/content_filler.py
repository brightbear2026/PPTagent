"""
内容填充器 — Pipeline content阶段

根据大纲逐页生成详细内容（文字块、图表建议、图表规格）。
批量调用LLM（3-4页/批），支持批次级重试。
这是第二个检查点，用户审阅并确认后进入build阶段。
"""

import json
import re
import time
from typing import Optional

from models.slide_spec import (
    RawContent, AnalysisResult, OutlineResult, OutlineItem,
    SlideContent, TextBlock, ChartSuggestion, ContentDiagramSpec,
    EnrichedTableData, DiagramType,
    VisualBlock, VisualBlockItem, VisualBlockType,
)
from llm_client.base import LLMClient


class ContentFiller:
    """逐页内容生成器"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.batch_size = 3  # 每批处理的页数

    def fill_all(
        self,
        raw_content: RawContent,
        analysis: AnalysisResult,
        outline: OutlineResult,
        target_audience: str = "管理层",
    ) -> list[SlideContent]:
        """
        为大纲中的每一页生成详细内容

        跳过title/agenda页（build阶段直接渲染）。
        每3-4页为一批调用LLM，失败批次自动重试。
        """
        # 需要填充的页面
        fillable_pages = [
            item for item in outline.items
            if item.slide_type not in ("title", "agenda")
        ]

        if not fillable_pages:
            return []

        # 准备共享上下文（每批都会用到）
        shared_context = self._build_shared_context(
            raw_content, analysis, outline, target_audience
        )

        # 分批处理
        all_contents: list[SlideContent] = []
        batches = self._split_batches(fillable_pages)

        for batch_idx, batch in enumerate(batches):
            contents = self._process_batch(batch, shared_context, batch_idx)
            all_contents.extend(contents)

        # 合并结果，保持页码顺序
        all_contents.sort(key=lambda c: c.page_number)
        return all_contents

    def fill_single_page(
        self,
        page_number: int,
        raw_content: RawContent,
        analysis: AnalysisResult,
        outline: OutlineResult,
    ) -> Optional[SlideContent]:
        """
        为单页重新生成内容（用户编辑后单页重跑）
        """
        item = None
        for i in outline.items:
            if i.page_number == page_number:
                item = i
                break
        if item is None:
            return None

        shared_context = self._build_shared_context(raw_content, analysis, outline)
        contents = self._process_batch([item], shared_context, 0)

        return contents[0] if contents else None

    # ================================================================
    # 批次处理
    # ================================================================

    def _split_batches(self, items: list[OutlineItem]) -> list[list[OutlineItem]]:
        """将页面分批"""
        batches = []
        for i in range(0, len(items), self.batch_size):
            batches.append(items[i:i + self.batch_size])
        return batches

    def _process_batch(
        self,
        batch: list[OutlineItem],
        shared_context: str,
        batch_idx: int,
        max_retries: int = 2,
    ) -> list[SlideContent]:
        """处理一批页面，失败自动重试"""
        prompt = self._build_batch_prompt(batch, shared_context)

        for attempt in range(max_retries + 1):
            response = self.llm.generate(
                prompt, temperature=0.4, max_tokens=8192
            )

            if not response.success:
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                # 全部重试失败，逐页标记失败
                return [
                    SlideContent(
                        page_number=item.page_number,
                        slide_type=item.slide_type,
                        takeaway_message=item.takeaway_message,
                        is_failed=True,
                        error_message=f"LLM调用失败: {response.error}",
                    )
                    for item in batch
                ]

            contents = self._parse_batch_response(batch, response.content)
            if contents is not None:
                return contents

            # 解析失败，重试
            if attempt < max_retries:
                time.sleep(2)

        # 解析全部失败
        return [
            SlideContent(
                page_number=item.page_number,
                slide_type=item.slide_type,
                takeaway_message=item.takeaway_message,
                is_failed=True,
                error_message="LLM输出解析失败",
            )
            for item in batch
        ]

    # ================================================================
    # Prompt构建
    # ================================================================

    def _build_shared_context(
        self,
        raw_content: RawContent,
        analysis: AnalysisResult,
        outline: OutlineResult,
        target_audience: str = "管理层",
    ) -> str:
        """构建所有批次共享的上下文"""
        parts = []

        # 目标受众
        parts.append(f"## 目标受众\n{target_audience}\n请确保内容的深度和专业度适配受众水平。")

        # 整体叙事
        parts.append(f"## 整体叙事逻辑\n{outline.narrative_logic}")

        # 全部大纲（让LLM知道上下文）
        outline_lines = []
        for item in outline.items:
            outline_lines.append(
                f"  P{item.page_number}[{item.slide_type}]: {item.takeaway_message}"
            )
        parts.append("## 完整大纲\n" + "\n".join(outline_lines))

        # 原始材料
        text_preview = raw_content.raw_text[:3000]
        if len(raw_content.raw_text) > 3000:
            text_preview += "\n...(省略)"
        parts.append(f"## 原始材料\n{text_preview}")

        # 关键数据
        metrics_lines = []
        for m in analysis.derived_metrics[:20]:
            line = f"- {m.name}: {m.formatted_value}"
            if m.context:
                line += f" ({m.context})"
            metrics_lines.append(line)
        if metrics_lines:
            parts.append("## 可用数据指标\n" + "\n".join(metrics_lines))

        # 关键发现
        if analysis.key_findings:
            parts.append("## 关键发现\n" + "\n".join(
                f"- {f}" for f in analysis.key_findings[:5]
            ))

        # 原始表格数据（chart_suggestion必须引用这些真实数据）
        table_blocks = []
        for et in getattr(analysis, 'enriched_tables', [])[:3]:
            t = et.original
            if not t.headers:
                continue
            header_line = " | ".join(str(h) for h in t.headers[:8])
            rows_preview = []
            for row in t.rows[:8]:
                cells = [str(c)[:15] if c is not None else "" for c in row[:8]]
                rows_preview.append(" | ".join(cells))
            summary_lines = []
            for col, stats in et.summary.items():
                if isinstance(stats, dict):
                    summary_lines.append(
                        f"  {col}: 合计={stats.get('total','')}, "
                        f"均值={stats.get('avg','')}, "
                        f"最大={stats.get('max','')}, 最小={stats.get('min','')}"
                    )
            sheet_name = t.source_sheet or "表格"
            block = f"### {sheet_name}\n{header_line}\n" + "\n".join(rows_preview)
            if summary_lines:
                block += "\n统计:\n" + "\n".join(summary_lines)
            table_blocks.append(block)
        if table_blocks:
            parts.append(
                "## 原始表格数据（chart_suggestion的数据必须完全来自以下表格，禁止编造数字！）\n"
                + "\n\n".join(table_blocks)
            )

        return "\n\n".join(parts)

    def _build_batch_prompt(
        self,
        batch: list[OutlineItem],
        shared_context: str,
    ) -> str:
        """构建批次prompt"""
        page_descriptions = []
        for item in batch:
            pv = getattr(item, 'primary_visual', '') or 'text_only'
            desc = f"""### 第{item.page_number}页 [{item.slide_type}] primary_visual={pv}
- 核心论点: {item.takeaway_message}
- 支撑材料提示: {item.supporting_hint}
- 数据来源: {item.data_source or '无特定来源'}
- 主视觉类型: {pv}"""
            page_descriptions.append(desc)

        pages_block = "\n\n".join(page_descriptions)

        return f"""你是一位顶级咨询公司的PPT内容专家。请为以下页面生成详细内容。

{shared_context}

---
## 需要生成的页面
{pages_block}

---
## 输出格式

返回JSON数组，每个元素对应一页：
```json
[{{"page_number": N, "takeaway_message": "核心论点", "text_blocks": [{{"content": "...", "level": 0, "is_bold": false}}], "chart_suggestion": null, "diagram_spec": null, "visual_hint": null, "source_note": ""}}]
```

### text_blocks
level: 0=正文段落, 1=一级子弹点, 2=二级子弹点。每页2-5个。

### chart_suggestion（primary_visual="chart"时必填，其余null）
```json
{{"chart_type": "column", "data_feature": "time_series", "title": "图表标题", "categories": ["2022","2023","2024"], "series": [{{"name": "收入(亿)", "values": [12.0, 13.5, 15.6]}}], "so_what": "结论"}}
```
chart_type: bar/column/line/pie/combo。**categories和series的数字必须完全来自「原始表格数据」章节，严禁编造！**

### diagram_spec（primary_visual="diagram"时必填，其余null）
- process_flow: {{"diagram_type":"process_flow","title":"...","direction":"horizontal","nodes":[{{"id":"1","label":"步骤","desc":"描述"}}],"connections":[{{"from":"1","to":"2"}}]}}
- architecture: {{"diagram_type":"architecture","title":"...","variant":"layers","layers":[{{"label":"层名","items":["组件"]}}]}}
- relationship: {{"diagram_type":"relationship","title":"...","variant":"causal","nodes":[{{"id":"1","label":"因素"}}],"edges":[{{"from":"1","to":"2","label":"影响"}}]}}
- framework: {{"diagram_type":"framework","title":"...","variant":"matrix_2x2|swot|pyramid|funnel",...}}

### visual_hint（primary_visual="visual_block"时必填，其余null）
block_type选择：
| block_type | 适用场景 | items字段 |
|---|---|---|
| kpi_cards | 2-4个关键指标 | title, value, description, trend(up/down/flat) |
| step_cards | 3-6个步骤 | title, description |
| comparison_columns | A vs B对比 | title, description |
| icon_text_grid | 4-6个并列要点 | title, description |
| stat_highlight | 单个震撼数字 | value, title, description |
| callout_box | 关键洞察/金句 | title, description |
尽量避免bullet_list！有数字用kpi_cards，有步骤用step_cards，有对比用comparison_columns。

### primary_visual互斥规则（严格遵守！）
- "chart": 只填chart_suggestion，其余null
- "diagram": 只填diagram_spec，其余null
- "visual_block": 只填visual_hint，其余null
- "text_only": 三个都null

### 质量标准
- text_blocks要具体，包含实际数据
- takeaway可微调措辞但不改核心论点
- 数据必须来自原始材料，不可编造

只输出JSON数组，不要其他文字。"""

    # ================================================================
    # 响应解析
    # ================================================================

    def _parse_batch_response(
        self,
        batch: list[OutlineItem],
        text: str,
    ) -> Optional[list[SlideContent]]:
        """解析批次响应"""
        data = self._extract_json_array(text)
        if data is None:
            return None

        # 按page_number建立索引
        batch_map = {item.page_number: item for item in batch}
        contents = []

        for item_data in data:
            page_num = item_data.get("page_number")
            if page_num is None or page_num not in batch_map:
                continue

            outline_item = batch_map[page_num]

            # 解析text_blocks
            text_blocks = []
            for tb in item_data.get("text_blocks", []):
                if not isinstance(tb, dict) or "content" not in tb:
                    continue
                text_blocks.append(TextBlock(
                    content=tb["content"],
                    level=tb.get("level", 0),
                    is_bold=tb.get("is_bold", False),
                ))

            # 解析chart_suggestion
            chart_suggestion = None
            cs = item_data.get("chart_suggestion")
            if cs and isinstance(cs, dict):
                chart_suggestion = ChartSuggestion(
                    chart_type=cs.get("chart_type", "column"),
                    data_feature=cs.get("data_feature", ""),
                    title=cs.get("title", ""),
                    categories=cs.get("categories", []),
                    series=cs.get("series", []),
                    so_what=cs.get("so_what", ""),
                )

            # 解析diagram_spec
            diagram_spec = None
            ds = item_data.get("diagram_spec")
            if ds and isinstance(ds, dict):
                try:
                    diagram_spec = ContentDiagramSpec.from_dict(ds)
                except Exception:
                    pass

            # 解析visual_hint
            visual_block = None
            vh = item_data.get("visual_hint")
            if vh and isinstance(vh, dict):
                try:
                    visual_block = VisualBlock.from_dict(vh)
                except Exception:
                    pass

            # ── primary_visual 互斥强制 ──
            pv = getattr(outline_item, 'primary_visual', '') or 'text_only'
            if pv == 'chart':
                diagram_spec = None
                visual_block = None
            elif pv == 'diagram':
                chart_suggestion = None
                visual_block = None
            elif pv == 'visual_block':
                chart_suggestion = None
                diagram_spec = None
            else:  # text_only
                chart_suggestion = None
                diagram_spec = None
                visual_block = None

            # 如果 primary_visual=visual_block 且 LLM 未输出 visual_hint，从 text_blocks 自动推断
            if pv == 'visual_block' and (visual_block is None or visual_block.block_type == VisualBlockType.BULLET_LIST):
                inferred = self._infer_visual_block(text_blocks, outline_item)
                if inferred is not None:
                    visual_block = inferred

            # 质量校验
            warnings = self._validate_content(
                text_blocks, outline_item.slide_type
            )

            contents.append(SlideContent(
                page_number=page_num,
                slide_type=outline_item.slide_type,
                takeaway_message=item_data.get(
                    "takeaway_message", outline_item.takeaway_message
                ),
                text_blocks=text_blocks,
                chart_suggestion=chart_suggestion,
                diagram_spec=diagram_spec,
                visual_block=visual_block,
                primary_visual=pv,
                source_note=item_data.get("source_note", ""),
                warnings=warnings,
            ))

        return contents if contents else None

    def _extract_json_array(self, text: str) -> Optional[list]:
        """从文本中提取JSON数组"""
        text = text.strip()

        # DeepSeek-R1: strip <think'> reasoning tags
        if '<think' in text:
            text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text, flags=re.DOTALL).strip()

        # 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # ```json ... ```
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 找第一个 [ ... ]
        depth = 0
        start = None
        for i, ch in enumerate(text):
            if ch == '[':
                if start is None:
                    start = i
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        start = None

        # 最后尝试：逐个提取 JSON 对象（容忍部分页面格式错误）
        return self._extract_individual_pages(text)

    def _extract_individual_pages(self, text: str) -> Optional[list]:
        """逐个提取 {"page_number": N, ...} JSON对象，容忍部分页面损坏"""
        results = []
        pattern = r'\{\s*"page_number"\s*:\s*\d+'
        for match in re.finditer(pattern, text):
            start = match.start()
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(text[start:i + 1])
                            if isinstance(obj, dict) and "page_number" in obj:
                                results.append(obj)
                        except json.JSONDecodeError:
                            pass
                        break
        return results if results else None

    # ================================================================
    # 质量校验
    # ================================================================

    def _validate_content(
        self, text_blocks: list[TextBlock], slide_type: str
    ) -> list[str]:
        """校验单页内容质量"""
        warnings = []

        if not text_blocks:
            warnings.append("页面无文本内容")
            return warnings

        # 检查内容长度
        total_chars = sum(len(tb.content) for tb in text_blocks)
        if total_chars < 10:
            warnings.append("内容过短，可能缺少具体信息")

        # 检查是否有子弹点
        has_bullets = any(tb.level > 0 for tb in text_blocks)
        if slide_type == "content" and not has_bullets:
            warnings.append("内容页建议使用子弹点结构")

        return warnings

    # ================================================================
    # 可视化块自动推断（fallback）
    # ================================================================

    _NUMBER_RE = re.compile(r'\d+[\.,]?\d*\s*[%％亿万元倍]')
    _COMPARE_WORDS = re.compile(r'(对比|比较|versus|vs\.?|优势|劣势|方案[AB]|相比)', re.IGNORECASE)
    _STEP_WORDS = re.compile(r'(步骤|阶段|流程|第[一二三四五六]步|Phase|Step)', re.IGNORECASE)

    def _infer_visual_block(
        self,
        text_blocks: list[TextBlock],
        outline_item: OutlineItem,
    ) -> Optional[VisualBlock]:
        """从text_blocks内容自动推断可视化形式"""
        if not text_blocks:
            return None

        all_text = " ".join(tb.content for tb in text_blocks)
        bullet_blocks = [tb for tb in text_blocks if tb.level >= 1]

        # 含多个数字/百分比 → kpi_cards
        numbers = self._NUMBER_RE.findall(all_text)
        if len(numbers) >= 2:
            items = []
            for tb in bullet_blocks[:4]:
                nums = self._NUMBER_RE.findall(tb.content)
                if nums:
                    items.append(VisualBlockItem(
                        value=nums[0],
                        title=self._NUMBER_RE.sub('', tb.content).strip(' ：:，,、'),
                    ))
            if len(items) >= 2:
                return VisualBlock(block_type=VisualBlockType.KPI_CARDS, items=items)

        # 含对比词 → comparison_columns
        if self._COMPARE_WORDS.search(all_text) and len(bullet_blocks) >= 2:
            items = [
                VisualBlockItem(title=tb.content[:20], description=tb.content)
                for tb in bullet_blocks[:4]
            ]
            return VisualBlock(block_type=VisualBlockType.COMPARISON_COLUMNS, items=items)

        # 含步骤词 → step_cards
        if self._STEP_WORDS.search(all_text) and len(bullet_blocks) >= 3:
            items = [
                VisualBlockItem(title=tb.content[:15], description=tb.content)
                for tb in bullet_blocks[:6]
            ]
            return VisualBlock(block_type=VisualBlockType.STEP_CARDS, items=items)

        # 4-6个并列子弹点 → icon_text_grid
        if 4 <= len(bullet_blocks) <= 6:
            items = [
                VisualBlockItem(title=tb.content[:12], description=tb.content)
                for tb in bullet_blocks
            ]
            return VisualBlock(block_type=VisualBlockType.ICON_TEXT_GRID, items=items)

        return None
