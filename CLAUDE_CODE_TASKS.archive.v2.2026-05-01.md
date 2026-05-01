# PPTagent — 工作清单 v3 (B2B 售前 deck 对齐版)

> **生成日期**：2026-04-30
> **验收标准**：[`REQUIREMENTS.md`](./REQUIREMENTS.md)（B2B 售前方案 deck，**不是** MBB 极简风）
> **本清单可直接交给 Claude Code 实施**，不需要会话上下文。所有路径相对 `/Users/xiongzhou/project/PPTagent/`（Docker 内 `/app/`）。
>
> **历史版本**：
> - `CLAUDE_CODE_TASKS.archive.2026-04-29.md` — 最早版本（PR1-PR3）
> - `CLAUDE_CODE_TASKS.archive.MBB.2026-04-30.md` — MBB 对标版（Fix 7-13），部分作废

---

## 当前状态

### 已完成（不要重做）

| Fix | 内容 | Commit |
|---|---|---|
| Fix 1 | PlanAgent 章节编号 deterministic | ae51556 |
| Fix 4 | page_weight schema enum 加 transition | ae51556 |
| Fix 5 | HTMLDesignAgent dup-prefix detector + retry | ae51556 |
| Fix 6 | 章节页数均衡（_verify_plan 加约束） | (合入主线) |
| Cleanup 2 | narrative_arc 端点 deterministic | (合入主线) |
| Fix 7 | Action title prompt 强化 | 26a1f5e |
| Fix 8 | Source 脚注渲染 | 26a1f5e |
| Fix 10 | Bullet 长度 cap | 26a1f5e |
| Fix 12 | Chart annotation callouts（**注意**：引入 H3 回归，需 R1 修） | ee8e164 |
| Fix 13 | Footer with section name | ee8e164 |
| Phase 2 | Schema-centric pipeline (pydantic) | c008011 |
| Phase 3 | LayoutTemplate Registry 全部 8 layouts | 30241f7 |

### 已撤销（不要做）

- ~~Fix 2 render_server.js UTF-8~~ — H3 是观察伪影，pptx 实际无乱码
- ~~Fix 11 颜色 pixel ratio 严格化~~ — 售前 deck 不需要单 accent 严格约束
- ~~Fix 9 单独 closing layout~~ — 已被 Phase 3 的 call_to_action layout 覆盖

### 当前 v4 audit（基于 REQUIREMENTS.md SLO）

**Hard requirements（3/5 不达标，当前不可发布）**：

| ID | 状态 | 详情 |
|---|---|---|
| H1 章节编号一致 | ✅ Pass | |
| H2 0 prefix-of-superset | ❌ **Fail** | slide 21 三槽 hero 布局漏修 |
| H3 0 chart 误注入扉页 | ❌ **Severe Fail** | slide 9/17/20 全被 chart_renderer 误注入 |
| H4 数据可溯源 | ❌ **Severe Fail** | "+540% / +1050% / +0%" 是 LLM 幻觉 |
| H5 章节名一致 | ✅ Pass | |

---

## 实施顺序

```
Week 1 (P0 — 修 Hard requirements，4 个任务，~3 天):
  R1  chart_renderer slide_type 过滤             [2 小时]
  R2  ContentAgent chart_suggestion 数据可溯源    [1 天]
  R3  Universal post-render dup-prefix guard      [半天]
  R4  Layout fallback 单元测试矩阵                [1 天]

Week 2-3 (P1 — 补售前必备 layout，5 个新 layout):
  R5.1 tech_architecture                          [1 天]
  R5.2 capability_matrix                          [1 天]
  R5.3 case_study                                 [1 天]
  R5.4 solution_comparison                        [1 天]
  R5.5 end_to_end_flow                            [1 天]

Week 4 (P1 — 视觉密度 mode):
  R6  dense_b2b theme + 满版构图模板               [2 天]

后续 (P2 — Soft requirements 持续优化):
  S5  ≥30% 内容页含图表 — ContentAgent prompt 加权
  S2  章节 3-7 页 — Fix 6 已部分修，运营观察
```

**质量目标**：完成 R1-R4 后 v4 audit 5/5 Hard pass（可发布门槛）。完成 R5-R6 后达到"售前 deck-grade"完整能力。

---

## R1 (P0) — chart_renderer slide_type 过滤

### 问题

