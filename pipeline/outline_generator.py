"""
大纲生成器 — Pipeline outline阶段

基于金字塔原理生成页面级大纲。这是第一个检查点，用户审阅并确认。
输入：RawContent + AnalysisResult
输出：OutlineResult（含OutlineItem列表）
"""

import json
import re
from typing import Optional

from models.slide_spec import (
    RawContent, AnalysisResult, OutlineItem, OutlineResult,
)
from llm_client.base import LLMClient


class OutlineGenerator:
    """金字塔原理驱动的PPT大纲生成器"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(
        self,
        raw_content: RawContent,
        analysis: AnalysisResult,
        title: str = "",
        target_audience: str = "管理层",
        scenario: str = "",
        page_count_hint: int = 0,
    ) -> OutlineResult:
        """
        生成PPT大纲

        Args:
            raw_content: 第1层解析的原始内容
            analysis: analyze阶段的派生指标和关键发现
            title: PPT标题
            target_audience: 目标受众
            scenario: 汇报场景
            page_count_hint: 期望页数（0=自动决定）
        """
        prompt = self._build_prompt(
            raw_content, analysis, title, target_audience, scenario, page_count_hint
        )

        response = self.llm.generate(prompt, temperature=0.4, max_tokens=8192)
        if not response.success:
            raise RuntimeError(f"LLM大纲生成失败: {response.error}")

        print(f"[outline] LLM response length={len(response.content)}")

        result = self._parse_response(response.content)
        self._validate(result)
        self._assign_primary_visual(result)
        return result

    # ================================================================
    # Prompt构建
    # ================================================================

    SCENARIO_FRAMEWORKS = {
        "季度汇报": (
            "SCR（Situation-Complication-Resolution）",
            "先现状，再挑战/偏差，最后解决方案与下一步行动"
        ),
        "战略提案": (
            "SCQA（Situation-Complication-Question-Answer）",
            "先背景，再矛盾，提出核心问题，最后给出战略回答与行动计划"
        ),
        "竞标pitch": (
            "AIDA（Attention-Interest-Desire-Action）",
            "先用数据/痛点抓注意力，再展示方案亮点引发兴趣，用案例/ROI激发需求，最后CTA"
        ),
        "内部分析": (
            "Issue Tree + MECE分解",
            "拆解核心问题为互斥穷举的子问题，逐层用数据验证假设，最终汇总结论"
        ),
        "培训材料": (
            "ADDIE（分析-设计-开发-实施-评估）",
            "先定义学习目标，按知识依赖顺序组织，每章有要点摘要，结尾有行动清单"
        ),
        "项目汇报": (
            "STAR（Situation-Task-Action-Result）",
            "先项目背景，再目标/KPI，展示关键行动，最后量化成果与经验教训"
        ),
        "产品发布": (
            "Problem-Solution-Benefit",
            "先痛点/市场机会，再产品方案与核心功能，最后用户收益与路线图"
        ),
    }

    def _build_prompt(
        self,
        raw_content: RawContent,
        analysis: AnalysisResult,
        title: str,
        target_audience: str,
        scenario: str,
        page_count_hint: int,
    ) -> str:
        """构建金字塔原理大纲prompt"""

        # 原始材料摘要
        text_preview = raw_content.raw_text[:4000]
        if len(raw_content.raw_text) > 4000:
            text_preview += "\n...(省略)"

        # 表格概要
        table_summary = self._summarize_tables(raw_content)

        # 派生指标（精选最有说服力的）
        metrics_text = self._format_metrics(analysis)

        # 关键发现
        findings_text = "\n".join(
            f"- {f}" for f in analysis.key_findings[:5]
        ) if analysis.key_findings else "（无）"

        # 数据gap提示
        gaps_text = "\n".join(
            f"- {g.gap_description}（{g.importance}）" for g in analysis.data_gaps[:3]
        ) if analysis.data_gaps else "（无）"

        # 校验警告
        warnings_text = "\n".join(
            f"- {w.message}" for w in analysis.validation_warnings[:3]
        ) if analysis.validation_warnings else ""

        page_instruction = ""
        if page_count_hint > 0:
            page_instruction = f"\n目标页数: {page_count_hint}页左右。"

        warning_block = ""
        if warnings_text:
            warning_block = f"""
