"""
ChartSpec构建器 - 使用LLM从文本提取图表数据
"""
import json
import re
from typing import Optional
from models import (SlideSpec, ChartSpec, ChartType, ChartSeries,
                    InsightSpec, ChartAnnotation, VisualEmphasis)
from llm_client.glm_client import GLMClient


class ChartSpecBuilder:
    """从slide文本内容中提取数据，构建ChartSpec"""

    def __init__(self, llm_client: GLMClient, enriched_tables=None):
        self.llm = llm_client
        self.enriched_tables = enriched_tables or []

    def build_from_slide(self, slide: SlideSpec, chart_type: ChartType,
                         theme_colors: list[str]) -> Optional[ChartSpec]:
        """从slide内容构建ChartSpec"""
        # 1. LLM提取数据
        chart_data = self._extract_chart_data(slide, chart_type)
        if not chart_data:
            return None

        # 2. 组装ChartSpec
        categories = chart_data.get("categories", [])
        series_data = chart_data.get("series", [])
        so_what = chart_data.get("so_what", "")
        insights_raw = chart_data.get("key_insights", [])

        # 构建ChartSeries
        series_list = []
        for i, s in enumerate(series_data):
            color = theme_colors[i % len(theme_colors)] if theme_colors else ""
            series_list.append(ChartSeries(
                name=s.get("name", f"系列{i+1}"),
                values=[float(v) for v in s.get("values", [])],
                color=color,
            ))

        # 构建InsightSpec
        insights = []
        for ins in insights_raw[:3]:
            try:
                insights.append(InsightSpec(
                    data_point=(str(ins.get("label", "")), float(ins.get("value", 0))),
                    insight_text=ins.get("insight_text", ""),
                    emphasis=VisualEmphasis.ANNOTATION,
                ))
            except (ValueError, TypeError):
                continue

        return ChartSpec(
            chart_type=chart_type,
            categories=categories,
            series=series_list,
            so_what=so_what,
            key_insights=insights,
            title=chart_data.get("title", slide.takeaway_message),
            show_legend=len(series_list) > 1,
            show_data_labels=len(categories) <= 8,
        )

    def _extract_chart_data(self, slide: SlideSpec, chart_type: ChartType) -> Optional[dict]:
        """使用LLM从文本中提取图表数据"""
        text_content = self._format_text_blocks(slide)
        table_section = self._format_enriched_tables()

        prompt = f"""你是一个数据分析专家。请从以下PPT页面内容中提取适合制作{chart_type.value}图表的结构化数据。

## 页面标题
{slide.takeaway_message}

## 页面文本内容
{text_content}
{table_section}
## 要求
1. categories和series的数字必须完全来自原始表格数据，严禁编造
2. 生成1-2个数据系列（series）
3. 为图表生成一个"so what"结论（一句话概括）
4. 生成1-3个key_insights

## 输出格式（纯JSON，不要markdown标记）
{{
  "title": "图表标题",
  "categories": ["类别1", "类别2", "类别3", "类别4"],
  "series": [
    {{"name": "系列名", "values": [数值1, 数值2, 数值3, 数值4]}}
  ],
  "so_what": "一句话结论",
  "key_insights": [
    {{"label": "类别名", "value": 数值, "insight_text": "洞察说明"}}
  ]
}}

请直接输出JSON。"""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            return self._parse_json(response)
        except Exception as e:
            print(f"⚠️ LLM提取图表数据失败: {e}")
            return self._fallback_extract(slide)

    def _format_text_blocks(self, slide: SlideSpec) -> str:
        lines = []
        for block in slide.text_blocks:
            prefix = "- " if block.level == 0 else "  - "
            lines.append(f"{prefix}{block.content}")
        return "\n".join(lines)

    def _format_enriched_tables(self) -> str:
        """将enriched_tables格式化为prompt中的表格数据段"""
        if not self.enriched_tables:
            return ""
        blocks = []
        for et in self.enriched_tables[:3]:
            t = et.original
            if not t.headers:
                continue
            header_line = " | ".join(str(h) for h in t.headers[:8])
            rows_preview = []
            for row in t.rows[:8]:
                cells = [str(c)[:15] if c is not None else "" for c in row[:8]]
                rows_preview.append(" | ".join(cells))
            blocks.append(f"## 原始表格({t.source_sheet or '表'})\n{header_line}\n" + "\n".join(rows_preview))
        if not blocks:
            return ""
        return "\n## 原始表格数据（categories和values必须完全来自这里）\n" + "\n\n".join(blocks) + "\n"

    def _parse_json(self, text: str) -> Optional[dict]:
        """解析LLM返回的JSON（容错处理）"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            match = re.search(r'\{[\s\S]+\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    def _fallback_extract(self, slide: SlideSpec) -> Optional[dict]:
        """降级策略：用正则从文本中提取数字"""
        text = " ".join(b.content for b in slide.text_blocks)
        numbers = re.findall(r'(\d+\.?\d*)\s*[%％]?', text)

        if len(numbers) < 2:
            return None

        values = [float(n) for n in numbers[:6]]
        categories = [f"类别{i+1}" for i in range(len(values))]

        return {
            "title": slide.takeaway_message,
            "categories": categories,
            "series": [{"name": "数据", "values": values}],
            "so_what": slide.takeaway_message,
            "key_insights": [],
        }
