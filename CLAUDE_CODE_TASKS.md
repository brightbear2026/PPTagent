# PPTagent — 工作清单 v3

> **验收标准**：[`REQUIREMENTS.md`](./REQUIREMENTS.md)（唯一真相源）
> **灵感参考**：[`CONSULTING_TEMPLATE_REFERENCE.md`](./CONSULTING_TEMPLATE_REFERENCE.md)（部分作废，顶部有 banner）
> **本清单可直接交给 Claude Code 实施**，不需要会话上下文。
> **路径约定**：所有路径相对 `/Users/xiongzhou/project/PPTagent/`（Docker 内 `/app/`）。

---

## 文档体系

| 文档 | 作用 | 状态 |
|---|---|---|
| **REQUIREMENTS.md** | 验收标准（B2B 售前 deck），Hard SLO H1-H5 + Soft S1-S5 | **唯一真相源** |
| **CLAUDE_CODE_TASKS.md** | R1-R6 实施 spec（本文件） | 实施清单 |
| CONSULTING_TEMPLATE_REFERENCE.md | MBB 风格灵感参考（部分作废，有 banner） | 参考 |
| CLAUDE_CODE_TASKS.archive.v2.2026-05-01.md | 上一版（含完整内联代码 spec） | 历史归档 |
| CLAUDE_CODE_TASKS.archive.MBB.2026-04-30.md | MBB 对标版（Fix 7-13） | 历史归档 |
| CLAUDE_CODE_TASKS.archive.2026-04-29.md | 最早版 | 历史归档 |

---

## 已完成（不要重做）

| Fix | 内容 | Commit |
|---|---|---|
| Fix 1 | PlanAgent 章节编号 deterministic | ae51556 |
| Fix 4 | page_weight schema enum 加 transition | ae51556 |
| Fix 5 | HTMLDesignAgent dup-prefix detector + retry | ae51556 |
| Fix 6 | 章节页数均衡（_verify_plan 加约束） | 合入主线 |
| Cleanup 2 | narrative_arc 端点 deterministic | 合入主线 |
| Fix 7 | Action title prompt 强化 | 26a1f5e |
| Fix 8 | Source 脚注渲染 | 26a1f5e |
| Fix 10 | Bullet 长度 cap | 26a1f5e |
| Fix 12 | Chart annotation callouts | ee8e164 |
| Fix 13 | Footer with section name | ee8e164 |
| Phase 2 | Schema-centric pipeline (pydantic) | c008011 |
| Phase 3 | LayoutTemplate Registry 全部 8 layouts | 30241f7 |
| **R1** | chart_renderer slide_type 过滤（H3） | 4c97e29 |
| **R2** | ContentAgent chart 数据可溯源 validator（H4） | 8dcb9c6 |
| **R3** | Universal dup-prefix guard（H2） | dc10282 |
| **R4** | Layout fallback 测试矩阵 52 case | 8ac6f8b |
| **R5** | 5 个 B2B 售前 layout（13 total） | 3c028e3 |
| **R6** | dense_b2b theme | 2247394 |

## 已撤销（不要做）

| 任务 | 原因 |
|---|---|
| Fix 2 render_server.js UTF-8 | H3 是观察伪影，pptx 实际无乱码 |
| Fix 11 颜色 pixel ratio 严格化 | 售前 deck 不需要单 accent 严格约束 |
| Fix 9 单独 closing layout | Phase 3 的 call_to_action 已覆盖 |
| Bullet 60-80 字上限 | 改为 60-120 字（REQUIREMENTS.md §3.1） |
| White space ≥1cm 留白 | 反向需求 |
| MBB Rubric 评分 | 用 REQUIREMENTS.md §二 SLO 替代 |

---

## v4 Audit（基于 REQUIREMENTS.md SLO）

### Hard requirements — 5/5 pass（R1-R4 修后）

| ID | 状态 | 修复 |
|---|---|---|
| H1 章节编号一致 | ✅ Pass | — |
| H2 0 prefix-of-superset | ✅ **Fixed** | R3: universal guard + registry/heuristic degrade |
| H3 0 chart 误注入扉页 | ✅ **Fixed** | R1: chart_renderer slide_type filter |
| H4 数据可溯源 | ✅ **Fixed** | R2: traceability validator + chunk context |
| H5 章节名一致 | ✅ Pass | — |

### Soft requirements — 粗估

| ID | 状态 |
|---|---|
| S1 bullet 60-120 字 | ✅ ~80% 达标 |
| S2 章节 3-7 页 | ⚠️ Ch1 仅 2 页 |
| S3 Source 脚注 | ⚠️ Fix 8 已加渲染逻辑 |
| S4 Action title | ✅ 多数达标 |
| S5 ≥30% 含图表 | ⚠️ 需实际生成验证 |

---

## 实施顺序