`chart_renderer.py` 把 chart 注入到了 section_divider / agenda / title 页面（v4 slide 9/17/20）。这违反 **H3 Hard requirement**。

### 实施

**File**：`pipeline/layer6_output/chart_renderer.py`

`add_chart_to_slide()` 入口加 slide_type 检查：

```python
_CHART_FORBIDDEN_SLIDE_TYPES = frozenset({"section_divider", "agenda", "title"})

def add_chart_to_slide(slide, chart_spec, slide_data, ...):
    """Inject native python-pptx chart at placeholder coords.
    
    SKIP for structural slides (section_divider, agenda, title) —
    these pages must remain clean separators per REQUIREMENTS.md H3.
    """
    slide_type = slide_data.get("slide_type", "content")
    if slide_type in _CHART_FORBIDDEN_SLIDE_TYPES:
        logger.info(
            "Skipping chart injection on %s slide (page=%d): structural slides reserved for navigation",
            slide_type, slide_data.get("page_number", "?"),
        )
        return  # No-op
    
    # ... existing injection logic
```

### 测试

新建 `tests/test_chart_renderer_slide_filter.py`：

```python
import pytest
from unittest.mock import MagicMock
from pipeline.layer6_output.chart_renderer import add_chart_to_slide

@pytest.mark.parametrize("slide_type", ["section_divider", "agenda", "title"])
def test_chart_skipped_on_structural_slide(slide_type):
    mock_slide = MagicMock()
    mock_chart_spec = {"chart_type": "bar", "series": [{"values": [1, 2, 3]}]}
    slide_data = {"slide_type": slide_type, "page_number": 9}
    
    add_chart_to_slide(mock_slide, mock_chart_spec, slide_data)
    
    # Assert no chart was added
    assert mock_slide.shapes.add_chart.call_count == 0

def test_chart_injected_on_content_slide():
    mock_slide = MagicMock()
    mock_chart_spec = {"chart_type": "bar", "series": [{"values": [1, 2, 3]}]}
    slide_data = {"slide_type": "content", "page_number": 5}
    
    add_chart_to_slide(mock_slide, mock_chart_spec, slide_data)
    
    # Should attempt to add chart
    assert mock_slide.shapes.add_chart.called or mock_slide.shapes.add_textbox.called
```

### 验收

1. `pytest tests/test_chart_renderer_slide_filter.py -v` 全过
2. Docker 重跑同份 docx：v4 slide 9/17/20 (section_divider) 不再出现 chart 形状
3. 内容页 (slide 4/5/7 等) 的 chart 不受影响

### 工作量

~30 行实现 + ~40 行测试 = 半天

---

## R2 (P0) — ContentAgent chart_suggestion 数据可溯源

### 问题

ContentAgent 输出的 chart_suggestion 中的百分比 / 数字是 LLM 幻觉（v4 +540% / +1050% / +0%）。违反 **H4 Hard requirement**。

### 实施

**File**：`models/schemas.py` + `pipeline/agents/content_agent.py`

#### 步骤 2.1：ContentSlideSchema 加 chart 数据可溯源 validator

```python
import re

class ContentSlideSchema(BaseModel):
    # ... existing fields
    
    @model_validator(mode="after")
    def enforce_chart_data_traceability(self):
        """All numbers in chart_suggestion (series values, so_what) must be 
        traceable to source raw_text within ±5% tolerance, OR explicitly
        marked as 'estimated'."""
        if self.primary_visual != PrimaryVisualType.CHART:
            return self
        
        cs = self.chart_suggestion or {}
        if cs.get("estimated") is True:
            return self  # Explicitly marked estimate, skip check
        
        # Extract all numbers from chart annotations / so_what
        annotations = []
        for s in cs.get("series", []):
            for v in s.get("values", []):
                if isinstance(v, (int, float)):
                    annotations.append(v)
        if cs.get("so_what"):
            # Pull percent / large numbers from so_what string
            for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(%|％|亿|万|千|倍|x)', cs["so_what"]):
                annotations.append(float(m.group(1)))
        
        # Cross-reference with raw_text from source chunks
        # raw_text comes from slide_data.get("source_chunks", [])
        # ... see content_agent.py for chunk lookup
        # If any number can't be found in source ±5%, raise
        
        # Implementation note: actual chunk lookup requires injection of
        # chunk text at validation time — see content_agent.py step 2.2
        return self
```

