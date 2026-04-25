# PPTagent 改进工作清单 — Claude Code 任务

**适用版本**：基于 commit 29 (master)
**目标**:把"模板退化率 30%"压到 < 5%,解决预览/输出差异
**预估总工时**:8-12 小时(分 5 个 PR)

---

## 总体原则

每个任务都遵循下述流程:

1. **先读再写**:任何改动前先 `view` 相关文件,确认行号/字段名/函数签名
2. **小 PR**:每个 Task = 一个 PR,独立可合并、独立可回滚
3. **必须验证**:每个 Task 完成后,必须用 `tests/eval/` 跑一次或手工验证一个 .docx 输入,产出截图对比
4. **不破坏现有 API**:任何字段都用 `.get(key, default)` 兼容老数据,新加字段不能让旧 task_id 解析失败
5. **commit message 格式**:`fix(html_design): ...` / `feat(plan): ...` / `chore: ...`

---

## Task 1 — Heuristic 模板选择器(P0,先做)

### 背景
当前 `_fallback_html` 在 LLM 模板生成失败时,把整页退化成"takeaway 横条 + 一堆 `<p>` 段落"(见 `html_design_agent.py:523-580`)。这是用户看到的"输出与预览差很大"的最大单一根因。改造为:**完全脱离 LLM,根据 slide_data 结构特征自动选择 6 个模板之一**。

### 改动范围
仅 `pipeline/agents/html_design_agent.py`,不动其他文件。

### 具体步骤

**1.1** `view pipeline/agents/html_design_agent.py [1, 50]` 确认顶部 import 和常量位置。

**1.2** 在 `_CHROME_TEMPLATE` 定义之后(约 line 32)插入两个常量:
```python
_AUTO_ICONS = ["🎯", "💡", "📊", "⚙️", "🔍", "🚀", "🌟", "📈", "🛡️", "🤝"]
_COMPARISON_KEYWORDS = ("vs", " v.s.", "对比", "相比", "相较", "vs.", "对照", "差异", "区别")
_NUMERIC_TOKENS = ("%", "％", "亿", "万", "千", "倍", "x", "X", "k", "K", "M", "B")
```

**1.3** 确认 imports 含有 `from typing import Any, Dict, List, Optional, Tuple`,缺则补齐。

**1.4** 在 `_fallback_html` 方法**之前**插入新方法 `_heuristic_template_html` 及辅助方法。完整代码见 `/mnt/user-data/outputs/02_heuristic_template_picker.md` 的"新增方法"小节。

关键设计:
- `_heuristic_template_html(slide_index, slide_data, theme_colors, total_slides)` —— 入口
- `_pick_template_and_slots(slide_data, body_blocks, bold_blocks, title)` —— 决策树
- 6 个静态辅助:`_chart_has_data`, `_looks_like_comparison`, `_split_comparison`, `_infer_column_label`, `_has_numeric`, `_extract_metric`

**1.5** 修改 `_generate_slide_html` 中的两处 fallback 调用:
- line 283:`return self._fallback_html(...)` → `return self._heuristic_template_html(...)`
- line 326:同上

**1.6** **保留** `_fallback_html` 不动,作为 heuristic 内部异常时的最后兜底。

### 验收标准
- 用 `tests/test_e2e_html_render.py` 跑通,无新增失败
- 在容器内手动构造一个 `slide_data` 含 4 条等长并列要点,调用 `_heuristic_template_html`,生成的 HTML 应包含 `icon_grid` 模板的 grid div 结构(grep `width:263px` 或 `width:410px`)
- 在容器内构造一个 `slide_data` 含 3 条数字描述,生成的 HTML 应是 `content_key_metrics` 模板(grep `METRIC_BOXES_HTML`)
- 不调 LLM 也能生成像样的多模板 HTML

### Commit
`feat(html_design): heuristic template picker replaces dumb fallback`

---

## Task 2 — 真渲染版 inspect-loop(P0,做完 Task 1 再做)

### 背景
`_inspect_and_fix` 注释里写"Pre-validate HTML with a single-slide Node.js render",但 `html_design_agent.py:333` 实际只调了 `linter.validate(html)` —— 一个静态 CSS 白名单扫描,**发现不了 SVG 被吞、文字溢出、整页消失**这类只有真跑 html2pptx 才暴露的问题。这是退化页第二大根因。