```
Week 1 (P0 — 修 Hard requirements):
  R1  chart_renderer slide_type 过滤             [2h]
  R2  ContentAgent chart_suggestion 数据可溯源    [1d]
  R3  Universal post-render dup-prefix guard      [4h]
  R4  Layout fallback 单元测试矩阵                [1d]

Week 2-3 (P1 — 补售前必备 layout):
  R5.1-R5.5 五个新 B2B layout                    [5d]

Week 4 (P1 — 视觉密度 mode):
  R6  dense_b2b theme + 满版构图                  [2d]
```

**质量门槛**：R1-R4 完成 → 5/5 Hard pass → 可发布。R5-R6 → 售前 deck 完整能力。

---

## R1 — chart_renderer slide_type 过滤

**SLO**：H3 | **工作量**：2h

**问题**：`chart_renderer.py` 把 chart 注入到 section_divider / agenda / title 页面（v4 slide 9/17/20），无任何 slide_type 过滤。

**文件**：`pipeline/layer6_output/chart_renderer.py`

**实施要点**：`add_chart_to_slide()` / `render_into_pptx()` 入口加 slide_type 检查，`_CHART_FORBIDDEN_SLIDE_TYPES = frozenset({"section_divider", "agenda", "title"})`，命中则跳过注入（no-op + info log）。

**验收**：
1. 新测试 `tests/test_chart_renderer_slide_filter.py`：3 个 forbidden type 全跳过 + 1 个 content type 正常注入
2. Docker 重跑 v4：slide 9/17/20 不再出现 chart shape
3. 内容页 chart 不受影响

---

## R2 — ContentAgent chart_suggestion 数据可溯源

**SLO**：H4 | **工作量**：1d

**问题**：ContentAgent 输出的 chart_suggestion 中百分比/数字是 LLM 幻觉（v4 +540%/+1050%/+0%）。当前 `models/schemas.py` 的 `ContentSlideSchema` 有 `enforce_visual_content_present` + `enforce_visual_mutual_exclusion` + `enforce_bullet_length_cap` 三个 validator，但无数据溯源校验。`content_agent.py` 的 prompt 虽有"禁止编造"指令但无 post-hoc 验证。

**文件**：`models/schemas.py`、`pipeline/agents/content_agent.py`

**实施要点**：
- `ContentSlideSchema` 加 `enforce_chart_data_traceability` model_validator：提取 chart series values + so_what 中的百分比/大数字，与 ValidationContext 注入的 `raw_text` 交叉比对（±5% 容忍）；找不到则 raise ValidationError
- ContentAgent `_generate_one_slide()` 调 `model_validate(data, context={"raw_text": chunks_text, "tolerance": 0.05})` 注入 chunk 上下文
- `estimated: true` 字段跳过溯源检查
- Prompt 加 chart_suggestion 数据约束（4 条规则）
- Retry chain：溯源失败时告诉 LLM 标 estimated 或修正数字

**验收**：
1. `tests/test_chart_traceability.py` 4 case：可溯源通过、幻觉 540% 拒绝、estimated 跳过、±5% 容差
2. Docker 重跑：日志出现 "traceability retry" ≥3 次
3. 输出 pptx chart 数据可在源 docx grep 到（抽查 5 张）

---

## R3 — Universal post-render dup-prefix guard

**SLO**：H2 | **工作量**：4h

**问题**：`detect_dup_prefix` 已实现（`html_dup_check.py`，ratio=1.3）但非 universal——在 registry 路径只 log 不修（line 295），heuristic fallback 只 log（line 439），inspect-and-fix 只 log（line 536）。v4 slide 21 三槽 hero 布局走 registry 路径，漏检。

**文件**：`pipeline/agents/html_design_agent.py`、`pipeline/layer6_output/html_dup_check.py`

**实施要点**：
- 新增 `_enforce_dup_prefix_guard()` 方法作为 `_generate_slide_html()` 的统一出口
- 所有路径（LLM、registry、special_pages、fallback）产出 HTML 后必须过 detector
- Registry 路径命中 → 直接降级 text_only（deterministic 重试无意义）
- LLM 路径命中 → retry with error（max 2 次）→ 仍命中降级
- 其他路径命中 → 直接降级
- 确认 `detect_dup_prefix` 默认 ratio=1.3

**验收**：
1. `tests/test_universal_dup_guard.py`：registry 路径降级、clean HTML 直通、ratio=1.3 抓 v4 slide 21
2. Docker 重跑：0 处 prefix
3. 现有 `tests/test_html_dup_check.py` 仍全过

---

## R4 — Layout fallback 单元测试矩阵

**SLO**：防回归 | **工作量**：1d

**问题**：v3/v4 的 H2 bug 都是 layout fallback 路径引入的（visual_block 缺失时启发式拼 HTML 导致 prefix-of-superset）。当前测试只覆盖快乐路径。

