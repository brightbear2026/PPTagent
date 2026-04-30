# PPTagent — Claude Code 工作清单

> **更新日期**：2026-04-30（第二轮）
> **状态**：Fix 5-13 全部完成 + Phase 3 LayoutTemplate Registry 8/8 layout_hints 覆盖。293 tests pass。
> **历史版本**：旧任务清单归档为 `CLAUDE_CODE_TASKS.archive.2026-04-29.md`。
>
> 本清单可独立交给一个新 Claude Code 会话实施，不需要其他对话上下文。所有路径相对于 `/Users/xiongzhou/project/PPTagent/`（或 Docker 内 `/app/`）。

---

## 已完成

| Fix | 内容 | Commit | 验证 |
|---|---|---|---|
| **Fix 1** | PlanAgent 章节编号 deterministic | `ae51556` | 5/5 tests |
| **Fix 4** | `page_weight` schema enum 补 `transition` | `ae51556` | 10/10 tests |
| **Fix 5** | Dup-prefix detector（三路径覆盖）+ hero_splash 根因 | `ae51556` | 6/6 tests |
| **Cleanup 2** | narrative_arc 端点 deterministic | `ae51556` | 2/2 tests |
| **Fix 6** | 章节页数均衡（thin/overlong） | `ae51556` | 3/3 tests |
| **Fix 9** | Phase 3 pilot: call_to_action closing layout | `c253e47` | 16/16 tests |
| **Fix 7** | Action title prompt + soft warning | `26a1f5e` | prompt + log |
| **Fix 8** | Source 脚注渲染 | `26a1f5e` | render_template |
| **Fix 10** | Bullet 长度 cap 120 字 | `26a1f5e` | 4/4 tests |
| **Fix 12** | Chart annotation callouts | `ee8e164` | 3/3 tests |
| **Fix 13** | Footer 章节+页码 | `ee8e164` | 3/3 tests |
| **Fix 11** | 颜色 semantic prompt-only | `8c9de87` | prompt |
| **Phase 3** | LayoutTemplate Registry — 8/8 layout_hints 覆盖 | `8c9de87` | 21+6+8 tests |

**已撤销**：~~Fix 2 render_server.js UTF-8 边界 bug~~ — H3 是观察伪影。

---

## Phase 3 LayoutTemplate Registry — 完成

8 个 layout_hint 全部迁移到 typed, system-assembled HTML：

| Layout | 模板 | 文件 |
|---|---|---|
| `call_to_action` | CTA closing 页 | `pipeline/layouts/call_to_action.py` |
| `quote_emphasis` | 核心结论强调 | `pipeline/layouts/quote_emphasis.py` |
| `parallel_points` | 并列论据 bullets | `pipeline/layouts/parallel_points.py` |
| `metrics` | KPI 卡片 | `pipeline/layouts/metrics.py` |
| `chart_focus` | 图表 + 注解 | `pipeline/layouts/chart_focus.py` |
| `comparison` | 双栏对比 | `pipeline/layouts/comparison.py` |
| `framework_grid` | 图标网格 | `pipeline/layouts/framework_grid.py` |
| `narrative` | 时间线 | `pipeline/layouts/narrative.py` |

每个 layout 含：`content_schema`（pydantic）、`from_slide_data()`、`build_html()`、`prompt_fragment()`。

HTMLDesignAgent 路由：`if layout_hint in LayoutRegistry.names()` → registry bypass LLM → fall through to old path。

---

## 剩余工作

### Cleanup 1 — 删 Phase 2 defensive code（一个月后）

| 文件 | 行 | 内容 | 删的理由 |
|---|---|---|---|
| `pipeline/agents/html_design_agent.py` | ~630 | `_match_slides` 互斥清理块 | schema 已保证 |
| `pipeline/agents/design_strategies/templates.py` | ~455 | `_chart_has_data` | schema 已保证 |
| `pipeline/agents/html_design_agent.py` | _inspect_and_fix | LLM re-gen fallback | registry 已覆盖 |

