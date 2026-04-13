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

        return f"""你是一位顶级咨询公司的PPT内容专家。
请为以下页面生成详细内容。内容必须专业、具体、数据驱动。

{shared_context}

---

## 需要生成的页面

{pages_block}

---

## 输出要求

返回JSON数组，每个元素对应一页的详细内容。格式：
```json
[
  {{
    "page_number": {batch[0].page_number},
    "takeaway_message": "可能微调措辞后的核心论点",
    "text_blocks": [
      {{"content": "正文段落或子弹点内容", "level": 0, "is_bold": false}},
      {{"content": "子弹点1（关键支撑）", "level": 1, "is_bold": false}},
      {{"content": "子弹点2", "level": 1, "is_bold": false}}
    ],
    "visual_hint": {{
      "block_type": "kpi_cards",
      "items": [
        {{"title": "收入", "value": "15.6亿", "description": "同比+32%", "trend": "up"}},
        {{"title": "利润", "value": "3.2亿", "description": "同比+18%", "trend": "up"}}
      ]
    }},
    "chart_suggestion": null,
    "diagram_spec": null,
    "source_note": "数据来源脚注"
  }},
  {{
    "page_number": ...,
    "takeaway_message": "...",
    "text_blocks": [...],
    "visual_hint": {{
      "block_type": "step_cards",
      "items": [
        {{"title": "需求分析", "description": "收集业务需求，明确目标"}},
        {{"title": "方案设计", "description": "架构评审，技术选型"}}
      ]
    }},
    "chart_suggestion": {{
      "chart_type": "column",
      "data_feature": "time_series",
      "title": "图表标题",
      "categories": ["2022", "2023", "2024"],
      "series": [{{"name": "收入(亿)", "values": [12.0, 13.5, 15.6]}}],
      "so_what": "图表结论，如：收入持续增长，2024年加速"
    }},
    "diagram_spec": null,
    "source_note": "..."
  }}
]
```

### text_blocks level说明
- 0: 正文段落
- 1: 一级子弹点（主要论据）
- 2: 二级子弹点（细节/数据）

### chart_suggestion 规则
- **积极生成图表**：只要页面涉及数据对比、趋势、占比、排名，都应提供 chart_suggestion
- slide_type为"data"时必须提供图表
- slide_type为"content"时，如果 takeaway 或 text_blocks 包含具体数字/百分比/对比，也应生成图表
- chart_type: "bar"(横向条形图), "column"(纵向柱状图), "line"(折线图), "pie"(饼图), "combo"(柱+线组合图)
- 数据必须来自原始材料，不可编造数字
- so_what 是这张图的结论，用一句话说明
- 即使只有2-3个数据点也值得做图表（对比更直观）

### diagram_spec 规则
- slide_type为"diagram"时必须提供
- 当内容描述流程、架构、关系时，即使不是 diagram 类型也可以提供
- 支持类型:
  - process_flow: 流程/步骤图
    ```json
    {{"diagram_type": "process_flow", "title": "...",
      "direction": "horizontal",
      "nodes": [{{"id": "1", "label": "步骤1", "desc": "描述"}}],
      "connections": [{{"from": "1", "to": "2", "label": "→"}}]}}
    ```
  - architecture: 架构/层级图
    ```json
    {{"diagram_type": "architecture", "title": "...",
      "variant": "layers",
      "layers": [{{"label": "层名", "items": ["组件1", "组件2"]}}]}}
    ```
  - relationship: 因果/关系图
    ```json
    {{"diagram_type": "relationship", "title": "...",
      "variant": "causal",
      "nodes": [{{"id": "1", "label": "因素", "role": "cause"}}],
      "edges": [{{"from": "1", "to": "2", "label": "+30%", "type": "directed"}}]}}
    ```
  - framework: 矩阵/SWOT/金字塔
    ```json
    {{"diagram_type": "framework", "title": "...",
      "variant": "matrix_2x2",
      "x_axis": {{"label": "维度X", "low": "低", "high": "高"}},
      "y_axis": {{"label": "维度Y", "low": "低", "high": "高"}},
      "quadrants": [{{"position": "top_left", "label": "象限名", "items": ["项目A"]}}]}}
    ```

### visual_hint 规则（重要！决定页面视觉呈现形式）
每页必须提供 visual_hint 字段，指导页面用什么可视化形式呈现文字内容。
可选值及适用场景：
- **"kpi_cards"**: 页面包含2-4个关键指标/数字 → 大数字卡片
  items格式: [{{"title": "指标名", "value": "15.6亿", "description": "同比增长32%", "trend": "up"}}]
- **"comparison_columns"**: A vs B 对比/方案对比/优劣势对比 → 并列栏
  items格式: [{{"title": "方案A", "description": "• 成本低\\n• 部署快"}}]
- **"step_cards"**: 3-6个步骤/阶段/流程 → 编号卡片+箭头
  items格式: [{{"title": "步骤1: 分析", "description": "收集业务需求"}}]
- **"icon_text_grid"**: 4-6个并列要点/能力/特性 → 图标网格
  items格式: [{{"title": "数据分析", "description": "结构化数据处理引擎"}}]
- **"stat_highlight"**: 单个核心数据/震撼数字 → 超大字号居中
  items格式: [{{"value": "32%", "title": "收入增长率", "description": "远超行业平均15%"}}]
- **"callout_box"**: 关键洞察/重要引用/结论金句 → 引用框
  items格式: [{{"title": "关键洞察", "description": "引用内容..."}}]
- **"bullet_list"**: 仅当以上都不适合时使用（尽量少用！）

**选择原则：尽量避免 bullet_list！** 大多数内容都可以用更好的可视化形式：
- 有具体数字 → kpi_cards 或 stat_highlight
- 有步骤/流程描述 → step_cards
- 有对比/两种方案 → comparison_columns
- 有多个并列要点 → icon_text_grid
- 有关键结论/洞察 → callout_box

### primary_visual 互斥规则（最重要！严格遵守！）
每页有一个 primary_visual 属性，决定该页只能输出哪种视觉内容：
- primary_visual="chart": **只填** chart_suggestion，visual_hint=null, diagram_spec=null
- primary_visual="diagram": **只填** diagram_spec，visual_hint=null, chart_suggestion=null
- primary_visual="visual_block": **只填** visual_hint，chart_suggestion=null, diagram_spec=null
- primary_visual="text_only": 三个都必须为 null

**严禁同时输出多种视觉内容！** 每页只有一个"主角"。

### 质量标准
- text_blocks 内容要具体，包含实际数据，不能只有框架性文字
- 每页2-5个text_blocks
- takeaway可微调措辞但不可改变核心论点
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

        return None

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