## 数据一致性警告
{warnings_text}
请在大纲中回避或标注这些不一致的数据。
"""

        # 场景化叙事框架
        framework_name, framework_desc = self.SCENARIO_FRAMEWORKS.get(
            scenario,
            ("根据材料内容自动选择最合适的叙事框架", "可选SCR/SCQA/AIDA/Issue Tree等，选择最匹配材料性质的框架"),
        )

        scenario_block = ""
        if scenario:
            scenario_block = f"\n## 汇报场景\n{scenario}\n"

        return f"""你是一位顶级咨询公司（麦肯锡/BCG级别）的PPT结构设计师。
请根据以下材料，设计一份专业PPT的页面级大纲。

## 设计原则（金字塔原理）
1. **结论先行**：每页必须有明确的takeaway（核心论点），写在页面顶部
2. **MECE**：页面之间不重叠、不遗漏
3. **逻辑递进**：整体遵循 **{framework_name}** 叙事框架 — {framework_desc}
4. **数据驱动**：充分利用提供的派生指标，让数据支撑论点
5. **可操作性**：每页的supporting_hint要具体，便于后续内容填充

## 结构 / 信息密度硬约束（违反将被自动修正）
- takeaway_message **必须 ≤ 40 个汉字**（含数据），且为完整判断句，禁止用"…的分析"这类短语
- 整套大纲应包含且仅包含一张 title、一张 agenda、若干 content/data/comparison/diagram、最后 1-2 张 summary
- 每 3-5 张内容页之前应插入一张 section_divider，标注章节名（不计入正文 slide）
- 单页内的论据数量预估在 supporting_hint 中体现：
  - content 页：最多 3 个 level-0 论据
  - comparison 页：每边最多 4 个论据
  - data 页：最多 1 张主图 + 1 段 so-what
- 严禁产出空白论据页：supporting_hint 必须列出至少 2 条具体的事实/数据来源

## 标题
{title or '（根据材料自拟）'}
{scenario_block}
## 目标受众
{target_audience}

### 受众适配要求（必须严格遵守）
根据目标受众调整叙事策略和信息密度：
- **CEO/高管层**：聚焦战略决策和关键指标，减少操作细节，每页不超过3个核心数据点，强调"所以呢"（So What），用结论驱动而非过程驱动
- **执行团队**：平衡战略与执行细节，包含关键里程碑、责任分工、时间节点，数据深度中等
- **客户/投资者**：突出价值和成果，用案例和ROI数据说话，弱化内部流程，强调差异化优势
- **内部团队/培训**：详细操作流程和知识点，每页信息密度可以更高，包含具体步骤和注意事项
- **管理层（默认）**：兼顾战略和执行，信息密度适中，结论先行但保留关键支撑数据

叙事逻辑的深度和广度必须匹配受众：高层看结论，执行看细节，客户看价值。
{page_instruction}

## 原始材料
{text_preview}

## 数据表格概要
{table_summary}

## 计算得到的派生指标
{metrics_text}

## 关键发现
{findings_text}

## 数据缺失建议
{gaps_text}
{warning_block}
## 输出要求
返回JSON对象，格式如下：
```json
{{
  "narrative_logic": "整体叙事逻辑的简述，须使用{framework_name}框架组织",
  "items": [
    {{
      "page_number": 1,
      "slide_type": "title",
      "takeaway_message": "封面页标题/副标题",
      "supporting_hint": "封面信息",
      "data_source": "",
      "primary_visual": "text_only"
    }},
    {{
      "page_number": 2,
      "slide_type": "content",
      "takeaway_message": "该页的核心论点（一句完整判断句，包含关键数据）",
      "supporting_hint": "该页需要什么论据、图表、对比来支撑takeaway",
      "data_source": "引用的数据来源，如'Sheet1: 季度收入表'",
      "primary_visual": "visual_block"
    }},
    {{
      "page_number": 3,
      "slide_type": "data",
      "takeaway_message": "...",
      "supporting_hint": "...",
      "data_source": "...",
      "primary_visual": "chart"
    }}
  ],
  "data_gap_suggestions": [
    "建议补充XXX数据以增强第N页论证",
    "建议补充YYY数据以支撑结论"
  ]
}}
```

