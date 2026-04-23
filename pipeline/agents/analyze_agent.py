"""
AnalyzeAgent — ReActAgent
LLM读取文档，分析受众和汇报场景，输出策略框架 + 派生指标。

工具：
  - read_section(section_title): 读取文档指定章节
  - compute_table_metrics(table_index): 计算表格派生指标
  - submit_analysis(json): 提交最终分析结果

输出：AnalysisResult.to_dict()
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from .base import CodeAgent, ReActAgent, Tool, ValidationResult
from llm_client.base import ChatMessage

logger = logging.getLogger(__name__)


class AnalyzeAgent(ReActAgent):
    """
    策略分析 Agent。

    通过 ReAct 循环：
    1. 读取文档概要和关键章节
    2. 结合目标受众和汇报场景输出策略框架
    3. 调用代码工具计算派生指标
    4. 提交最终 AnalysisResult
    """

    max_iterations = 3
    max_validation_retries = 2
    temperature = 0.4
    max_tokens = 4096

    def __init__(self, llm_client):
        super().__init__(llm_client)
        self._context: Dict[str, Any] = {}

    @property
    def system_prompt(self) -> str:
        return """你是一位专业的战略分析师。文档内容已在用户消息中完整提供。

直接输出 JSON 分析结果，放在 ```json ... ``` 代码块中。不要说废话，直接输出 JSON。

格式：
```json
{
  "document_summary": "文档总结（50字以上）",
  "audience_analysis": "受众分析",
  "scenario_strategy": "叙事策略（SCR/SCQA等框架）",
  "core_themes": ["主题1", "主题2", "主题3"],
  "recommended_structure": "开篇→问题→分析→方案→行动",
  "key_messages": ["关键信息1", "关键信息2", "关键信息3"],
  "recommended_page_range": "12-18页"
}
```"""

    @property
    def tools(self) -> List[Tool]:
        # 不使用工具调用 — 直接让 LLM 输出 JSON 文本，通过 extract_output 解析
        return []

    def build_initial_messages(self, context: Dict[str, Any]) -> List[ChatMessage]:
        self._context = context
        task = context.get("task", {})
        raw = context.get("raw_content", {})

        target_audience = task.get("target_audience", "管理层")
        scenario = task.get("scenario", "")
        title = task.get("title", "未命名文档")

        source_pages = raw.get("source_pages", [])
        tables = raw.get("_tables", [])

        # 章节标题列表（不铺全文，避免 token 爆炸）
        section_lines = [
            f"  {i+1}. {sp.get('title', '')}（{len(sp.get('content',''))}字）"
            for i, sp in enumerate(source_pages[:25])
        ]
        sections_text = "\n".join(section_lines) if section_lines else "（无结构化章节）"

        # 文档前1500字作为内容概要
        raw_text = raw.get("_raw_text", "")
        doc_preview = raw_text[:1500] if raw_text else ""

        # 表格清单（只列表头，不铺行数据）
        table_lines = [
            f"  表格{i}: {t.get('source_sheet','表格')} ({len(t.get('rows',[]))}行) "
            f"| 字段: {', '.join(str(h) for h in t.get('headers',[])[:6])}"
            for i, t in enumerate(tables[:5])
        ]
        tables_text = "\n".join(table_lines) if table_lines else "（无数据表格）"

        user_msg = f"""请分析以下文档材料并制定PPT演讲策略。

**文档标题**: {title}
**目标受众**: {target_audience}
**汇报场景**: {scenario or "通用汇报"}

## 文档章节结构（共{len(source_pages)}个章节）
{sections_text}

## 文档内容概要（前1500字）
{doc_preview}

## 数据表格（共{len(tables)}个）
{tables_text}