> **Implementation note**: pydantic validators don't have access to raw_text by default. Two options:
> 
> **Option A (preferred)**: Pass raw_text as ValidationContext in ContentAgent before calling `model_validate`. Use `info.context['raw_text_chunks']` inside validator.
> 
> **Option B**: Move traceability check OUT of pydantic validator into ContentAgent's `_validate_traceability()` method, called after `model_validate()` returns successfully. This is cleaner but loses the auto-retry chain.
> 
> Recommend **Option A** — preserves Phase 2 auto-retry on schema failure.

#### 步骤 2.2：ContentAgent 调用时注入 chunk 上下文

```python
# pipeline/agents/content_agent.py _generate_one_slide()

# Get the chunks this slide is bound to
chunk_ids = slide.get("chunk_ids", [])
chunks_text = "\n".join(c.get("text", "") for c in self._all_chunks if c.get("id") in chunk_ids)

# Validate with context
try:
    schema = ContentSlideSchema.model_validate(
        data,
        context={"raw_text": chunks_text, "tolerance": 0.05},
    )
except ValidationError as e:
    if "traceability" in str(e).lower():
        # Retry chain: tell LLM to mark estimated or fix numbers
        retry_msg = (
            f"图表数据 ({extract_numbers(data)}) 无法从源文档找到对应数字。\n"
            f"请按以下规则修改：\n"
            f"1. 如果数字直接来自源文档，使用源文档的原始数字（容差 ±5%）\n"
            f"2. 如果是行业估算，加 \"estimated\": true 字段并改写 so_what 为"
            f"\"基于行业平均估算\"\n"
            f"3. 不允许出现源文档中不存在的精确百分比"
        )
        # ... retry with this message
```

#### 步骤 2.3：ContentAgent prompt 加约束

`pipeline/prompts/content_agent.v2.md`（或对应 prompt 文件）section 关于 chart_suggestion 加：

```
chart_suggestion 数据约束：
1. 所有 series values 中的数字必须来自源文档（chunk_ids 对应内容）
2. so_what 字段中的百分比 / 大数字必须能在源文档找到（容差 ±5%）
3. 如果是行业估算或推理值，必须加 "estimated": true 字段，
   且 so_what 改写为"基于行业平均估算 X%"或"估算值，待校对"
4. 不允许编造源文档中不存在的精确数字（特别是百分比、增长率）
```

### 测试

`tests/test_chart_traceability.py`：

```python
import pytest
from pydantic import ValidationError
from models.schemas import ContentSlideSchema, PrimaryVisualType

CHUNK_TEXT_WITH_NUMBERS = """
2024 年金融行业大模型应用率达到 38%，同比增长 12 个百分点。
某银行案例：部署 AI 风控后欺诈拦截率提升至 92%，年节省成本约 1.5 亿元。
"""

def test_chart_with_traceable_numbers_passes():
    data = {
        "page_number": 5,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "series": [{"values": [38, 50]}],
            "so_what": "金融大模型应用率达到 38%，预计 2025 年突破 50%",
            "estimated": False,
        },
        "text_blocks": [],
    }
    schema = ContentSlideSchema.model_validate(
        data,
        context={"raw_text": CHUNK_TEXT_WITH_NUMBERS, "tolerance": 0.05},
    )
    assert schema.primary_visual == PrimaryVisualType.CHART


def test_chart_with_hallucinated_540pct_rejected():
    """Reproduces v4 slide 9 bug: '+540%' is not in source."""
    data = {
        "page_number": 9,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "series": [{"values": [540]}],
            "so_what": "数据投毒攻击同比增长 540%",
            "estimated": False,
        },
        "text_blocks": [],
    }
    with pytest.raises(ValidationError, match="traceability"):
        ContentSlideSchema.model_validate(
            data,
            context={"raw_text": CHUNK_TEXT_WITH_NUMBERS, "tolerance": 0.05},
        )


def test_chart_marked_estimated_passes():
    """If estimated=True, traceability check is skipped."""
    data = {
        "page_number": 9,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "series": [{"values": [540]}],
            "so_what": "基于行业平均估算 540%",
            "estimated": True,
        },
        "text_blocks": [],
    }
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": "", "tolerance": 0.05},
    )
    assert schema.chart_suggestion["estimated"] is True


def test_tolerance_5pct_accepts_close_match():
    """38% in source, 39% in chart should pass (≤5% diff)."""
    data = {
        "page_number": 5,
        "primary_visual": "chart",
        "chart_suggestion": {
            "chart_type": "bar",
            "series": [{"values": [39]}],  # 38 in source, ~3% off
            "so_what": "应用率约 39%",
        },
        "text_blocks": [],
    }
    schema = ContentSlideSchema.model_validate(
        data, context={"raw_text": CHUNK_TEXT_WITH_NUMBERS, "tolerance": 0.05},
    )
    assert schema is not None
```