### 改动范围
- 新建 `pipeline/layer6_output/html2pptx_validate.js`(单页 dry-run 脚本)
- `pipeline/layer6_output/node_bridge.py` 加方法 `validate_single_slide`
- `pipeline/agents/html_design_agent.py` 重写 `_inspect_and_fix`

### 具体步骤

**2.1** `create_file pipeline/layer6_output/html2pptx_validate.js`,内容见 `/mnt/user-data/outputs/01_real_render_inspect.md` 的"1. 新建" 小节。这是约 30 行的 Node.js 脚本,跑 html2pptx 但不写 pptx,只输出 JSON `{ok, errors}`。

**2.2** `view pipeline/layer6_output/node_bridge.py [120, 131]` 确认文件末尾结构,在 `is_node_available` 函数**之前**插入 `validate_single_slide` 方法(作为 `NodeRenderBridge` 类的方法)。完整代码见 patch 01 的"2." 小节。

**2.3** **替换** `pipeline/agents/html_design_agent.py:328-381` 整个 `_inspect_and_fix` 方法。新版本:
   - 同时收集 lint 错误和真渲染错误
   - 都通过才返回 html
   - 失败时调一次 LLM 修(prompt 加上"DIV 不能含裸文字"等具体约束)
   - 修不好走 Task 1 的 `_heuristic_template_html`(这就是为什么 Task 1 必须先做)

完整代码见 patch 01 的"3." 小节。

### 性能注意
每页验证多 ~2-5s 的 chromium 启动。如果 20 页 PPT 多 60s,可接受。**不要预优化做 browser pool**,先验证效果,后续如果延迟成瓶颈再做。

### 验收标准
- 故意构造一个含 `<svg>` 的 HTML,调 `validate_single_slide`,应返回 `ok=False`
- 故意构造一个内容溢出 540px 高度的 HTML,应返回 `ok=False` 且错误信息含"overflow"
- 端到端跑一个真实 .docx,日志中能看到 `Slide N: fix reduced errors X→Y` 的修复成功记录
- 跑完后输出 .pptx,Pre-Task-2 baseline 中"整页消失"的页应当全部恢复

### Commit
`fix(html_design): inspect-loop now does real Node render dry-run`

---

## Task 3 — 删除死代码 outline_agent.py

### 背景
`pipeline/agents/outline_agent.py` 已被 `plan_agent.py` 取代(见 plan_agent.py 文件头注释),orchestrator 不调用,仓库里只有自身遗留 import。`design_agent.py:84` 注释提到 OutlineAgent 但只是历史 comment,无实际引用。

### 改动范围
- 删除 `pipeline/agents/outline_agent.py`
- 改 `pipeline/agents/__init__.py` 移除 OutlineAgent export(如果有)
- 改 `pipeline/agents/design_agent.py:84` 注释,把"OutlineAgent LLM"改为"PlanAgent LLM"

### 具体步骤

**3.1** `bash_tool: cd $REPO && grep -rn "OutlineAgent\|from.*outline_agent\|import.*outline_agent" --include="*.py" | grep -v __pycache__`
确认所有引用。如果只剩文档/注释引用,可以安全删除。

**3.2** 删 `pipeline/agents/outline_agent.py`。

**3.3** 检查 `pipeline/agents/__init__.py`,如果含 `from .outline_agent import OutlineAgent` 类似行,删掉。

**3.4** `view pipeline/agents/design_agent.py [82, 88]`,把注释里的 `OutlineAgent LLM` 改为 `PlanAgent LLM`。

**3.5** 检查测试文件:`grep -rn "outline_agent\|OutlineAgent" tests/`,清理任何遗留引用。

### 验收标准
- `pytest tests/` 全绿
- `bash_tool: cd $REPO && grep -rn "outline_agent\|OutlineAgent" --include="*.py" | grep -v __pycache__` 应只返回 plan_agent.py 文件头的历史说明注释

### Commit
`chore: remove obsolete outline_agent.py (450 lines dead code)`

---

## Task 4 — Prompt 外置:plan_agent + html_design_agent