### 未来方向

- **MBB Rubric 打分**：跑一次真实 docx 生成，按 `CONSULTING_TEMPLATE_REFERENCE.md` 10 维度打分
- **Performance tuning**：观察 registry vs LLM latency 差异
- **Specialty layouts**：architecture_stack / quadrant_matrix / role_columns 等 diagram 布局按需迁移

---

## Phase 3 复盘 & Lesson Learned

**Date**: 2026-04-30

### Bug: Registry fallback dup-prefix (framework_grid, narrative)

`framework_grid.py` 和 `narrative.py` 的 fallback path（content 无 visual_block 时）将同一段文字切两段填入 `title=c[:N1]` + `desc=c[:N2]`，导致 desc 以 title 开头 → dup-prefix。

**Root cause**: typed schema 只约束字段形状，`from_slide_data()` 和 `build_html()` 的转换逻辑仍可能引入 logic bug。Registry bypass LLM ≠ immune to content bugs。

**Lesson**:
1. **所有 `build_html()` 输出都必须过 `detect_dup_prefix`** — 不只 LLM 路径。已在 `html_design_agent.py` registry 分发后加 safety net（ERROR 日志）。
2. **Fallback path 必须有独立测试** — 之前所有 layout 测试都用 visual_block 充足的 fixture，从不触发 fallback。已加 `test_layout_no_dup_prefix.py` 参数化测每个 layout 的 fallback path。
3. **`detect_dup_prefix` ratio 阈值 2.0 过严** — 实际 dup-prefix 是 1.5x（title=20chars, desc=60chars），被漏掉。已降至 1.3。

### PPTX Quality Review — 9 Fixes Applied

| # | Issue | Fix |
|---|---|---|
| 1 | Footer total /21 但实际 20 slides | Node bridge 报告 rendered_count；Python 日志 dropped slides |
| 2 | CTA slide 缺 footer | 加 footer bar HTML |
| 3 | CTA takeaway 与 action_item[0] 重复 | CTAContent model_validator reject_duplicated_action_item |
| 4 | framework_grid/narrative fallback dup-prefix | title="" + desc=c[:80]（不切同段文字）；ratio 降至 1.3 |
| 5 | Metrics KPI label 截断 | card_w 200→260 + overflow:ellipsis |
| 6 | Hero "—" 空占位 | conditional render：空/占位符时移除元素 |
| 7 | Footer 格式不一致 P4/21 vs PX / 21 | hero 模板加空格 + _inject_section_footer 多 pattern fallback |
| 8 | Closing 内容稀疏 | CTAContent action_items min_length=3, timeline min_length=1 |
| 9 | Chart annotation \x0b 控制字符 | sanitize before render |

---

## ADR-001: LayoutTemplate Registry（内联）

### 决策

每个 layout 抽成自包含 module，包含 4 个切面：`name`、`content_schema`（pydantic）、`capacity`、`build_html()`。HTMLDesignAgent 对 registry 覆盖的 layout 直接走 `build_html()`，绕过 LLM HTML 生成。

### 背景

当前 HTMLDesignAgent 让 LLM 输出 HTML 字符串——这是 untyped LLM surface。Fix 5 用 dup-prefix detector + retry 防御了症状，但根因是 LLM 自由写 HTML。Phase 2 把 ContentAgent 的 dict 输出 schema 化了，HTMLDesignAgent 仍裸奔。

### 方案

```python
# pipeline/layouts/base.py
class LayoutModule(Protocol):
    name: str
    content_schema: type[BaseModel]
    capacity: Capacity
    def build_html(self, content, theme_colors, page_number, total_slides) -> str: ...
    def prompt_fragment(self) -> str: ...
```