### 验收

1. `pytest tests/test_chart_traceability.py -v` 4/4 pass
2. Docker 重跑同份 docx：日志中 "traceability retry" 出现 ≥ 3 次（说明在拦截幻觉）
3. 输出 pptx 中 chart 数据可在源 docx grep 到（人工抽查 5 张图）

### 工作量

~80 行 schema validator + chunk context 注入 + ~120 行测试 = **1 天**

---

## R3 (P0) — Universal post-render dup-prefix guard

### 问题

`detect_dup_prefix` 现在只在 LLM HTML 路径调用，registry 路径绕过（v4 slide 21 三槽 hero 漏检）。违反 **H2 Hard requirement**。

### 实施

**File**：`pipeline/agents/html_design_agent.py`

#### 步骤 3.1：把 detector 调用提到统一出口

```python
def _generate_slide_html(self, slide_index, slide_data, theme_colors, total_slides, task):
    """Generate HTML for a single slide.
    
    All paths (LLM, registry, special_pages, fallback) must produce HTML
    that passes detect_dup_prefix(ratio=1.3) before commit.
    """
    html = self._dispatch_to_path(slide_index, slide_data, theme_colors, total_slides, task)
    
    # Universal guard — applies regardless of which path generated the HTML
    return self._enforce_dup_prefix_guard(html, slide_data, theme_colors, total_slides)


def _enforce_dup_prefix_guard(self, html, slide_data, theme_colors, total_slides, max_retry=2):
    """Universal post-render dup-prefix guard.
    
    Phase 3 LayoutTemplate Registry assumption that 'typed schema = safe by 
    construction' was disproven by v3/v4 regressions. Apply detector to 
    ALL build_html outputs as the final safety net.
    """
    from pipeline.layer6_output.html_dup_check import detect_dup_prefix
    
    for attempt in range(max_retry):
        err = detect_dup_prefix(html, ratio=1.3)
        if err is None:
            return html  # OK
        
        logger.warning(
            "Slide %d: dup-prefix detected (attempt %d): %s",
            slide_data.get("page_number", "?"), attempt + 1, err[:100],
        )
        
        # Retry strategy depends on path
        path = self._classify_path(slide_data)
        if path == "registry":
            # Registry build_html is deterministic — retry won't help. Degrade.
            logger.error(
                "Registry layout %s produced dup-prefix HTML — bug in build_html. "
                "Falling back to text_only.",
                slide_data.get("layout_hint", "?"),
            )
            return self.fallback.heuristic_template_html(
                slide_data.get("page_number", 1),
                slide_data, theme_colors, total_slides,
            )
        elif path == "llm":
            # LLM path — retry with error message in prompt
            html = self._llm_retry_with_dup_error(slide_data, html, err, theme_colors)
        else:
            # special_pages / fallback — degrade immediately
            return self.fallback.heuristic_template_html(...)
    
    # Final fallback after retries exhausted
    logger.error("Slide %d: dup-prefix retries exhausted, hard fallback", 
                 slide_data.get("page_number", "?"))
    return self.fallback.heuristic_template_html(...)
```

#### 步骤 3.2：detect_dup_prefix ratio 阈值确认

`pipeline/layer6_output/html_dup_check.py`：确认默认 ratio=1.3 已经合入。如果还是 2.0，改成 1.3。

```python
def detect_dup_prefix(html, min_short=5, max_short=30, ratio=1.3):
    # ... existing logic
```

### 测试

`tests/test_universal_dup_guard.py`：