### 背景
`pipeline/prompts/` 下只有 `analyze_agent.v1.md` 和 `content_agent.v1.md`,plan_agent 和 html_design_agent 的 prompt 仍内嵌在 `.py` 文件里。这阻碍了:
1. eval baseline 的稳定性(prompt 改一行就要改 .py 重新部署)
2. A/B 测试不同 prompt 版本

### 改动范围
- 新建 `pipeline/prompts/plan_agent.v1.md`
- 新建 `pipeline/prompts/html_design_slot.v1.md`
- `pipeline/agents/plan_agent.py` 用 `base.py` 的 `load_prompt` 机制读取
- `pipeline/agents/html_design_agent.py` 同上

### 具体步骤

**4.1** `view pipeline/agents/base.py` 确认 prompt 加载机制(StructuredLLMAgent 基类的 prompt 加载方式)。如果有 `_load_prompt(version)` 类似方法,直接复用。

**4.2** `view pipeline/prompts/analyze_agent.v1.md` 看现有 prompt 文件的格式约定(可能有 frontmatter 或特殊分隔)。

**4.3** `view pipeline/agents/plan_agent.py [200, 350]` 找到 `_build_system_prompt` 和 `_build_user_prompt`,把里面的 prompt 字符串(尤其是大段示例 JSON 和叙事框架描述)迁出到 `plan_agent.v1.md`。

**4.4** 同样把 `html_design_agent.py:34-71` 的 `_SLOT_SYSTEM_PROMPT` 迁到 `html_design_slot.v1.md`。

**4.5** 在两个 .py 文件里改用:
```python
_SLOT_SYSTEM_PROMPT = self._load_prompt("html_design_slot", version="v1")
```
具体语法看 base.py 现有约定。

### 验收标准
- 两个 prompt 文件创建完成,内容与原 .py 内嵌字符串字节级一致
- 对同一个输入 task,Prompt 外置前后 LLM 调用的 system message 应**完全相同**(可加 print 对比)
- E2E 测试通过

### Commit
`refactor(prompts): externalize plan + html_design prompts to v1.md`

---

## Task 5 — layout_hint 字段贯通(P1,大改动,放最后)

### 背景
`OutlineItem.primary_visual` 只区分 chart/diagram/visual_block/text_only,力度太弱。让 PlanAgent 在大纲阶段直接打出 7 种 layout_hint(parallel_points / comparison / metrics / chart_focus / quote_emphasis / framework_grid / narrative),贯通到 ContentAgent(指导内容形态)和 HTMLDesignAgent(直接对应 6 个模板)。

### 改动范围
- `models/slide_spec.py` —— `OutlineItem` 加字段
- `pipeline/agents/plan_agent.py` —— prompt 加 layout_hint 说明,fallback 也加默认值
- `pipeline/agents/content_agent.py` —— prompt 加 LAYOUT_GUIDE 引导,entry 透传
- `pipeline/agents/html_design_agent.py` —— SLOT prompt 让 layout_hint 锁定 template_id;heuristic 函数也优先看 hint
- 数据库迁移:不需要(layout_hint 是 outline JSON 内字段,task_store 里 outline 整体序列化为 JSON)

### 具体步骤

**5.1 — 模型层** 改 `models/slide_spec.py:924`:
```python
@dataclass
class OutlineItem:
    page_number: int
    slide_type: str
    takeaway_message: str
    supporting_hint: str = ""
    data_source: str = ""
    primary_visual: str = ""
    narrative_arc: str = ""
    chunk_ids: list = field(default_factory=list)
    layout_hint: str = ""  # NEW
```

`OutlineResult.to_dict` 加 `"layout_hint": i.layout_hint`,`from_dict` 加 `layout_hint=i.get("layout_hint", "")`。

**5.2 — PlanAgent** 改 `pipeline/agents/plan_agent.py`:
- prompt 中(已外置到 .md)加入 layout_hint 取值表和选择规则。完整规则见 `/mnt/user-data/outputs/03_layout_hint_propagation.md` 的"2a." 小节
- `OutlineItem(...)` 构造处(line ~595)加 `layout_hint=i.get("layout_hint", "parallel_points")`
- `_fallback_plan` 里每个 item 加 `"layout_hint": "parallel_points"` 默认值

