"""
数据分析引擎 — Pipeline analyze阶段

静默执行，为outline阶段提供丰富的数据素材。
纯代码计算派生指标（精确），LLM辅助提取关键发现和数据gap。
"""

import json
import math
import re
from typing import Optional

from models.slide_spec import (
    AnalysisResult, DerivedMetric, MetricType, DataGapSuggestion,
    ValidationWarning, EnrichedTableData, RawContent, TableData,
)
from llm_client.base import LLMClient, LLMResponse


class DataAnalyzer:
    """数据分析引擎"""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm

    def analyze(self, raw_content: RawContent) -> AnalysisResult:
        """
        完整分析流程：
        1. 纯代码计算派生指标（精确）
        2. 数据一致性校验
        3. LLM辅助提取关键发现和数据gap
        """
        # Step 1: 计算派生指标
        all_metrics = []
        enriched_tables = []
        for table in raw_content.tables:
            metrics, enriched = self._analyze_table(table)
            all_metrics.extend(metrics)
            enriched_tables.append(enriched)

        # Step 2: 数据一致性校验
        warnings = self._validate_consistency(raw_content)

        # Step 3: LLM辅助分析（如果有LLM客户端）
        key_findings = []
        data_gaps = []
        if self.llm:
            key_findings = self._extract_key_findings(raw_content, all_metrics)
            data_gaps = self._identify_data_gaps(raw_content, all_metrics)

        return AnalysisResult(
            derived_metrics=all_metrics,
            key_findings=key_findings,
            data_gaps=data_gaps,
            validation_warnings=warnings,
            enriched_tables=enriched_tables,
        )

    # ================================================================
    # 纯代码计算（不用LLM，避免幻觉）
    # ================================================================

    def _analyze_table(self, table: TableData) -> tuple[list[DerivedMetric], EnrichedTableData]:
        """分析单个表格，返回派生指标和增强表格"""
        metrics = []
        enriched = EnrichedTableData(original=table)

        if not table.headers or not table.rows:
            return metrics, enriched

        # 识别列类型
        numeric_cols = self._find_numeric_columns(table)
        time_col = self._find_time_column(table)
        category_col = self._find_category_column(table, numeric_cols, time_col)

        for col_idx, col_name in numeric_cols:
            values = self._extract_numeric_values(table, col_idx)
            if not values:
                continue

            # 基础统计
            metrics.extend(self._compute_basic_stats(
                values, col_name, table.source_sheet))

            # 时间序列指标
            if time_col is not None:
                time_labels = [str(row[time_col]) for row in table.rows
                               if row[time_col] is not None]
                metrics.extend(self._compute_time_series_metrics(
                    values, time_labels, col_name, table.source_sheet))

            # 分组占比
            if category_col is not None:
                categories = [str(row[category_col]) for row in table.rows
                              if row[category_col] is not None]
                metrics.extend(self._compute_category_metrics(
                    values, categories, col_name, table.source_sheet))

            # 存入enriched summary
            enriched.summary[col_name] = {
                "total": sum(values),
                "avg": sum(values) / len(values),
                "max": max(values),
                "min": min(values),
                "count": len(values),
            }

        return metrics, enriched

    def _compute_basic_stats(
        self, values: list[float], col_name: str, sheet: str
    ) -> list[DerivedMetric]:
        """计算基础统计指标"""
        metrics = []
        total = sum(values)
        avg = total / len(values)
        max_val = max(values)
        min_val = min(values)

        metrics.append(DerivedMetric(
            metric_type=MetricType.TOTAL, name=f"{col_name}合计",
            value=total, formatted_value=self._format_number(total),
            source_table=sheet, source_column=col_name,
        ))
        metrics.append(DerivedMetric(
            metric_type=MetricType.AVERAGE, name=f"{col_name}平均值",
            value=avg, formatted_value=self._format_number(avg),
            source_table=sheet, source_column=col_name,
        ))
        metrics.append(DerivedMetric(
            metric_type=MetricType.MAX, name=f"{col_name}最大值",
            value=max_val, formatted_value=self._format_number(max_val),
            source_table=sheet, source_column=col_name,
        ))
        metrics.append(DerivedMetric(
            metric_type=MetricType.MIN, name=f"{col_name}最小值",
            value=min_val, formatted_value=self._format_number(min_val),
            source_table=sheet, source_column=col_name,
        ))

        if len(values) > 1:
            mean = avg
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            stddev = math.sqrt(variance)
            metrics.append(DerivedMetric(
                metric_type=MetricType.STDDEV, name=f"{col_name}标准差",
                value=stddev, formatted_value=self._format_number(stddev),
                source_table=sheet, source_column=col_name,
            ))

        return metrics

    def _compute_time_series_metrics(
        self, values: list[float], time_labels: list[str],
        col_name: str, sheet: str
    ) -> list[DerivedMetric]:
        """计算时间序列指标"""
        metrics = []
        n = min(len(values), len(time_labels))
        if n < 2:
            return metrics

        # 环比增长率（相邻期）
        for i in range(1, n):
            if values[i - 1] != 0:
                qoq = (values[i] - values[i - 1]) / abs(values[i - 1])
                metrics.append(DerivedMetric(
                    metric_type=MetricType.QOQ_GROWTH,
                    name=f"{col_name} {time_labels[i]}环比增长",
                    value=qoq,
                    formatted_value=f"{qoq * 100:.1f}%",
                    source_table=sheet, source_column=col_name,
                    context=f"从{self._format_number(values[i-1])}到{self._format_number(values[i])}",
                ))

        # 总体增长率（首尾）
        if values[0] != 0:
            total_growth = (values[-1] - values[0]) / abs(values[0])
            metrics.append(DerivedMetric(
                metric_type=MetricType.YOY_GROWTH,
                name=f"{col_name}总增长率({time_labels[0]}→{time_labels[-1]})",
                value=total_growth,
                formatted_value=f"{total_growth * 100:.1f}%",
                source_table=sheet, source_column=col_name,
                context=f"从{self._format_number(values[0])}到{self._format_number(values[-1])}",
            ))

        # CAGR（如果跨度>=2期）
        if n >= 3 and values[0] > 0 and values[-1] > 0:
            cagr = (values[-1] / values[0]) ** (1.0 / (n - 1)) - 1
            metrics.append(DerivedMetric(
                metric_type=MetricType.CAGR,
                name=f"{col_name} CAGR ({n-1}期)",
                value=cagr,
                formatted_value=f"{cagr * 100:.1f}%",
                source_table=sheet, source_column=col_name,
            ))

        # 趋势方向
        increasing = sum(1 for i in range(1, n) if values[i] > values[i - 1])
        trend_ratio = increasing / (n - 1)
        if trend_ratio >= 0.7:
            trend = "上升"
        elif trend_ratio <= 0.3:
            trend = "下降"
        else:
            trend = "波动"
        metrics.append(DerivedMetric(
            metric_type=MetricType.TREND,
            name=f"{col_name}趋势",
            value=trend_ratio,
            formatted_value=trend,
            source_table=sheet, source_column=col_name,
        ))

        return metrics

    def _compute_category_metrics(
        self, values: list[float], categories: list[str],
        col_name: str, sheet: str
    ) -> list[DerivedMetric]:
        """计算分类相关指标"""
        metrics = []
        n = min(len(values), len(categories))
        if n < 2:
            return metrics

        total = sum(values[:n])
        if total == 0:
            return metrics

        # 各类占比
        for i in range(n):
            ratio = values[i] / total
            metrics.append(DerivedMetric(
                metric_type=MetricType.RATIO,
                name=f"{categories[i]}占{col_name}比重",
                value=ratio,
                formatted_value=f"{ratio * 100:.1f}%",
                source_table=sheet, source_column=col_name,
            ))

        # 排名 (Top-3)
        indexed = sorted(enumerate(values[:n]), key=lambda x: x[1], reverse=True)
        for rank, (idx, val) in enumerate(indexed[:3], 1):
            metrics.append(DerivedMetric(
                metric_type=MetricType.RANK,
                name=f"{col_name}排名第{rank}: {categories[idx]}",
                value=val,
                formatted_value=self._format_number(val),
                source_table=sheet, source_column=col_name,
            ))

        # HHI集中度
        hhi = sum((v / total * 100) ** 2 for v in values[:n])
        metrics.append(DerivedMetric(
            metric_type=MetricType.HHI,
            name=f"{col_name} HHI集中度",
            value=hhi,
            formatted_value=f"{hhi:.0f}",
            source_table=sheet, source_column=col_name,
            context="HHI>2500为高度集中，1500-2500为中度集中",
        ))

        return metrics

    # ================================================================
    # 数据一致性校验
    # ================================================================

    def _validate_consistency(self, raw_content: RawContent) -> list[ValidationWarning]:
        """检查正文数字与表格数据是否一致"""
        warnings = []
        if not raw_content.raw_text or not raw_content.tables:
            return warnings

        # 从正文提取数字 (带上下文)
        text_numbers = self._extract_numbers_from_text(raw_content.raw_text)

        # 从表格提取数字
        table_numbers = set()
        for table in raw_content.tables:
            for row in table.rows:
                for cell in row:
                    if isinstance(cell, (int, float)) and cell != 0:
                        table_numbers.add(round(cell, 2))

        # 对比：正文中的数字是否在表格中有近似值
        for text_num, context in text_numbers:
            # 查找近似匹配（允许1%误差）
            close_matches = [
                t for t in table_numbers
                if t != 0 and abs(text_num - t) / abs(t) < 0.01 and text_num != t
            ]
            # 如果有非常接近但不完全相等的值，发出警告
            # （完全相等说明一致，差距大说明可能是不同数据）
            if close_matches:
                for match in close_matches:
                    if abs(text_num - match) > 0.001:  # 不是精度误差
                        warnings.append(ValidationWarning(
                            message=f"正文提到\"{context}\"={text_num}，表格中为{match}，请确认",
                            text_value=str(text_num),
                            table_value=str(match),
                        ))

        return warnings

    # ================================================================
    # LLM辅助分析
    # ================================================================

    def _extract_key_findings(
        self, raw_content: RawContent, metrics: list[DerivedMetric]
    ) -> list[str]:
        """LLM提取关键发现"""
        if not self.llm:
            return []

        metrics_text = self._format_metrics_for_prompt(metrics[:30])  # 限制数量
        text_preview = raw_content.raw_text[:3000]

        prompt = f"""分析以下材料和数据指标，提取3-5个最重要的发现。
每个发现必须是完整的判断句，包含具体数字。

## 原始材料（前3000字）
{text_preview}

## 计算得到的数据指标
{metrics_text}

## 输出要求
返回JSON数组，每个元素是一个发现字符串。只输出JSON，不要其他文字。
示例: ["收入同比增长32%至15.6亿元，连续三年保持20%以上增速", "华东区贡献47%收入但增速放缓至15%"]
"""
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1024)
        if not response.success:
            return []

        return self._parse_json_array(response.content)

    def _identify_data_gaps(
        self, raw_content: RawContent, metrics: list[DerivedMetric]
    ) -> list[DataGapSuggestion]:
        """LLM识别数据gap"""
        if not self.llm:
            return []

        metrics_text = self._format_metrics_for_prompt(metrics[:20])
        text_preview = raw_content.raw_text[:2000]

        prompt = f"""分析以下材料，识别缺失但对做PPT论证很重要的数据。
不要建议已有的数据，只关注真正缺失的。

## 材料
{text_preview}

## 已有数据指标
{metrics_text}

## 输出要求
返回JSON数组，每个元素格式:
{{"gap": "缺失的数据描述", "reason": "为什么需要这个数据", "importance": "high/medium/low"}}

最多输出5个建议。只输出JSON，不要其他文字。
"""
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=1024)
        if not response.success:
            return []

        items = self._parse_json_array(response.content)
        return [
            DataGapSuggestion(
                gap_description=item.get("gap", ""),
                reason=item.get("reason", ""),
                importance=item.get("importance", "medium"),
            )
            for item in items
            if isinstance(item, dict) and item.get("gap")
        ]

    # ================================================================
    # 微型分析（补充数据用）
    # ================================================================

    def micro_analyze(
        self, text_data: str = "", tables: Optional[list[TableData]] = None
    ) -> AnalysisResult:
        """对补充数据做轻量分析"""
        metrics = []
        enriched_tables = []

        if tables:
            for table in tables:
                m, e = self._analyze_table(table)
                metrics.extend(m)
                enriched_tables.append(e)

        return AnalysisResult(
            derived_metrics=metrics,
            enriched_tables=enriched_tables,
        )

    # ================================================================
    # 辅助方法
    # ================================================================

    def _find_numeric_columns(self, table: TableData) -> list[tuple[int, str]]:
        """识别数值列（超过50%的行是数字）"""
        result = []
        for col_idx, header in enumerate(table.headers):
            numeric_count = 0
            for row in table.rows:
                if col_idx < len(row):
                    val = row[col_idx]
                    if isinstance(val, (int, float)):
                        numeric_count += 1
                    elif isinstance(val, str):
                        try:
                            cleaned = val.replace(",", "").replace("%", "").replace("亿", "").replace("万", "").strip()
                            if cleaned:
                                float(cleaned)
                                numeric_count += 1
                        except ValueError:
                            pass
            if table.rows and numeric_count / len(table.rows) > 0.5:
                result.append((col_idx, header))
        return result

    def _find_time_column(self, table: TableData) -> Optional[int]:
        """识别时间列（包含年份、季度、月份等）"""
        time_patterns = [
            r'20\d{2}', r'Q[1-4]', r'[一二三四]季度',
            r'\d{1,2}月', r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec',
            r'年份|年度|季度|月份|日期|时间|period|year|quarter|month',
        ]
        for col_idx, header in enumerate(table.headers):
            # 检查表头
            for pattern in time_patterns:
                if re.search(pattern, header, re.IGNORECASE):
                    return col_idx
            # 检查第一行数据
            if table.rows and col_idx < len(table.rows[0]):
                val = str(table.rows[0][col_idx])
                for pattern in time_patterns:
                    if re.search(pattern, val, re.IGNORECASE):
                        return col_idx
        return None

    def _find_category_column(
        self, table: TableData, numeric_cols: list[tuple[int, str]],
        time_col: Optional[int]
    ) -> Optional[int]:
        """识别分类列（非数值、非时间的第一列）"""
        numeric_indices = {idx for idx, _ in numeric_cols}
        for col_idx, header in enumerate(table.headers):
            if col_idx not in numeric_indices and col_idx != time_col:
                return col_idx
        return None

    def _extract_numeric_values(self, table: TableData, col_idx: int) -> list[float]:
        """从表格列提取数值"""
        values = []
        for row in table.rows:
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            if isinstance(val, (int, float)):
                values.append(float(val))
            elif isinstance(val, str):
                try:
                    cleaned = val.replace(",", "").replace("%", "").strip()
                    multiplier = 1.0
                    if "亿" in val:
                        cleaned = cleaned.replace("亿", "")
                        multiplier = 1e8
                    elif "万" in val:
                        cleaned = cleaned.replace("万", "")
                        multiplier = 1e4
                    if cleaned:
                        values.append(float(cleaned) * multiplier)
                except ValueError:
                    pass
        return values

    def _extract_numbers_from_text(self, text: str) -> list[tuple[float, str]]:
        """从正文提取数字及其上下文"""
        results = []
        # 匹配常见数字格式
        patterns = [
            r'(\d+(?:\.\d+)?)\s*亿',
            r'(\d+(?:\.\d+)?)\s*万',
            r'(\d+(?:\.\d+)?)\s*%',
            r'(\d{1,3}(?:,\d{3})+(?:\.\d+)?)',  # 千分位数字
            r'(?<![.\d])(\d+\.\d+)(?![.\d%亿万])',  # 小数
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    num_str = match.group(1).replace(",", "")
                    val = float(num_str)
                    # 获取上下文
                    start = max(0, match.start() - 10)
                    end = min(len(text), match.end() + 5)
                    context = text[start:end].strip()
                    results.append((val, context))
                except ValueError:
                    pass
        return results

    def _format_number(self, val: float) -> str:
        """格式化数字为可读字符串"""
        abs_val = abs(val)
        if abs_val >= 1e8:
            return f"{val / 1e8:.1f}亿"
        elif abs_val >= 1e4:
            return f"{val / 1e4:.1f}万"
        elif abs_val >= 1:
            return f"{val:,.1f}"
        elif abs_val > 0:
            return f"{val:.2%}"
        return "0"

    def _format_metrics_for_prompt(self, metrics: list[DerivedMetric]) -> str:
        """将指标格式化为prompt文本"""
        lines = []
        for m in metrics:
            line = f"- {m.name}: {m.formatted_value}"
            if m.context:
                line += f" ({m.context})"
            lines.append(line)
        return "\n".join(lines) if lines else "（无计算指标）"

    def _parse_json_array(self, text: str) -> list:
        """解析LLM返回的JSON数组，含容错"""
        text = text.strip()

        # 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 提取 ```json ... ``` 代码块
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 提取第一个 [ ... ]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        return []