```python
import pytest
from unittest.mock import MagicMock, patch
from pipeline.agents.html_design_agent import HTMLDesignAgent
from pipeline.layer6_output.html_dup_check import detect_dup_prefix


def test_registry_path_dup_prefix_triggers_fallback():
    """Reproduces v4 slide 21: registry-built HTML with dup-prefix
    should be detected and degraded."""
    agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
    agent.fallback = MagicMock()
    agent.fallback.heuristic_template_html.return_value = "<html><body>Fallback</body></html>"
    
    bad_html = """
    <html><body>
        <p style="font-size:13.5pt">分层分域防护框架在关键风险点实现了60%-90%的威胁降低效果...</p>
        <h1 style="font-size:54pt">60%</h1>
        <p style="font-size:12pt">分层分域防护框架在关键风险点实现</p>
    </body></html>
    """
    slide_data = {"page_number": 21, "layout_hint": "quote_emphasis"}
    
    with patch.object(agent, '_classify_path', return_value='registry'):
        result = agent._enforce_dup_prefix_guard(bad_html, slide_data, {}, 25)
    
    assert "Fallback" in result
    agent.fallback.heuristic_template_html.assert_called_once()


def test_clean_html_passes_through():
    agent = HTMLDesignAgent.__new__(HTMLDesignAgent)
    clean_html = "<html><body><h1>主动防御四步法</h1><p>识别 防护 监控 响应</p></body></html>"
    slide_data = {"page_number": 5, "layout_hint": "framework_grid"}
    
    result = agent._enforce_dup_prefix_guard(clean_html, slide_data, {}, 25)
    assert result == clean_html


def test_ratio_1_3_catches_v4_slide21():
    """v4 slide 21: 16-char prefix in 60-char long, ratio = 4.62"""
    short = "分层分域防护框架在关键风险点实现"  # 16 chars
    long = "分层分域防护框架在关键风险点实现了60%-90%的威胁降低效果，经银行实践..."  # 60+ chars
    html = f"<p>{long}</p><h2>{short}</h2>"
    err = detect_dup_prefix(html, ratio=1.3)
    assert err is not None
    assert "分层分域" in err
```

### 验收

1. `pytest tests/test_universal_dup_guard.py -v` 全过
2. Docker 重跑：日志中 "dup-prefix detected" 应在 v4 出现的位置出现，且最终 pptx 0 处 prefix
3. 现有 `tests/test_html_dup_check.py` 仍全过

### 工作量

~50 行实现 + ~80 行测试 = 半天

---

## R4 (P0) — Layout fallback 单元测试矩阵

### 问题

v3/v4 的 H1 bug 都是 **layout fallback 路径**引入的（visual_block 缺失时 layout 自己用启发式拼，结果引入 prefix-of-superset）。当前测试只覆盖了 visual_block 充足的快乐路径。

### 实施

**File**：新建 `tests/test_layout_fallback_no_dup_prefix.py`

```python
"""Regression test: every layout's from_slide_data + build_html must NOT
produce prefix-of-superset HTML, regardless of input completeness.

Covers the v3/v4 bug pattern where layout fallback paths (no visual_block,
no chart_suggestion) introduced prefix-truncated text into separate slots.
"""
import pytest
from pipeline.layouts import LayoutRegistry
from pipeline.layer6_output.html_dup_check import detect_dup_prefix

THEME_COLORS = {
    "primary": "#003D6E", "secondary": "#005A9E", "accent": "#FF6B35",
    "text": "#2D3436", "muted": "#636E72", "bg": "#EEF4FA", "border": "#C8D8E8",
}


def _slide_data_full():
    """Slide with both visual_block AND text_blocks populated."""
    return {
        "page_number": 5,
        "slide_type": "content",
        "takeaway_message": "示例 takeaway 描述本页核心论点的完整结论句。",
        "title": "示例标题",
        "primary_visual": "visual_block",
        "visual_block": {
            "type": "icon_text_grid",
            "items": [
                {"title": f"维度{i}", "description": f"维度{i}的具体描述内容"}
                for i in range(1, 5)
            ],
        },
        "text_blocks": [
            {"content": f"论据 {i}：详细论据描述。", "level": 1}
            for i in range(1, 5)
        ],
        "chart_suggestion": None,
        "layout_hint": "framework_grid",
    }


def _slide_data_no_visual_block():
    """Slide WITHOUT visual_block — forces layout fallback path."""
    d = _slide_data_full()
    d["visual_block"] = None
    return d


def _slide_data_no_text_blocks():
    d = _slide_data_full()
    d["text_blocks"] = []
    return d


def _slide_data_minimal():
    """Just takeaway, no visual_block, no text_blocks."""
    return {
        "page_number": 5,
        "slide_type": "content",
        "takeaway_message": "示例 takeaway。",
        "title": "示例",
        "primary_visual": "text_only",
        "visual_block": None,
        "chart_suggestion": None,
        "text_blocks": [],
        "layout_hint": "framework_grid",
    }


@pytest.mark.parametrize("layout_name", LayoutRegistry.names())
@pytest.mark.parametrize("fixture_name,fixture_factory", [
    ("full", _slide_data_full),
    ("no_visual_block", _slide_data_no_visual_block),
    ("no_text_blocks", _slide_data_no_text_blocks),
    ("minimal", _slide_data_minimal),
])
def test_layout_no_dup_prefix(layout_name, fixture_name, fixture_factory):
    """Each layout × each fixture must produce HTML free of prefix-of-superset.
    
    8 layouts × 4 fixtures = 32 test cases. Catches v3/v4-class regressions
    before they ship.
    """
    layout = LayoutRegistry.get(layout_name)
    slide_data = fixture_factory()
    
    content = layout.from_slide_data(slide_data)
    html = layout.build_html(
        content,
        theme_colors=THEME_COLORS,
        page_number=slide_data["page_number"],
        total_slides=20,
    )
    
    err = detect_dup_prefix(html, ratio=1.3)
    assert err is None, (
        f"Layout '{layout_name}' with fixture '{fixture_name}' produced "
        f"dup-prefix HTML. Likely a fallback path bug. Error: {err}"
    )
```