**文件**：新建 `tests/test_layout_fallback_no_dup_prefix.py`

**实施要点**：
- 8 layout × 4 fixture（full / no_visual_block / no_text_blocks / minimal）= 32 参数化测试
- 每个 case 调 `layout.from_slide_data()` + `layout.build_html()`，过 `detect_dup_prefix(ratio=1.3)`
- Fixture 必须覆盖 fallback 路径（minimal fixture 逼 layout 走启发式）

**验收**：
1. `pytest tests/test_layout_fallback_no_dup_prefix.py -v` 32 个测试
2. R1-R3 修完后 32/32 pass

---

## R5 — 5 个 B2B 售前必备 layout

**SLO**：补必备能力 | **工作量**：5d（每个 1d）

每个按 Phase 3 LayoutTemplate Registry 模式：pydantic content_schema + `from_slide_data` + system-assembled `build_html` + 注册到 `LayoutRegistry` + prompt hint。

| ID | Layout | 数据形状 | 文件 |
|---|---|---|---|
| R5.1 | `tech_architecture` | 3-7 layers，每层 name + components[] | `pipeline/layouts/tech_architecture.py` |
| R5.2 | `capability_matrix` | 横轴（阶段）× 纵轴（维度），cell 有 status + note | `pipeline/layouts/capability_matrix.py` |
| R5.3 | `case_study` | 客户名 + 行业 + KPI 2-4 个 + 引言 + 实施周期 | `pipeline/layouts/case_study.py` |
| R5.4 | `solution_comparison` | 行=能力维度，列=方案选项，cell=score(best/good/average/poor) | `pipeline/layouts/solution_comparison.py` |
| R5.5 | `end_to_end_flow` | 4-7 阶段，每段 actor + action + output | `pipeline/layouts/end_to_end_flow.py` |

**每个 layout 验收**：
1. `from_slide_data` + `build_html` 实现完成
2. 注册到 `LayoutRegistry`（`pipeline/layouts/__init__.py`）
3. 加进 `LAYOUT_HINT_MAP`
4. R4 测试矩阵自动覆盖（每加一个 layout 多 4 case）
5. ContentAgent prompt 加对应 layout_hint 描述

**参考实现**：`pipeline/layouts/quote_emphasis.py`（Phase 3 标杆）

---

## R6 — `dense_b2b` Theme + 满版构图

**SLO**：视觉密度 | **工作量**：2d

**问题**：当前 5 个 theme 全是 minimalist 风格。售前 deck 需要满版构图（左文右图 50/50、顶部章节带、底部数据条）。

**文件**：`templates/themes/dense_b2b.json`、`pipeline/layer4_visual/theme_registry.py`、所有 layout 的 `build_html`

**实施要点**：
- Theme JSON：`density_mode: "dense"` + `section_color_1-6` + `content_split_ratio: 0.5` + header/footer bar height
- ThemeRegistry 注册 dense_b2b
- Layout build_html 读 `density_mode`，dense 模式下：padding 16px（vs 24px）、header bar 加章节色块、footer 显示章节名+页码
- 不影响现有 5 个 theme

**验收**：
1. ThemeRegistry 测试通过
2. dense_b2b 重跑：内容页文字密度 ≥50%（抽查 5 页）
3. 现有 theme 不受影响

---

## 关键约束

1. **REQUIREMENTS.md 是唯一真相**。本清单与它冲突时以后者为准。
2. **Docker-first**：`docker-compose -f docker-compose.dev.yml up --build -d backend`
3. **每 PR 一个 Task**：R1-R6 各 1 个 PR
4. **现有测试必须全过**：≥299 个现有测试不能 fail
5. **新 layout 必须过 R4 测试**：R5 每加一个 layout，R4 矩阵自动多 4 case
6. **LLM 成本不省**：schema retry ×3，效果优先（REQUIREMENTS.md §六）
7. **commit 格式**：`fix(quality): ...` / `feat(layouts): ...` / `feat(theme): ...`

---

## 验证流程（每个 PR 必跑）

1. **单测**：`pytest tests/ -v` 全绿
2. **Docker 集成**：rebuild backend，跑同份 docx 生成 pptx
3. **Audit**：提取 pptx shape 结构，对照 REQUIREMENTS.md §二 SLO 逐项核查
4. **5/5 Hard pass** 后 PR 才能合并

---

## 启动指令

```
请读 /Users/xiongzhou/project/PPTagent/REQUIREMENTS.md 和
/Users/xiongzhou/project/PPTagent/CLAUDE_CODE_TASKS.md，
按 R1 → R2 → R3 → R4 顺序实施，每个 R 一个 PR。
PR 描述里贴 audit 表对照（H1-H5 哪几条修了）+ before/after pptx shape 对比。
完成 R1-R4 后跑全 audit，确认 5/5 Hard requirement pass 后再启动 R5。
```