HTMLDesignAgent 路由：
```python
if slide_data.get("layout_hint") in LayoutRegistry.names():
    layout = LayoutRegistry.get(slide_data["layout_hint"])
    content = layout.content_schema.model_validate(slide_data)  # schema-validated
    return layout.build_html(content, theme_colors, ...)        # system-assembled
# else: fall through to existing LLM HTML path
```

### 取舍

- **vs 现状 LLM HTML**：消除 untyped surface，但每个 layout 需要手工写 `build_html()`。接受：layout 种类有限（~7 个），手工写可控性远高于 LLM 自由发挥。
- **vs 渐进迁移**：先 pilot 1 个 layout（call_to_action），验证架构可行后再 roll out。不接受一次性全量迁移——风险太大。
- **ADR 内联 vs 独立文件**：项目目前只有 1 个 ADR，建 `docs/adr/` 目录是孤儿基础设施。积累 3 个以上 ADR 再 extract。

### 否决的备选

- **纯 prompt 工程**（让 LLM "更规范地"写 HTML）——已证明不可靠（Fix 5 的 3 个路径都出过 dup-prefix）
- **HTML 模板引擎**（Jinja2）——增加依赖，且 pydantic schema + f-string 拼装已足够

### 迁移路径

1. Pilot `call_to_action`（Phase 3 pilot = Fix 9）
2. Roll out `quote_emphasis`（Fix 5 的主要受害者）
3. Roll out 剩余 5 个: `parallel_points` / `comparison` / `metrics` / `chart_focus` / `framework_grid`
4. 清理：删除 `_generate_slide_html` 里的 LLM HTML 路径 + Fix 5 detector + 旧 `slide_templates.py`

---

## Fix 9 / Phase 3 pilot (P0+) — call_to_action Layout via Registry

### 问题

当前最后一页只是 bullet 罗列 + 撞 H1 bug（Fix 5 已防但未根治）。MBB 标准是强 CTA：超大 takeaway + 1-3 个 action items + 时间表。

### 为什么这是 Phase 3 pilot 而非又一个模板

往旧模板系统加新 `call_to_action` 模板 = 给 Phase 3 制造拆迁对象（又一个 untyped HTML surface）。用 registry 实现 = 用真实需求驱动架构落地，pilot 本身就是可出货的价值。

### 新文件

#### `pipeline/layouts/__init__.py`

```python
"""LayoutTemplate Registry — typed, system-assembled HTML layouts."""
from pipeline.layouts.base import LayoutModule, Capacity
from pipeline.layouts.call_to_action import CallToActionLayout

class LayoutRegistry:
    _modules: dict[str, LayoutModule] = {}

    @classmethod
    def register(cls, module: LayoutModule) -> None:
        cls._modules[module.name] = module

    @classmethod
    def get(cls, name: str) -> LayoutModule:
        return cls._modules[name]

    @classmethod
    def names(cls) -> set[str]:
        return set(cls._modules.keys())

LayoutRegistry.register(CallToActionLayout())
```

#### `pipeline/layouts/base.py`

```python
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

@dataclass
class Capacity:
    max_text_chars: int = 300
    max_bullet_count: int = 3

@runtime_checkable
class LayoutModule(Protocol):
    name: str
    content_schema: type  # pydantic BaseModel subclass
    capacity: Capacity

    def build_html(
        self,
        content,  # pydantic model instance
        theme_colors: dict[str, str],
        page_number: int = 1,
        total_slides: int = 1,
    ) -> str: ...

    def prompt_fragment(self) -> str: ...
```

#### `pipeline/layouts/call_to_action.py`