### 验收

1. `pytest tests/test_layout_fallback_no_dup_prefix.py -v` 应有 8 × 4 = 32 个测试
2. **预期 R1-R3 没修前会有失败项**——这正是这个测试的目的（暴露漏洞）
3. R1-R3 修完后全部 32 项 pass

### 工作量

~150 行测试，1 天（含跑测试 + 修出来的回归）

---

## R5 (P1) — 5 个 B2B 售前必备 layout

按 Phase 3 LayoutTemplate Registry 模式实现：每个 layout 一个文件 + content_schema + system-assembled build_html + fallback 测试。

### R5.1 — `tech_architecture` 多层级技术栈

**File**：`pipeline/layouts/tech_architecture.py`

**Schema**：
```python
class ArchLayer(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    components: list[str] = Field(default_factory=list, max_length=8)
    color: Optional[str] = None  # Optional layer-specific color

class TechArchitectureContent(BaseModel):
    title: str = Field(default="")
    layers: list[ArchLayer] = Field(min_length=2, max_length=7)
```

**视觉**：横向堆叠的层级矩形，自上而下"应用层 → 平台层 → 数据层 → 基础设施层"。每层显示组件标签（如 "Web前端", "API网关", "K8s 集群"）。可选每层不同色。

### R5.2 — `capability_matrix` 能力维度对比

**File**：`pipeline/layouts/capability_matrix.py`

**Schema**：
```python
class MatrixCell(BaseModel):
    status: Literal["yes", "no", "partial", "planned"] = "no"
    note: str = ""

class CapabilityMatrixContent(BaseModel):
    title: str = Field(default="")
    columns: list[str] = Field(min_length=2, max_length=5, description="x 轴标签（阶段/方案）")
    rows: list[str] = Field(min_length=2, max_length=8, description="y 轴标签（能力维度）")
    cells: list[list[MatrixCell]] = Field(description="二维矩阵，行 × 列")
```

**视觉**：表格状矩阵，行=能力维度，列=阶段或选项。单元格用图标（✓ / ✗ / ◑ / ⏱）+ 颜色编码状态。

### R5.3 — `case_study` 客户案例卡

**File**：`pipeline/layouts/case_study.py`

**Schema**：
```python
class CaseStudyContent(BaseModel):
    title: str = Field(default="")
    customer_name: str = Field(min_length=1, max_length=30)
    customer_industry: str = ""
    challenge: str = Field(max_length=120)  # 客户问题
    solution: str = Field(max_length=120)   # 方案
    kpis: list[dict] = Field(min_length=2, max_length=4)  # 每个 {label, value, unit}
    quote: str = ""  # 客户引言
    duration: str = ""  # 实施周期 e.g. "3个月"
```