### slide_type 说明
- "title": 封面页（仅 1 页）
- "agenda": 目录/议程页（仅 1 页）
- "section_divider": 章节过渡页（每 3-5 张内容页前 1 张，takeaway 写章节名）
- "content": 文字为主的内容页
- "data": 数据/图表为主的内容页
- "diagram": 流程图/架构图/关系图页
- "comparison": 对比分析页
- "summary": 总结/建议页（1-2 页）

### primary_visual 说明（每页必须且只能选一种，决定该页的视觉呈现方式）
- "chart": 有定量数据对比/趋势/占比时选择 → 生成数据图表
- "diagram": 需要流程图/架构图/关系图/框架图时选择 → 生成概念图
- "visual_block": 适合用KPI卡片/步骤卡/对比栏/图标网格呈现时选择 → 生成可视化块
- "text_only": 纯论述文字，无需可视化时选择
**强制规则**: slide_type为"data"必须选"chart"，"diagram"必须选"diagram"，"title"/"agenda"/"section_divider"必须选"text_only"
**多样性**: 避免连续3页以上使用相同的primary_visual，保持视觉多样性

### 质量标准
- takeaway_message 必须是**完整的判断句**，不是标题短语
  - 好的示例："2024年收入增长32%至15.6亿，连续三年保持20%以上增速"
  - 差的示例："收入增长趋势"
- 每页的 supporting_hint 要足够具体，让下一步内容生成无需重新理解材料
- 页数通常在8-15页之间，封面+目录+总结是固定页，核心论证页5-10页
- 确保整体叙事有清晰的起承转合