---
请直接输出 JSON 格式的策略分析结果，放在 ```json ... ``` 代码块中。"""

        return [ChatMessage(role="user", content=user_msg)]

    def extract_output(self, messages: List[ChatMessage]) -> Dict:
        """从对话历史中找到 submit_analysis 的参数（最终输出）"""
        # 从 _submitted_analysis 中提取（由工具函数设置）
        if hasattr(self, "_submitted_analysis") and self._submitted_analysis:
            return self._submitted_analysis

        # 回退：从 LLM 文本中解析 JSON 对象
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content:
                result = self._parse_analysis_from_text(msg.content)
                if result:
                    logger.info("[AnalyzeAgent] 从文本回复中提取到策略分析")
                    self._tool_submit_analysis(
                        document_summary=result.get("document_summary", "文档摘要"),
                        audience_analysis=result.get("audience_analysis", "管理层"),
                        scenario_strategy=result.get("scenario_strategy", "标准汇报"),
                        core_themes=result.get("core_themes", ["核心主题"]),
                        recommended_structure=result.get("recommended_structure", "开篇→分析→结论"),
                        key_messages=result.get("key_messages", ["核心信息"]),
                        recommended_page_range=result.get("recommended_page_range", "12-16页"),
                    )
                    return self._submitted_analysis

        raise ValueError("未找到 submit_analysis 调用结果，请确认 Agent 已调用该工具")

    @staticmethod
    def _parse_analysis_from_text(text: str) -> Optional[Dict]:
        """从文本中提取包含策略分析字段的 JSON 对象"""
        import re
        patterns = [
            r'```json\s*(\{[\s\S]*?\})\s*```',
            r'```\s*(\{[\s\S]*?\})\s*```',
            r'(\{[\s\S]*"document_summary"[\s\S]*?\})',
            r'(\{[\s\S]*"core_themes"[\s\S]*?\})',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict) and ("document_summary" in data or "core_themes" in data):
                        return data
                except Exception:
                    continue
        return None

    def validate(self, output: Dict) -> ValidationResult:
        errors = []

        strategy = output.get("strategy", {})
        if not isinstance(strategy, dict):
            strategy = {}
            output["strategy"] = strategy

        core_themes = strategy.get("core_themes", [])
        key_messages = strategy.get("key_messages", [])
        document_summary = strategy.get("document_summary", "")

        # 致命错误：核心内容为空
        if not document_summary:
            errors.append("document_summary 不能为空")
        if not core_themes:
            errors.append("core_themes 不能为空")
        if not key_messages:
            errors.append("key_messages 不能为空")

        # 非致命字段：缺失时填入合理默认值，不触发重试
        if not strategy.get("recommended_page_range"):
            strategy["recommended_page_range"] = "12-16页"
            logger.warning("[AnalyzeAgent] recommended_page_range 缺失，使用默认值 '12-16页'")
        if not strategy.get("recommended_structure"):
            strategy["recommended_structure"] = "开篇→背景→分析→结论→建议"
            logger.warning("[AnalyzeAgent] recommended_structure 缺失，使用默认值")
        if not strategy.get("scenario_strategy"):
            strategy["scenario_strategy"] = "标准汇报结构"
        if not strategy.get("audience_analysis"):
            strategy["audience_analysis"] = strategy.get("core_themes", [""])[0] if core_themes else "管理层"

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def run(self, context: Dict[str, Any]) -> Dict:
        """运行 Agent，返回序列化的 AnalysisResult dict"""
        report = context.get("report_progress", lambda p, m: None)
        self._submitted_analysis = None

        report(16, "正在分析受众与策略...")
        result = super().run(context)

        report(27, "正在计算数据指标...")
        raw = context.get("raw_content", {})
        result = self._enrich_with_code_metrics(result, raw)

        # Chunk document for PlanAgent retrieval
        result["chunks"] = self._chunk_document(raw.get("source_pages", []))

        report(29, "策略分析完成")
        return result

    @staticmethod
    def _chunk_document(source_pages: List[Dict], chunk_chars: int = 600) -> List[Dict]:
        """Split source_pages into overlapping character-based chunks for PlanAgent reference."""
        chunks = []
        overlap = 80
        step = chunk_chars - overlap
        for page in source_pages:
            text = page.get("content", "")
            section = page.get("title", "")
            if not text.strip():
                continue
            # If text fits in one chunk, keep as-is
            if len(text) <= chunk_chars:
                chunk_id = "ch_" + hashlib.sha256(
                    (section + text[:50]).encode()
                ).hexdigest()[:8]
                chunks.append({"id": chunk_id, "section": section, "text": text})
                continue
            for i in range(0, len(text), step):
                chunk_text = text[i:i + chunk_chars]
                if not chunk_text.strip():
                    continue
                chunk_id = "ch_" + hashlib.sha256(
                    (section + str(i) + chunk_text[:30]).encode()
                ).hexdigest()[:8]
                chunks.append({"id": chunk_id, "section": section, "text": chunk_text})
        return chunks

    # ------------------------------------------------------------------
    # 工具函数实现
    # ------------------------------------------------------------------

    def _tool_read_overview(self) -> str:
        raw = self._context.get("raw_content", {})

        lines = ["=== 文档概要 ==="]

        # 章节列表
        source_pages = raw.get("source_pages", [])
        sections = raw.get("structured_sections", [])
        if source_pages:
            lines.append(f"\n【章节列表】共 {len(source_pages)} 个章节：")
            for sp in source_pages[:20]:
                title = sp.get("title", "")
                content_len = len(sp.get("content", ""))
                lines.append(f"  - {title}（{content_len}字）")
        elif sections:
            lines.append(f"\n【章节列表】共 {len(sections)} 个章节：")
            for s in sections[:20]:
                lines.append(f"  - {s.get('title', '')}（{s.get('level', 1)}级）")

        # 表格列表
        tables = raw.get("_tables", [])
        if tables:
            lines.append(f"\n【数据表格】共 {len(tables)} 个表格：")
            for i, t in enumerate(tables[:5]):
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                lines.append(f"  表格{i}: {t.get('source_sheet', '表格')} — {len(headers)}列 × {len(rows)}行，字段: {', '.join(headers[:5])}")

        # 文字摘要
        raw_text = raw.get("_raw_text", "")
        if raw_text:
            lines.append(f"\n【文字摘要（前1000字）】\n{raw_text[:1000]}")

        return "\n".join(lines)

    def _tool_read_section(self, section_title: str, max_chars: int = 2000) -> str:
        raw = self._context.get("raw_content", {})

        # 在 source_pages 中模糊匹配
        source_pages = raw.get("source_pages", [])
        for sp in source_pages:
            if section_title.lower() in (sp.get("title") or "").lower():
                content = sp.get("content", "")
                return f"【{sp['title']}】\n{content[:max_chars]}"

        # 在 structured_sections 中匹配
        sections = raw.get("structured_sections", [])
        for s in sections:
            if section_title.lower() in (s.get("title") or "").lower():
                content = s.get("content", "")
                return f"【{s['title']}】\n{content[:max_chars]}"

        return f"未找到标题包含 '{section_title}' 的章节"

    def _tool_compute_metrics(self, table_index: int) -> str:
        raw = self._context.get("raw_content", {})
        tables = raw.get("_tables", [])

        if table_index >= len(tables):
            return f"表格{table_index}不存在（共{len(tables)}个表格）"

        table = tables[table_index]
        headers = table.get("headers", [])
        rows = table.get("rows", [])

        if not rows:
            return f"表格{table_index}无数据行"

        # 简单的数值分析
        result_lines = [f"表格{table_index} 分析结果："]
        result_lines.append(f"列名: {', '.join(headers)}")
        result_lines.append(f"行数: {len(rows)}")

        # 对数值列计算简单统计
        for i, header in enumerate(headers[:8]):
            try:
                vals = []
                for row in rows:
                    if i < len(row):
                        v = row[i]
                        if isinstance(v, (int, float)):
                            vals.append(float(v))
                        elif isinstance(v, str):
                            v_clean = v.replace(",", "").replace("%", "").strip()
                            if v_clean:
                                vals.append(float(v_clean))
                if len(vals) >= 2:
                    result_lines.append(f"  {header}: 最小={min(vals):.2f}, 最大={max(vals):.2f}, 均值={sum(vals)/len(vals):.2f}")
                    if len(vals) >= 2:
                        change = vals[-1] - vals[0]
                        pct = change / vals[0] * 100 if vals[0] != 0 else 0
                        result_lines.append(f"    → 首尾变化: {change:+.2f} ({pct:+.1f}%)")
            except (ValueError, ZeroDivisionError):
                pass

        return "\n".join(result_lines)

    def _tool_submit_analysis(
        self,
        document_summary: str,
        audience_analysis: str,
        scenario_strategy: str,
        core_themes: List[str],
        recommended_structure: str,
        key_messages: List[str],
        recommended_page_range: str,
    ) -> str:
        """接收最终分析结果，存储并返回确认"""
        from models.slide_spec import StrategyInsight

        strategy = StrategyInsight(
            document_summary=document_summary,
            audience_analysis=audience_analysis,
            scenario_strategy=scenario_strategy,
            core_themes=core_themes,
            recommended_structure=recommended_structure,
            recommended_page_range=recommended_page_range,
            key_messages=key_messages,
        )

        self._submitted_analysis = {
            "strategy": {
                "document_summary": document_summary,
                "audience_analysis": audience_analysis,
                "scenario_strategy": scenario_strategy,
                "core_themes": core_themes,
                "recommended_structure": recommended_structure,
                "recommended_page_range": recommended_page_range,
                "key_messages": key_messages,
            },
            "derived_metrics": [],
            "key_findings": [],
            "data_gaps": [],
            "validation_warnings": [],
            "enriched_tables": [],
        }

        return f"分析结果已提交。识别到{len(core_themes)}个核心主题，{len(key_messages)}条关键信息。"

    # ------------------------------------------------------------------
    # 纯代码指标补充
    # ------------------------------------------------------------------

    def _enrich_with_code_metrics(self, result: Dict, raw: Dict) -> Dict:
        """用纯代码计算表格派生指标，不再调用LLM"""
        try:
            raw_content = self._rebuild_raw_content(raw)
            all_metrics = []
            enriched_tables = []

            for table in raw_content.tables:
                metrics, enriched = self._analyze_table_code(table)
                all_metrics.extend(metrics)
                enriched_tables.append(enriched)

            result["derived_metrics"] = all_metrics
            result["enriched_tables"] = enriched_tables

        except Exception as e:
            logger.warning(f"代码指标计算失败（非致命）: {e}")

        return result

    @staticmethod
    def _analyze_table_code(table) -> tuple:
        """纯代码分析单个表格，返回 (metrics_list, enriched_dict)"""
        from models.slide_spec import DerivedMetric, MetricType, EnrichedTableData

        headers = table.headers
        rows = table.rows
        metrics = []

        for col_idx, header in enumerate(headers[:8]):
            try:
                vals = []
                for row in rows:
                    if col_idx < len(row):
                        v = row[col_idx]
                        if isinstance(v, (int, float)):
                            vals.append(float(v))
                        elif isinstance(v, str):
                            v_clean = v.replace(",", "").replace("%", "").strip()
                            if v_clean:
                                vals.append(float(v_clean))
                if len(vals) >= 2:
                    change = vals[-1] - vals[0]
                    pct = change / vals[0] * 100 if vals[0] != 0 else 0
                    metrics.append({
                        "metric_type": MetricType.YOY_GROWTH.value,
                        "name": f"{header}增长率",
                        "value": round(pct, 2),
                        "formatted_value": f"{pct:+.1f}%",
                        "source_table": table.source_sheet,
                        "source_column": header,
                        "context": f"首行{vals[0]:.2f} → 末行{vals[-1]:.2f}",
                    })
            except (ValueError, ZeroDivisionError):
                pass

        summary_dict = {
            "sheet": table.source_sheet,
            "rows": len(rows),
            "columns": len(headers),
        }
        return metrics, {
            "original": {"headers": headers, "rows": rows, "source_sheet": table.source_sheet},
            "summary": summary_dict,
        }

    @staticmethod
    def _rebuild_raw_content(raw: Dict):
        from models.slide_spec import RawContent, TableData, SourcePage, StructuredSection

        tables = []
        for t in raw.get("_tables", []):
            tables.append(TableData(
                headers=t.get("headers", []),
                rows=t.get("rows", []),
                source_sheet=t.get("source_sheet", ""),
            ))

        source_pages = []
        for sp in raw.get("source_pages", []):
            source_pages.append(SourcePage(
                page_number=sp.get("page_number", 0),
                title=sp.get("title", ""),
                content=sp.get("content", ""),
            ))

        return RawContent(
            raw_text=raw.get("_raw_text", ""),
            source_type=raw.get("source_type", "text"),
            tables=tables,
            images=[],
            source_pages=source_pages,
            detected_language=raw.get("detected_language", "zh"),
            metadata=raw.get("_metadata", {}),
        )