**视觉**：左侧客户名 + 行业 + 实施周期；中间挑战 → 方案；右侧 2-4 个大数字 KPI；底部可选引言。

### R5.4 — `solution_comparison` 方案 vs 竞品对比

**File**：`pipeline/layouts/solution_comparison.py`

**Schema**：
```python
class SolutionOption(BaseModel):
    name: str
    is_recommended: bool = False  # 推荐方案高亮

class CompareCell(BaseModel):
    score: Literal["best", "good", "average", "poor"] = "average"
    note: str = ""

class SolutionComparisonContent(BaseModel):
    title: str = Field(default="")
    options: list[SolutionOption] = Field(min_length=2, max_length=4)
    criteria: list[str] = Field(min_length=3, max_length=8)
    cells: list[list[CompareCell]]  # criteria × options
```

**视觉**：列对比表；推荐方案那一列加边框 + 标题底色；单元格用 ●●●● 圆点星级或图标显示评级。

### R5.5 — `end_to_end_flow` 端到端业务流

**File**：`pipeline/layouts/end_to_end_flow.py`

**Schema**：
```python
class FlowStage(BaseModel):
    name: str = Field(min_length=1, max_length=15)
    actor: str = ""        # 谁负责（系统/角色）
    action: str = Field(max_length=40)
    output: str = ""       # 产出
    duration: str = ""     # 耗时

class EndToEndFlowContent(BaseModel):
    title: str = Field(default="")
    stages: list[FlowStage] = Field(min_length=4, max_length=7)
    swim_lanes: bool = False  # 是否分泳道（按 actor）
```

**视觉**：横向 4-7 个阶段的流程图，每段用箭头连接。可选 swim_lanes 模式按 actor 分行。

### R5 通用验收

每个 layout 必须：

1. 实现 `from_slide_data` + `build_html` 两个方法
2. 注册到 `LayoutRegistry`（更新 `pipeline/layouts/__init__.py`）
3. 加进 `LAYOUT_HINT_MAP`（如果 PlanAgent 输出对应 hint）
4. 单测：自身正常路径 + fallback path（被 R4 测试矩阵自动覆盖）
5. ContentAgent prompt 加对应 layout_hint 描述（让 LLM 知道何时选这个 layout）

每个 layout 工作量约 1 天（含 schema、build_html、prompt、测试）。

---

## R6 (P1) — `dense_b2b` Theme + 满版构图

### 问题

当前 5 个 theme 都是 minimalist 风格（白底大留白）。售前 deck 需要满版构图（左文右图 50/50、顶部章节带、底部数据条）。

### 实施

**File**：`templates/themes/dense_b2b.json`

```json
{
  "id": "dense_b2b",
  "name": "B2B 售前方案密集型",
  "colors": {
    "primary": "#1a4d8c",
    "secondary": "#3a7bc8",
    "accent": "#ff6f3c",
    "text_dark": "#1a1a1a",
    "text_light": "#5a5a5a",
    "bg": "#f7f9fc",
    "border": "#d0d8e0",
    "section_color_1": "#1a4d8c",
    "section_color_2": "#2c7873",
    "section_color_3": "#a23b72",
    "section_color_4": "#f4a261",
    "section_color_5": "#7d4f8c",
    "section_color_6": "#577590"
  },
  "fonts": {
    "title": "Microsoft YaHei",
    "body": "Microsoft YaHei"
  },
  "density_mode": "dense",
  "layout_hints": {
    "content_split_ratio": 0.5,
    "header_bar_height": 36,
    "footer_bar_height": 28,
    "padding": 16
  }
}
```

**Theme Registry** (`pipeline/layer4_visual/theme_registry.py`)：注册 dense_b2b，让 strategy → theme 映射可选 dense_b2b。

**Layout 适配**：所有 layout 的 `build_html` 读 theme 的 `density_mode`，dense 模式下：
- 内容区 padding 缩小（16px vs 现有 24px）
- header bar 加章节色块（取 `section_color_X` 按章节 idx）
- footer 显示章节名 + 页码，用章节色背景

### 测试