```python
from pydantic import BaseModel, Field
from pipeline.layouts.base import LayoutModule, Capacity

class CTAContent(BaseModel):
    takeaway: str = Field(min_length=8)
    action_items: list[str] = Field(default_factory=list, max_length=3)
    timeline: str = ""

class CallToActionLayout:
    name = "call_to_action"
    content_schema = CTAContent
    capacity = Capacity(max_text_chars=200, max_bullet_count=3)

    def build_html(self, content: CTAContent, theme_colors: dict, page_number: int = 1, total_slides: int = 1) -> str:
        primary = theme_colors.get("primary", "#003D6E")
        accent = theme_colors.get("accent", "#FF6B35")
        bg = theme_colors.get("background", "#FFFFFF")
        text_color = theme_colors.get("text", "#333333")

        items_html = ""
        for i, item in enumerate(content.action_items, 1):
            items_html += f'<li style="margin-bottom:12px;font-size:20px;color:{text_color};">{i}. {item}</li>\n'

        timeline_html = ""
        if content.timeline:
            timeline_html = f'<p style="font-size:16px;color:{accent};margin-top:24px;">建议时间窗：{content.timeline}</p>'

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;width:960px;height:540px;background:{bg};display:flex;flex-direction:column;justify-content:center;align-items:center;font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',sans-serif;">
  <div style="max-width:760px;text-align:center;padding:40px;">
    <h1 style="font-size:36px;color:{primary};line-height:1.3;margin-bottom:32px;font-weight:700;">
      {content.takeaway}
    </h1>
    <ul style="list-style:none;padding:0;margin:0;">
      {items_html}
    </ul>
    {timeline_html}
  </div>
</body></html>"""

    def prompt_fragment(self) -> str:
        return (
            "本布局用于 deck 结尾的行动号召页。"
            "内容要求：1个核心结论(takeaway, 15-40字) + 1-3个具体行动项(每项≤20字) + 可选时间线。"
            "不要写长段落，只写可执行的行动步骤。"
        )
```

### 修改文件

#### `pipeline/agents/plan_agent.py` — `_to_outline_result()` 出口

在现有 `content_items[-1]["narrative_arc"] = "closing"` 之后加一行：

```python
content_items[-1]["layout_hint"] = "call_to_action"
```

#### `pipeline/agents/html_design_agent.py` — `_generate_slide_html()`

在 title/agenda/section_divider 分支之后、LLM slot 路径之前，插入 registry 路由：

```python
from pipeline.layouts import LayoutRegistry

# Registry-typed layouts bypass LLM entirely
if slide_data.get("layout_hint") in LayoutRegistry.names():
    try:
        layout = LayoutRegistry.get(slide_data["layout_hint"])
        content = layout.content_schema(
            takeaway=slide_data.get("takeaway_message", ""),
            action_items=[b.get("content", "") for b in slide_data.get("text_blocks", []) if b.get("level", 0) > 0][:3],
            timeline="",
        )
        return layout.build_html(content, theme_colors, slide_index + 1, total_slides)
    except Exception as e:
        logger.warning("Slide %d: registry layout failed, falling through to LLM: %s", slide_index, e)
```

#### `pipeline/agents/design_strategies/templates.py` — `LAYOUT_HINT_MAP`

加一条：
```python
"call_to_action": "call_to_action",
```

#### `pipeline/agents/content_agent.py` — `_TEMPLATE_CONTENT_GUIDE`

加：
```python
"call_to_action": (
    "结尾行动号召页。生成 1 个核心结论(takeaway_message, 15-40字) + "
    "text_blocks 中 1-3 个具体行动项(level=1, 每项≤20字)。"
    "不要写长段落，只写可执行的行动步骤。"
),
```

### 测试

新文件 `tests/test_layout_registry.py`：