**5.3 — ContentAgent** 改 `pipeline/agents/content_agent.py`:
- 找到构造单页 prompt 的方法(grep `outline_page` 和 `text_blocks` 配合定位)
- 加入 `LAYOUT_GUIDE` dict 和 `guide` 拼接到 prompt 末尾,完整代码见 patch 03 的"3a." 小节
- `entry` dict (line ~546)透传 layout_hint:`"layout_hint": outline_page.get("layout_hint", "")`

**5.4 — HTMLDesignAgent** 改:
- `_SLOT_SYSTEM_PROMPT`(已外置到 .md)开头加"如果输入数据中存在 layout_hint 字段,直接对应模板"的最高优先级规则,见 patch 03 的"4a." 小节
- Task 1 的 `_pick_template_and_slots` 函数开头加 layout_hint 短路逻辑,见 patch 03 的"4b." 小节

**5.5 — 前端兼容** 检查 `frontend-react/src/components/wizard/Step2Outline.tsx`,大纲编辑页可能需要展示 layout_hint(可选,先做后端就行)。

### 数据库注意
**重要**:旧的 task_id 在 PostgreSQL 里的 outline JSON 没有 layout_hint 字段。所有读取处必须用 `.get("layout_hint", "parallel_points")` 默认值,不能让旧任务从 stage 回读时崩。

### 验收标准
- PlanAgent 跑完后,`curl localhost:8000/api/task/<id>/stage/plan | jq '.items[].layout_hint'` 应当返回多种取值的混合分布,而不是全 `parallel_points`
- 把 ContentAgent 用同一篇思科 SE 文档跑两次(layout_hint 启用前后)对比,启用后的 PPT 中 icon_grid/two_column/key_metrics 模板使用率应明显上升
- 端到端跑老的、没有 layout_hint 的 task,应能正常 resume(测兼容性)

### Commit
- `feat(models): add layout_hint to OutlineItem`
- `feat(plan): generate layout_hint in outline`
- `feat(content): use layout_hint to shape per-slide output`
- `feat(html_design): layout_hint short-circuits template selection`

---

## 跨任务的共同要求

### 日志诊断(每个 Task 都加)
在改动 `_inspect_and_fix`、`_generate_slide_html`、`_heuristic_template_html` 这些关键路径时,确保关键决策点有 INFO 级日志:
```python
logger.info("Slide %d: layout_hint=%s, picked template=%s", slide_index, hint, template_id)
logger.info("Slide %d: render-validate ok=%s, errors=%d", slide_index, ok, len(errors))
```
这样上线后能直接 grep 日志统计:
- 模板分布(看是否多样化)
- 失败率(看 fallback 触发频率)
- 修复成功率(看 inspect-loop 收益)

### Eval 跑通
做完 Task 1 + Task 2 后,**必须**跑一次 `tests/eval/run_eval.py` 生成 baseline.json(README 说目前还没跑过)。Task 5 完成后再跑一次,对比 rule_scorer 和 llm_judge 的得分变化。

### 不要碰的边界
- 不要改 `html2pptx.js` 主文件本身(那是 fork 自 Anthropic skill 的,改了未来同步上游会冲突)
- 不要动 `chart_renderer.py`(本次问题不在 chart 渲染逻辑,在数据缺失时的体面降级,Task 1 的 `_chart_has_data` 已经帮助处理)
- 不要在这五个 Task 内做 docker/CI/部署相关改动

### 实施顺序
```
Task 1 (heuristic picker)         ← 立刻见效,P0
   ↓
Task 2 (real-render inspect)      ← 依赖 Task 1 的 heuristic 兜底,P0
   ↓
Task 3 (delete outline_agent)     ← 独立,清债,任何时候都可做
   ↓
Task 4 (externalize prompts)      ← Task 5 的前置,把 prompt 文件化
   ↓
Task 5 (layout_hint)              ← 大改动,长期收益最大
```

Task 1 和 Task 2 是当前问题的直接修复。如果时间紧张,**只做这两个就能解决用户感知的"差别很大"问题**。Task 3-5 是结构性改进,可以分多次发布。

### 每个 Task 完成后必做
1. `pytest tests/` 全绿
2. 在 docker-compose.dev 跑一次完整流水线,用 `extract-text output.pptx` 检查内容,用 `pdftoppm` 转图片用 view 工具看视觉效果
3. 提交 PR,在 PR 描述里贴 before/after 截图对比
4. 不要把多个 Task 合并到一个 PR 里