```python
# tests/test_dense_b2b_theme.py
def test_dense_b2b_theme_registered():
    from pipeline.layer4_visual.theme_registry import ThemeRegistry
    theme = ThemeRegistry().get_theme("dense_b2b")
    assert theme.id == "dense_b2b"
    assert "section_color_1" in theme.colors

def test_dense_mode_in_layout_html():
    """dense_b2b theme should produce HTML with smaller padding + section bar."""
    from pipeline.layouts.framework_grid import FrameworkGridLayout
    layout = FrameworkGridLayout()
    content = layout.from_slide_data({...})
    html = layout.build_html(content, theme_colors={"density_mode": "dense", ...}, ...)
    assert 'height:36px' in html  # header bar
    assert 'padding:16px' in html
```

### 验收

1. theme registry 测试通过
2. 用 dense_b2b 重跑 docx 生成：内容页文字密度 ≥ 50%（手测 5 张抽样）
3. 不影响现有 5 个 theme（旧 task 用旧 theme 仍然 OK）

### 工作量

theme JSON + registry + layout 适配 + 测试 = **2 天**

---

## 已撤销 / 不做（避免重做）

| 任务 | 原因 |
|---|---|
| ~~Fix 11 颜色 pixel ratio 严格化~~ | 售前 deck 不需要 single accent；REQUIREMENTS.md §3.2 |
| ~~Bullet 上限 60-80 字~~ | 改为 60-120 字；REQUIREMENTS.md §3.1 |
| ~~White space ≥ 1cm 留白~~ | 反向需求；REQUIREMENTS.md §3.1 |
| ~~MBB Rubric 10 维度评分~~ | 用 REQUIREMENTS.md §二 SLO 替代 |
| ~~render_server.js UTF-8 修复~~ | H3 是观察伪影 |

---

## 关键约束（实施者必读）

1. **REQUIREMENTS.md 是唯一真相**。任何质量决策都应回到 SLO H1-H5 / S1-S5。本清单与 REQUIREMENTS.md 冲突时以后者为准。
2. **Docker-first**：`docker-compose -f docker-compose.dev.yml up --build -d backend`，本地 venv 只能跑 schema/单元层。
3. **每 PR 一个 Task**：R1-R6 各 1 个 PR，独立合并/回滚。
4. **现有测试必须全过**：当前 ~299 个测试（含 Phase 2 + Phase 3 + Fix 1-13），新增项不能让现有项 fail。
5. **新 layout 必须过 R4 fallback 测试**：R5.1-R5.5 每加一个 layout，R4 的参数化矩阵自动多跑 4 个 case。
6. **LLM 成本不省**：schema retry × 3、自愈链能多调就多调，效果优先（REQUIREMENTS.md §六）。
7. **Phase 3 + Phase 2 已建好基础设施**：所有新 layout 都按 LayoutRegistry 模式，新 schema 都用 pydantic + auto-retry。
8. **commit message 格式**：`fix(layouts): ...` / `feat(theme): ...` / `chore: ...`

---

## 验证流程（每个 PR 必跑）

1. **单测**：`pytest tests/ -v` 全绿（≥299+R4 新增 32 个 layout matrix tests）
2. **Docker 集成**：rebuild backend，跑同份 docx 生成 pptx
3. **Audit 脚本**：用 `python3 -c "..."` 提取 pptx shape 结构，对照 REQUIREMENTS.md §二 SLO 逐项核查
4. **SLO 5/5 Hard pass** 后 PR 才能合并

---

## 参考资料

- [`REQUIREMENTS.md`](./REQUIREMENTS.md) — **验收标准**
- [`CONSULTING_TEMPLATE_REFERENCE.md`](./CONSULTING_TEMPLATE_REFERENCE.md) — 灵感参考（部分作废）
- `CLAUDE.md` — 项目架构 + 6-agent pipeline
- `tests/test_layout_fallback_no_dup_prefix.py` (R4 后) — layout 行为基准
- `pipeline/layouts/quote_emphasis.py` — Phase 3 layout 实现参考
- `models/schemas.py::ContentSlideSchema` — Phase 2 schema 实现参考

---

## 完成状态预期

| 里程碑 | Pass 标准 | 预期日期 |
|---|---|---|
| R1-R4 完成 | v4 audit 5/5 Hard pass，可发布 | Week 1 末 |
| R5 完成（5 layout） | ContentAgent 能选 5 个新 layout，PlanAgent 学会 hint | Week 3 末 |
| R6 完成 | dense_b2b theme 上线，售前 deck 视觉密度达标 | Week 4 末 |
| 整体达 SLO | H1-H5 100%，S1-S5 ≥95% | Week 4 末 |