```python
class TestLayoutRegistry:
    def test_registry_has_call_to_action(self):
        from pipeline.layouts import LayoutRegistry
        assert "call_to_action" in LayoutRegistry.names()

    def test_registry_get_returns_layout(self):
        from pipeline.layouts import LayoutRegistry
        layout = LayoutRegistry.get("call_to_action")
        assert layout.name == "call_to_action"

class TestCTAContent:
    def test_valid_content(self):
        from pipeline.layouts.call_to_action import CTAContent
        c = CTAContent(takeaway="建议三个月内完成安全评估", action_items=["启动试点", "组建团队"])
        assert c.takeaway == "建议三个月内完成安全评估"

    def test_max_3_action_items(self):
        from pipeline.layouts.call_to_action import CTAContent
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="X" * 10, action_items=["a", "b", "c", "d"])

    def test_min_takeaway_length(self):
        from pipeline.layouts.call_to_action import CTAContent
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            CTAContent(takeaway="短")

class TestCTABuildHtml:
    def test_html_contains_takeaway(self):
        from pipeline.layouts import LayoutRegistry
        from pipeline.layouts.call_to_action import CTAContent
        layout = LayoutRegistry.get("call_to_action")
        content = CTAContent(takeaway="立即启动安全评估试点", action_items=["第一步", "第二步"])
        html = layout.build_html(content, {"primary": "#003D6E"}, 10, 10)
        assert "立即启动安全评估试点" in html
        assert "第一步" in html
        assert "第二步" in html

    def test_no_dup_prefix_in_output(self):
        from pipeline.layer6_output.html_dup_check import detect_dup_prefix
        from pipeline.layouts import LayoutRegistry
        from pipeline.layouts.call_to_action import CTAContent
        layout = LayoutRegistry.get("call_to_action")
        content = CTAContent(takeaway="建议三个月内完成安全评估并启动两个核心场景试点", action_items=["组建专项团队"])
        html = layout.build_html(content, {"primary": "#003D6E"})
        assert detect_dup_prefix(html) is None

class TestPlanAgentClosingLayout:
    def test_closing_slide_gets_call_to_action_hint(self):
        from pipeline.agents.plan_agent import PlanAgent
        agent = PlanAgent.__new__(PlanAgent)
        plan = {
            "slides": [
                {"page_number": 1, "slide_type": "title", "title": "T",
                 "section": "", "takeaway_message": "",
                 "primary_visual": "text_only", "narrative_arc": "opening"},
                {"page_number": 2, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "First content slide takeaway sentence here",
                 "primary_visual": "text_only"},
                {"page_number": 3, "slide_type": "content", "section": "Ch1",
                 "narrative_arc": "evidence",
                 "takeaway_message": "Last content slide closing takeaway sentence",
                 "primary_visual": "text_only"},
            ],
            "scqa": {"answer": "X"}, "root_claim": "X",
        }
        result = agent._to_outline_result(plan, scenario="季度汇报", framework_desc="SCR")
        content = [s for s in result["items"] if s.get("slide_type") == "content"]
        assert content[-1]["narrative_arc"] == "closing"
        assert content[-1]["layout_hint"] == "call_to_action"
```

### 验收标准

1. `pytest tests/test_layout_registry.py -v` → 全绿
2. `pytest tests/` → 97+ 全过（不退化）
3. Docker rebuild + E2E：closing slide 走 registry 而非 LLM HTML
4. 检查生成的 PPTX 最后 slide：有 36pt takeaway + numbered action items
5. dup-prefix detector 不对 registry 渲染的 slide 触发

### 工作量

- 新文件 3 个：~170 行
- 修改 4 个文件：~30 行
- 测试 1 个文件：~60 行
- **Total: ~260 行**

---

## Fix 7 (P1) — Action Title Prompt 约束 + Soft Warning

### 问题

~30% slide 的标题是描述性（"下一步行动建议"），不是 MBB 风格的 action title（带动词的结论句）。

### 调整后的策略（基于反馈）

不用硬 regex gate（假阴/假阳太多），改为三层：

1. **ContentAgent / PlanAgent prompt 显式约束**（首要）：
   - `pipeline/prompts/content_agent.v2.md` 加："每个 slide 的 takeaway_message 必须是带动词的完整结论句。反例：'风险概览'。正例：'数据投毒已成最高发威胁，可直接扭曲风控决策'"
   - `pipeline/prompts/plan_agent_system.md`（如存在）同步

