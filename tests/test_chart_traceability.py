"""
R2 regression test: chart data traceability validator (H4).

Ensures chart_suggestion numbers are traceable to source text ±5%.
If not traceable, must be explicitly marked as estimated.
"""
import pytest
from pydantic import ValidationError

from models.schemas import ContentSlideSchema
from models.schema_adapter import parse_slide

SOURCE_TEXT = """
2024 年金融行业大模型应用率达到 38%，同比增长 12 个百分点。
某银行案例：部署 AI 风控后欺诈拦截率提升至 92%，年节省成本约 1.5 亿元。
市场整体增速为 23%，预计 2025 年将突破 50% 渗透率。
"""


def _dense_blocks():
    """Blocks satisfying min_length=4 and density>=300."""
    return [
        {"type": "heading", "text": "综合分析报告：技术架构优化与市场表现的全面评估总结与深度分析"},
        {"type": "bullet", "text": "微服务架构改造完成后系统整体响应性能实现显著提升，核心接口平均响应时间从原先的八百毫秒大幅缩减至两百毫秒以内，P99尾延迟指标改善幅度达到百分之七十五以上，建议在下一阶段将此优化方案推广至全业务线", "level": 1},
        {"type": "bullet", "text": "华东区域市场份额连续三个季度保持稳步增长态势，从百分之十八提升至百分之二十四，成功超越主要竞争对手成为该区域市场排名第二的参与者，该增长趋势与渠道下沉策略和本地化运营投入密切相关联", "level": 1},
        {"type": "bullet", "text": "平台用户留存率和付费转化率双双创下历史最高纪录，月活跃用户规模突破一百二十万大关，充分验证了产品核心功能迭代升级与精细化用户运营双轮驱动策略的有效性与长期可持续发展潜力", "level": 1},
    ]


def _chart_data(**overrides):
    base = {
        "page_number": 5,
        "slide_type": "content",
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "categories": ["2023", "2024"],
            "series": [{"name": "应用率", "values": [38, 50]}],
            "so_what": "金融大模型应用率达到 38%，预计 2025 年突破 50%",
        },
        "text_blocks": _dense_blocks(),
    }
    base.update(overrides)
    return base


def test_chart_with_traceable_numbers_passes():
    data = _chart_data()
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
    )
    assert schema.primary_visual.value == "chart"


def test_chart_with_hallucinated_540pct_rejected():
    """Reproduces v4 bug: '+540%' not in source."""
    data = _chart_data(
        chart_suggestion={
            "chart_type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "攻击增长", "values": [540]}],
            "so_what": "数据投毒攻击同比增长 540%",
        }
    )
    with pytest.raises(ValidationError, match="traceability"):
        ContentSlideSchema.model_validate(
            data, context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
        )


def test_chart_with_hallucinated_1050pct_rejected():
    """Reproduces v4 bug: '+1050%' not in source."""
    data = _chart_data(
        chart_suggestion={
            "chart_type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "增长", "values": [1050]}],
            "so_what": "同比增长 1050%",
        }
    )
    with pytest.raises(ValidationError, match="traceability"):
        ContentSlideSchema.model_validate(
            data, context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
        )


def test_chart_marked_estimated_passes():
    """estimated=True bypasses traceability check."""
    data = _chart_data(
        chart_suggestion={
            "chart_type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "增长", "values": [540]}],
            "so_what": "基于行业平均估算 540%",
            "estimated": True,
        }
    )
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": "", "tolerance": 0.05}
    )
    assert schema.chart_suggestion["estimated"] is True


def test_tolerance_5pct_accepts_close_match():
    """38 in source, 39 in chart passes (within 5% of 38)."""
    data = _chart_data(
        chart_suggestion={
            "chart_type": "bar",
            "categories": ["2024"],
            "series": [{"name": "应用率", "values": [39]}],
            "so_what": "应用率约 39%",
        }
    )
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
    )
    assert schema is not None


def test_no_context_skips_traceability():
    """Without context, traceability check is skipped (backward compat)."""
    data = _chart_data(
        chart_suggestion={
            "chart_type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "增长", "values": [9999]}],
            "so_what": "增长 9999%",
        }
    )
    schema = ContentSlideSchema.model_validate(data)
    assert schema is not None


def test_text_only_slide_skips_traceability():
    """Non-chart slides skip traceability entirely."""
    data = {
        "page_number": 5,
        "primary_visual": "text_only",
        "text_blocks": _dense_blocks(),
    }
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
    )
    assert schema.primary_visual.value == "text_only"


def test_parse_slide_passes_context():
    """parse_slide() should forward context to model_validate."""
    import json as _json
    data = {
        "page_number": 5,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "categories": ["2024"],
            "series": [{"name": "应用率", "values": [38]}],
            "so_what": "应用率 38%"
        },
        "text_blocks": _dense_blocks(),
    }
    llm_output = f'```json\n{_json.dumps(data, ensure_ascii=False)}\n```'
    result = parse_slide(
        llm_output, 5,
        context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
    )
    assert result.error_kind == "ok"
    assert result.schema.chart_suggestion["series"][0]["values"] == [38]


def test_parse_slide_traceability_failure_returns_schema_error():
    """parse_slide() should return schema error for traceability failures."""
    llm_output = '''```json
    {
        "page_number": 5,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "categories": ["Q1"],
            "series": [{"name": "增长", "values": [540]}],
            "so_what": "增长 540%"
        },
        "text_blocks": []
    }
    ```'''
    result = parse_slide(
        llm_output, 5,
        context={"raw_text": SOURCE_TEXT, "tolerance": 0.05}
    )
    assert result.error_kind == "schema"
    assert result.raw_data is not None