只输出JSON，不要其他文字。"""

    def _summarize_tables(self, raw_content: RawContent) -> str:
        """将表格转为简要文本"""
        if not raw_content.tables:
            return "（无表格数据）"

        parts = []
        for i, table in enumerate(raw_content.tables):
            sheet = table.source_sheet or f"表格{i+1}"
            col_info = f"列: {', '.join(table.headers[:8])}"
            row_info = f"{len(table.rows)}行"
            # 前两行预览
            preview = ""
            if table.rows:
                for row in table.rows[:2]:
                    cells = [str(c)[:20] if c else "" for c in row[:6]]
                    preview += f"  | {' | '.join(cells)} |\n"
            parts.append(f"**{sheet}** ({row_info}, {col_info})\n{preview}")

        return "\n".join(parts)

    def _format_metrics(self, analysis: AnalysisResult) -> str:
        """精选最有说服力的指标"""
        if not analysis.derived_metrics:
            return "（无派生指标）"

        # 优先选增长率、占比、排名等有说服力的指标
        priority_types = {"yoy_growth", "qoq_growth", "cagr", "ratio", "rank", "trend"}
        priority = []
        others = []
        for m in analysis.derived_metrics:
            if m.metric_type.value in priority_types:
                priority.append(m)
            else:
                others.append(m)

        selected = priority[:15]
        if len(selected) < 15:
            selected.extend(others[:15 - len(selected)])

        lines = []
        for m in selected:
            line = f"- {m.name}: {m.formatted_value}"
            if m.context:
                line += f" ({m.context})"
            lines.append(line)

        if len(analysis.derived_metrics) > len(selected):
            lines.append(f"... 共{len(analysis.derived_metrics)}个指标")

        return "\n".join(lines)

    # ================================================================
    # 响应解析
    # ================================================================

    def _parse_response(self, text: str) -> OutlineResult:
        """解析LLM返回的JSON"""
        data = self._extract_json(text)
        if data is None:
            preview = text[:500] if text else "(空)"
            raise RuntimeError(
                f"无法解析LLM返回的大纲JSON (响应{len(text)}字)\n前500字: {preview}"
            )

        narrative_logic = data.get("narrative_logic", "")
        items = []
        for item_data in data.get("items", []):
            items.append(OutlineItem(
                page_number=item_data.get("page_number", len(items) + 1),
                slide_type=item_data.get("slide_type", "content"),
                takeaway_message=item_data.get("takeaway_message", ""),
                supporting_hint=item_data.get("supporting_hint", ""),
                data_source=item_data.get("data_source", ""),
                primary_visual=item_data.get("primary_visual", ""),
            ))

        gap_suggestions = data.get("data_gap_suggestions", [])
        if isinstance(gap_suggestions, list):
            gap_suggestions = [str(g) for g in gap_suggestions]
        else:
            gap_suggestions = []

        return OutlineResult(
            narrative_logic=narrative_logic,
            items=items,
            data_gap_suggestions=gap_suggestions,
        )

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        多策略 LLM 输出 → JSON 提取，按"代价从低到高"依次尝试：
        1) 直接 json.loads
        2) 从 ```json ... ``` 代码块抽取（取第一个 ``` 到最后一个 ``` 的最大块，
           兼容嵌套示例与缺失闭合标记）
        3) 从首个 '{' 到匹配的 '}' 暴力提取
        4) 对每一种候选都尝试 LLM-JSON 修复（去 BOM、去尾随逗号、智能引号、单行注释等）
        """
        text = (text or "").strip().lstrip("\ufeff")  # 去 BOM

        # DeepSeek-R1: 去掉 <think>...</think>
        if '<think' in text:
            text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text,
                          flags=re.DOTALL).strip()

        candidates: list[str] = []

        # 候选 1：原文
        candidates.append(text)

        # 候选 2：``` 代码块（取第一个 ``` 到最后一个 ``` 之间最大块；
        # 容忍只有开头 ``` 没有结尾的情况）
        first_fence = re.search(r'```(?:json|JSON)?\s*\n?', text)
        if first_fence:
            inner_start = first_fence.end()
            last_fence = text.rfind('```')
            if last_fence > inner_start:
                candidates.append(text[inner_start:last_fence].strip())
            else:
                candidates.append(text[inner_start:].strip())

        # 候选 3：暴力大括号匹配（首个 { 到最后一个 }）
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            candidates.append(text[first_brace:last_brace + 1])

        # 依次尝试每个候选 → 直接解析 → 修复后解析 → 修复未转义引号
        for cand in candidates:
            cand = cand.strip()
            if not cand:
                continue
            parsed = self._try_parse_json(cand)
            if parsed is not None:
                return parsed
            repaired = self._repair_llm_json(cand)
            if repaired != cand:
                parsed = self._try_parse_json(repaired)
                if parsed is not None:
                    return parsed
            quote_fixed = self._fix_unescaped_quotes(repaired)
            if quote_fixed != repaired:
                parsed = self._try_parse_json(quote_fixed)
                if parsed is not None:
                    return parsed

        return None

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict]:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _repair_llm_json(text: str) -> str:
        """
        修复常见的 LLM JSON 输出问题：
        - 去掉单行 // 注释 和 /* */ 块注释
        - 把 } / ] 之前的尾随逗号去掉
        - 把智能引号 “ ” ‘ ’ 替换成普通引号
        - 把字符串内字面换行替换为 \\n（保守起见仅在被 " " 包围时处理）
        """
        s = text
        # 智能引号
        s = (s.replace("\u201c", '"').replace("\u201d", '"')
             .replace("\u2018", "'").replace("\u2019", "'"))
        # 块注释 /* ... */
        s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
        # 行注释 // ...  （注意：必须避开 URL 中的 ://）
        s = re.sub(r'(?<!:)//[^\n]*', '', s)
        # 尾随逗号：',\s*}' → '}', ',\s*]' → ']'
        s = re.sub(r',(\s*[}\]])', r'\1', s)
        return s.strip()

    @staticmethod
    def _fix_unescaped_quotes(text: str) -> str:
        """
        修复 JSON 字符串值内的未转义双引号。
        状态机遍历：在字符串内部遇到 " 时，如果后面跟的不是 JSON 结构字符
        （, : } ]）则转义为 \\"。
        """
        result = []
        i = 0
        in_string = False
        n = len(text)

        while i < n:
            ch = text[i]

            if not in_string:
                result.append(ch)
                if ch == '"':
                    in_string = True
                i += 1
                continue

            # 在字符串内
            if ch == '\\' and i + 1 < n:
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue

            if ch == '"':
                # 看后面的非空白字符判断这是否为字符串结尾
                j = i + 1
                while j < n and text[j] in ' \t\r\n':
                    j += 1
                next_ch = text[j] if j < n else ''
                if next_ch in ('', ',', ':', '}', ']'):
                    result.append('"')
                    in_string = False
                else:
                    result.append('\\"')
                i += 1
                continue

            if ch == '\n':
                result.append('\\n')
                i += 1
                continue

            result.append(ch)
            i += 1

        return ''.join(result)

    # ================================================================
    # 质量校验
    # ================================================================

    def _validate(self, result: OutlineResult):
        """校验大纲质量"""
        if not result.items:
            raise RuntimeError("大纲为空，至少需要封面页和1页内容")

        # 检查页码连续性
        page_numbers = [item.page_number for item in result.items]
        expected = list(range(1, len(result.items) + 1))
        if page_numbers != expected:
            # 修正页码
            for i, item in enumerate(result.items):
                item.page_number = i + 1

        # 检查第一页是否为title
        if result.items[0].slide_type != "title":
            result.items[0].slide_type = "title"

        # 检查takeaway质量
        # - 最少 5 字，不能只是短语
        # - 最多 40 字（与 prompt 硬约束保持一致），超长截断并末尾加省略
        VALID_TYPES = {
            "title", "agenda", "section_divider", "content", "data",
            "diagram", "comparison", "timeline", "matrix", "summary", "appendix",
        }
        for item in result.items:
            if item.slide_type not in VALID_TYPES:
                item.slide_type = "content"
            if item.slide_type == "title":
                continue
            msg = item.takeaway_message or ""
            if len(msg) < 5:
                msg = "（待补充核心论点）"
            elif len(msg) > 40:
                msg = msg[:38] + "…"
            item.takeaway_message = msg

    # ================================================================
    # 后验推断：确保每个 item 都有有效的 primary_visual
    # ================================================================

    VALID_PRIMARY_VISUALS = {"chart", "diagram", "visual_block", "text_only"}

    # slide_type → 强制 primary_visual 映射
    FORCED_VISUAL = {
        "title": "text_only",
        "agenda": "text_only",
        "section_divider": "text_only",
        "data": "chart",
        "diagram": "diagram",
    }

    # supporting_hint 关键词 → primary_visual
    HINT_KEYWORDS = {
        "chart": ["图表", "柱状图", "折线图", "饼图", "趋势", "占比", "增长率", "chart"],
        "diagram": ["流程", "架构", "关系图", "因果", "拓扑", "组织结构", "diagram", "flowchart"],
        "visual_block": ["KPI", "卡片", "步骤", "对比", "网格", "指标", "highlight"],
    }

    def _assign_primary_visual(self, result: OutlineResult):
        """后验推断：确保每个 OutlineItem 都有有效的 primary_visual"""
        for item in result.items:
            # 已有有效值 → 只做强制规则覆盖
            if item.primary_visual in self.VALID_PRIMARY_VISUALS:
                forced = self.FORCED_VISUAL.get(item.slide_type)
                if forced:
                    item.primary_visual = forced
                continue

            # 无值或无效值 → 推断
            forced = self.FORCED_VISUAL.get(item.slide_type)
            if forced:
                item.primary_visual = forced
                continue

            # 按 supporting_hint 关键词推断
            hint = (item.supporting_hint or "").lower()
            matched = False
            for pv, keywords in self.HINT_KEYWORDS.items():
                if any(kw in hint for kw in keywords):
                    item.primary_visual = pv
                    matched = True
                    break

            if not matched:
                # 有 data_source → chart；否则 visual_block（比 text_only 视觉更丰富）
                if item.data_source:
                    item.primary_visual = "chart"
                else:
                    item.primary_visual = "visual_block"