2. **`_verify_plan` 只做 light heuristic**（命中只 log warning，不喂回 `_fix_plan`）：
   ```python
   for s in slides:
       if s.get("slide_type") not in ("content", "data"):
           continue
       title = s.get("takeaway_message") or s.get("title", "")
       if title and len(title) >= 8:
           has_verb = any(c in title for c in "应须建议将实现构建降低提升减少增加发现表明证明要求推动是")
           if not has_verb:
               logger.info("P%s takeaway may lack verb: %s", s.get("page_number"), title[:40])
   ```

3. **`_fix_plan` 现有 LLM retry 机制处理细粒度**（已有 path，不需新代码）

### 工作量

- prompt 文件 2 处：~10 行
- `_verify_plan` soft warning：~8 行
- 无新测试（warning 不影响行为）

---

## Fix 8 (P1) — Source 脚注渲染

### 问题

ContentAgent 收 `data_source` 字段（outline.items[].data_source），design layer 没渲染。MBB 每张图必有 "Source: …" 脚注。

### 实施

1. `pipeline/agents/design_strategies/templates.py` 在 `chart_focus` / `content_key_metrics` build_slots 透传 source：
   ```python
   slots["source_note"] = slide_data.get("data_source", "") or slide_data.get("source_note", "")
   ```

2. `pipeline/layer6_output/slide_templates.py` 对应模板加 footer slot：
   ```html
   <p style="position:absolute; bottom:30px; right:40px; font-size:10px; color:#999; font-style:italic;">
     Source: <<SOURCE_NOTE>>
   </p>
   ```

3. 当 `source_note == ""` 时不渲染（避免空 "Source: " 留迹）。

### 工作量

30 行 + 1 测试。

---

## Fix 10 (P1) — Bullet 长度 cap 120 字

### 问题

当前 bullet 100-180 字，MBB 标准 30-60 英文 words。中文信息密度更高，120 字 ≈ 40 英文词，是合理的起步上限。

### 实施

`pipeline/agents/content_agent.py` `_parse_single_page` 后加校验：

```python
overlong = []
for tb in data.get("text_blocks", []):
    if tb.get("level", 0) > 0 and len(tb.get("content", "")) > 120:
        overlong.append(len(tb["content"]))
if overlong:
    return ParseResult(
        error_kind="schema",
        error_msg=f"Bullets too long: {overlong}. Max 120 chars per bullet (Chinese). Rewrite shorter.",
        raw_data=data,
    )
```

会自动走 schema retry chain。

ContentAgent prompt 同步加："每个 bullet ≤120 字（中文），不允许超长段落"。

### 工作量

15 行 + 1 测试。

---

## Fix 11 (P2) — 颜色 Semantic Prompt-only

### 问题

当前 5 个 theme 各定义了 primary/secondary/accent，但 LLM 自由用 accent。MBB 规则：accent 全 deck 只用于"关键点"。

### 调整后的策略（基于反馈）

**短期只做 prompt 注入**，不做 pixel ratio 检测（Playwright 截图 + 抗锯齿 + DPI = 不稳定）。

1. `pipeline/agents/html_design_agent.py` LLM prompt 注入约束："accent 色（{accent_color}）仅用于：① takeaway 标题 ② 关键数字 ③ 1 个 callout。不允许：背景色、装饰条、次要文本"

2. Phase 3 registry 全部 layout 迁移后，accent 用法在模板级 hardcode（哪些 zone 允许 accent），不需要事后检测。

### 工作量

15 行（prompt 注入）。

---

## Fix 12 (P2) — Chart Annotation Callouts

### 问题

当前 chart 只画原始数据，没有 callout 标记关键点。MBB 标准：图上必有指向最重要数据点的小注释（"+47% YoY"）。

### 实施

`pipeline/layer6_output/chart_renderer.py` 在注入 chart 后追加 annotation shape。

前置：ContentAgent 输出 `chart_suggestion.key_annotation`（新字段，可选）。

### 工作量

80 行 + 1 集成测试。

---

## Fix 13 (P3) — Footer 设计

### 问题

当前仅 "P4/27" 极小字号。MBB 标准 footer：左下章节名 + 右下页码。

### 实施

`pipeline/agents/design_strategies/special_pages.py` 加全页 footer 渲染（非 cover/section_divider 都加）：

```python
@staticmethod
def render_footer_html(slide_data, theme_colors, total_slides, sections_list, current_section_idx):
    section_name = sections_list[current_section_idx] if 0 <= current_section_idx < len(sections_list) else ""
    page_n = slide_data.get("page_number", 1)
    return f"""
    <div style="position:absolute; bottom:8px; left:40px; font-size:9px; color:#666;">{section_name}</div>
    <div style="position:absolute; bottom:8px; right:40px; font-size:9px; color:#666;">{page_n} / {total_slides}</div>
    """
```

`_generate_slide_html` 在 LLM 返回 HTML 后注入 footer 到 `<body>` 末尾。

### 工作量

30 行 + 1 测试。

---

## Cleanup 1 — Phase 2 后过期 defensive code（一个月后）

Phase 2 schema 化保证了 ContentAgent 输出契约。下面这些下游 defensive 启发式可以删（前提是 Fix 5 + 真实 deck 跑稳一个月）：

| 文件 | 行 | 内容 | 删的理由 |
|---|---|---|---|
| `pipeline/agents/html_design_agent.py` | 613-632 | `_match_slides` 互斥清理块 | schema `enforce_visual_mutual_exclusion` 已保证 |
| `pipeline/agents/design_strategies/templates.py` | 451-461 | `_chart_has_data` | schema `enforce_visual_content_present` 已保证 |
| `pipeline/agents/design_strategies/templates.py` | 165-188 | `pick()` 的 icon_grid 启发式 | visual_block 结构化路径覆盖 |

---

## 关键约束（实施者必读）

1. **Docker-first**：所有改动必须 `docker-compose -f docker-compose.dev.yml up --build -d backend` 重新构建后跑。
2. **现有测试必须全过**：当前 `pytest tests/` 97+ 项全过，新增项不能让现有项 fail。
3. **LLM cost**：Fix 5 的 retry 会让破相 slide 多 1 次 LLM 调用。20 页 deck 约 +2 次，可接受。
4. **schema 修改 = 全栈影响**：Fix 9 / Fix 7/8/10/11/12/13 不动 schema。Phase 3 roll out 会大改，必须同步前端 SSE/checkpoint API。
5. **不要重新发明 PlanAgent 章节编号**：Fix 1 已 deterministic + canonical，后续 Fix 在它之上加约束，不要回退。
6. **commit message 格式**：`fix(html_design): ...` / `feat(plan): ...` / `feat(layouts): ...` / `chore: ...`
7. **每个 Task = 一个 PR**：独立可合并、独立可回滚。

---

## 参考资料

- `CLAUDE.md` — 项目架构 + 6-agent pipeline 说明
- `CONSULTING_TEMPLATE_REFERENCE.md` — MBB 对标素材 + 差距表 + Rubric
- `tests/test_plan_chapter_numbering.py` — Fix 1/6/Cleanup 2 测试
- `tests/test_html_dup_check.py` — Fix 5 测试
- `tests/test_schemas.py::TestPageWeightEnum` — Fix 4 测试
- `models/schemas.py` — pydantic 契约

---

## 每个 Task 完成后必做

1. `pytest tests/` 全绿
2. Docker 重新构建 + 跑一次完整流水线（用 `tests/test_e2e_html_render.py` 或手工上传 docx）
3. 用 `python3 -c "from pptx import Presentation; ..."` 检查输出 pptx 的具体 slide shape 结构
4. 不要把多个 Task 合并到一个 PR
