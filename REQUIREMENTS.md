# PPTagent — 需求与验收标准

> **生成日期**：2026-04-30
> **本文档是验收标准**。`CONSULTING_TEMPLATE_REFERENCE.md` 仅作灵感参考，**不再作为对标目标**。
> 凡两文档冲突，以本文为准。

---

## 一、用途与受众

| 项 | 内容 |
|---|---|
| **直接用户** | 乙方售前工程师 / 解决方案工程师 |
| **最终读者** | 客户**中高层**（兼具决策权 + 技术理解力） |
| **使用场景** | 给客户做方案汇报，配合售前讲解 |
| **对标参考**（**不是 MBB 极简风**） | 华为白皮书、阿里云解决方案 deck、Gartner Magic Quadrant 报告、罗兰贝格 industry briefing、IDC 技术报告 |
| **明确不对标** | McKinsey/BCG/Bain 战略咨询 deck（白底大留白、一页一论点） |

风格定位：**信息密集型 B2B 方案 deck**——满版构图、专业图表、章节清晰、视觉精致。读者期待"能看出工程师懂行业、懂技术、懂客户问题"。

---

## 二、质量 SLO（5% 失败率分配）

允许的总失败预算：100 份 deck 里 ≤5 份"破相"。在此预算内分配如下：

### Hard requirements（必须 100%）

不达标 = 单 deck 即"破相"，计入失败预算。

| ID | 规则 | 验收方法 |
|---|---|---|
| H1 | 章节编号一致：目录 / 章节扉页 / 正文标题三处编号同步 | 自动化：parse pptx + 比对三处 |
| H2 | 0 处 prefix-of-superset 双重渲染（同 slide 内短文本是另一长文本的前缀且 ratio ≥ 1.3） | `detect_dup_prefix(ratio=1.3)` 在所有 build_html 出口跑 |
| H3 | 0 处 chart 误注入扉页/封面/目录页 | `chart_renderer` 检查 `slide_type ∉ {section_divider, agenda, title}` |
| H4 | 图表数据可溯源：图中所有百分比 / 大数字能在源文档 chunk 里找到（容忍 ±5%） | ContentAgent schema validator 强制 |
| H5 | 章节扉页 + 目录的章节名与正文章节标题字符串完全一致 | 已由 `_to_outline_result._strip_chapter_prefix` 保证 |
| H6 | Content slide 必须 ≥ 8 visible elements（slide_type ∈ {title, agenda, section_divider} 豁免），且不含禁止占位符 | parse pptx 检查 shape count + placeholder char scan |

### Soft requirements（≥95%）

每个 SLO 在 100 份 deck 中允许 ≤5 份不达标。

| ID | 规则 |
|---|---|
| S1 | bullet 长度 60-120 字（B2B 售前需要保留细节论据） |
| S2 | 章节页数 3-7 页（不要 1 页章节，也不要 10 页超长章节） |
| S3 | 每张图带 source 脚注（"Source: …" 或 "数据来源：…"） |
| S4 | 每页有 action title（带动词的结论句，非纯名词短语） |
| S5 | 全 deck 至少 30% 内容页含图表 / diagram / framework grid |

---

## 三、视觉与内容设计原则（**与 MBB 反向**）

### 3.1 内容密度

| 项 | MBB 风格 | **本产品要求** |
|---|---|---|
| 文字像素覆盖 | < 60% | **50-75%** |
| 单页论据数 | 3-4 | **6-8** |
| Bullet 字数 | 30-60 字 | **60-120 字** |
| 留白 | 极多 | **节制使用，不留大片空白** |

售前 deck 的密度逻辑：客户可能事后翻阅而非现场听讲，每页要"自带上下文"——光看一页就能理解论点 + 证据 + 出处。

### 3.2 颜色用量

不强制 MBB 的"2-3 色封顶"。允许：

- 主色 + 副色 + accent 色（3 色）
- 章节色：每章可有自己的色调标识（在章节扉页 + 该章页面 footer 强调色变化）
- 数据可视化：图表内最多 5-6 色（不强求灰阶背景 + 单 accent）
- Bain 风极简红黑、Deloitte 多色 teal/blue 都是可借鉴**风格**，但不是验收门槛

### 3.3 图表专业化

**核心要求**：图表不是装饰，是论据。

| 强制项 | 说明 |
|---|---|
| Source 脚注 | 每张图必须有"Source: …"或"数据来源：…" |
| 数据可溯源 | 图中数字必须能在源文档找到（允许 ±5% 估算容差） |
| 单位明确 | 百分比 / 万 / 亿 / 倍 等单位明确标注 |
| Y 轴起点 | 起点必须为 0（除非明确标注"非零起点"） |
| 系列限制 | 单图最多 6 系列；超过拆图或换 small multiples |

**禁止项**：
- LLM 幻觉百分比（如 +540%、+1050%、+0% 这种当前 v4 出现的情况）
- 不可解释的"+0%"占位
- 单一 chart 注释里出现源文档没有的数字

### 3.4 章节扉页

售前 deck 的章节扉页**应该有视觉冲击**——不是简单的"第N章 标题"白底页。

要求至少包含：
- 章节编号（"第N章"或"01-06"形式）
- 章节标题
- 章节核心论断（1 句话副标题）
- 可选：大数字 / 关键引言 / 主题图

### 3.5 明确禁止的 layout 风格

B2B 售前 deck 永远不允许出现的页面形态：

**禁止 1: hero_splash 风格**
- 特征：≤5 shapes / 中央巨型字符（fs ≥ 48pt）/ 仅 1-2 行文字
- 已删除模板：slide_templates.py 的 "hero_splash"
- 替代：page_weight=hero 强制 demote 到 framework_grid / parallel_points

**禁止 2: 单引言 quote 风格（稀疏）**
- 特征：仅 1 个引言 + 0-1 条副文，整页文字 < 100 字
- 处理：quote_emphasis 必须含 ≥3 sub_bullets（schema min_length=3）

**禁止 3: 任何中央装饰符号占位**
- 特征：<>、◇、□、—、N/A 等占位字符以大字号（fs ≥ 24pt）渲染
- 处理：所有 layout 的"无数据"分支必须隐藏整个元素，不允许显示占位符

---

## 四、必备 Layout 清单

当前 8 个通用 layout（call_to_action, quote_emphasis, parallel_points, metrics, chart_focus, comparison, framework_grid, narrative）保留，**新增 5 个 B2B 售前必备 layout**：

| Layout | 用途 | 数据形状 |
|---|---|---|
| `tech_architecture` | 多层级技术栈 | 3-7 layers，每层有 name + components[] |
| `capability_matrix` | 能力维度对比 | 横轴（时间/阶段）× 纵轴（维度），单元格含图标/状态 |
| `case_study` | 客户案例卡 | 客户 logo + 关键 KPI（3 个）+ 引言 + 实施周期 |
| `solution_comparison` | 方案 vs 竞品对比 | 表格：行=能力维度，列=方案选项，单元格=有/无/优劣 |
| `end_to_end_flow` | 端到端业务流 | 4-7 阶段流程，每段 actor + action + output |

每个新 layout 都按 Phase 3 LayoutTemplate Registry 模式实现：
- pydantic content schema
- system-assembled `build_html`（不让 LLM 自由写 HTML）
- 单测覆盖 fallback path（无 visual_block 时也不破相）

---

## 五、降级规则

LLM 多花一点没关系，但失败时要**优雅降级**而非崩溃。

| 触发条件 | 降级动作 |
|---|---|
| Schema validation 失败 | retry 最多 3 次（错误信息塞回 prompt） |
| 3 次 retry 仍失败 | 降级到 text_only layout，记录到 task metadata 的 warnings 数组 |
| 图表数据无法溯源 | 加标签 "基于行业平均估算" 或 "估算值，待校对"，**不删图表** |
| 单页 build_html 命中 dup-prefix detector | 重试 1 次；仍命中 → 降级 text_only |
| Layout 命中"明确禁止"风格（H6 失败 / shape < 8 / 含禁止占位符） | 直接降级 framework_grid（text_blocks 转 grid items），记 ERROR 日志 |
| Chart 误判要注入到 section_divider | 直接跳过注入，不报错 |
| 整个 deck 失败率 > 30% | 整个任务标 failed，但已生成的部分保留供用户参考 |

前端 UI 应当显示 task metadata 的 warnings，让用户知道哪些 slide 走了降级路径。

---

## 六、成本与时间约束

| 项 | 限制 |
|---|---|
| 单 deck LLM 调用次数 | 不设硬上限，效果优先 |
| 单 deck 生成时间 | 5-15 分钟可接受（含 retry + schema validate） |
| 并发上限 | 沿用现有 MAX_CONCURRENT=4（per-slide 并行） |
| 重试次数 | 每个 schema validation 最多 3 次 retry |

**指导原则**：宁可多调 5 次 LLM 把数据校对清楚，也不要省 token 出一份有幻觉数据的 deck——售前场景里，一个错数据可能让客户对整个方案失去信任。

---

## 七、当前版本（v4）Audit

基于本文 SLO 对 v4 那份 pptx 逐项打分。

### Hard requirements

| ID | 状态 | 详情 |
|---|---|---|
| H1 章节编号一致 | ✅ Pass | 6 章一/二/三/四/五/六 全对齐 |
| H2 0 prefix-of-superset | ❌ **Fail** | slide 21 命中（三槽 hero 布局漏修） |
| H3 0 chart 误注入扉页 | ❌ **Severe Fail** | slide 9 / 17 / 20 三个 section_divider 全被注入 chart |
| H4 数据可溯源 | ❌ **Severe Fail** | "+540% / +1050% / +0%" 明显是 LLM 幻觉 |
| H5 章节名一致 | ✅ Pass | |

3/5 Hard requirements 不达标。**当前 v4 不可发布**——任意一份 deck 出货必然踩 H3 + H4。

### Soft requirements（粗估）

| ID | 状态 |
|---|---|
| S1 bullet 60-120 字 | ✅ ~ 80% 达标，部分超长 |
| S2 章节 3-7 页 | ⚠️ Ch1 仅 2 页偏少 |
| S3 Source 脚注 | ❌ 0 张图带脚注 |
| S4 Action title | ✅ 多数达标 |
| S5 ≥30% 内容页含图表 | ⚠️ 实际仅 ~15%（27 页里 2 张 chart） |

---

## 八、修订后路线（R1-R6）

之前 `CLAUDE_CODE_TASKS.md` 里 Fix 7-13 的 13 个任务**部分作废**（特别是基于 MBB minimalist 假设的那些）。新路线按本文 SLO 优先级排：

### P0 — 1 周内（修 Hard requirement 不达标项）

| ID | 内容 | 工作量 |
|---|---|---|
| **R1** | `chart_renderer.py` 加 `slide_type` 过滤：section_divider / agenda / title 不允许注入 chart。修 H3。 | 2 小时 |
| **R2** | ContentAgent `chart_suggestion` schema 加 "数据可溯源" validator：so_what 中所有百分比 / 大数字必须能在 chunk_ids 对应 raw_text 找到（±5% 容忍）；找不到则标 `"estimated": true` 或拒收 retry。修 H4。 | 1 天 |
| **R3** | Universal post-render guard：`detect_dup_prefix(ratio=1.3)` 在所有 build_html 出口（LLM、registry、special_pages、slide_templates）都跑，命中即重试或降级。修 H2。 | 半天 |
| **R4** | Layout fallback 单元测试矩阵：8 layout × 4 fixture（含/不含 visual_block × 含/不含 chart_data）共 32 参数化测试，钉死 H2 类回归。 | 1 天 |

### P1 — 2 周内（补售前必备能力）

| ID | 内容 | 工作量 |
|---|---|---|
| **R5** | 新增 5 个垂直 layout：`tech_architecture`, `capability_matrix`, `case_study`, `solution_comparison`, `end_to_end_flow`。每个按 Phase 3 registry 模式实现。 | 5-7 天 |
| **R6** | Theme 系统新增 `dense_b2b` 模式：满版构图（左文右图 50/50）、顶部章节带、底部数据条、章节色；与现有 5 个 minimalist theme 并存。 | 2 天 |

### 不做（之前 plan 里的，与新需求冲突）

- ~~Fix 11 颜色 semantic 严格化（pixel ratio 检测）~~ —— 售前 deck 不需要单 accent 严格约束
- ~~Fix 10 bullet 80 字上限~~ —— 改为 60-120 字（已包含在 S1）
- ~~"白空间最大化"类优化~~ —— 反向需求

### 保留（之前 plan 里仍有效的）

- Fix 8 Source 脚注渲染（覆盖 S3）
- Fix 7 Action title 校验（覆盖 S4，但用 prompt + soft warning，不用硬 regex）
- Phase 3 LayoutTemplate Registry 已完成，R5 在其基础上扩展

---

## 九、与 `CONSULTING_TEMPLATE_REFERENCE.md` 的关系

`CONSULTING_TEMPLATE_REFERENCE.md` 在本次需求对齐前编写，部分内容**作废**：

| 章节 | 状态 | 说明 |
|---|---|---|
| 第一部分 真实素材库 | ✅ 仍有效 | MBB 真实 deck 链接作灵感参考 |
| 第二部分 §1 Action Title | ✅ 仍有效 | 售前 deck 也需要 action title |
| 第二部分 §2 Pyramid Principle | ✅ 仍有效 | 论证结构通用 |
| 第二部分 §3 排版规则 | ⚠️ 部分作废 | 字体规则保留；正文 ≥18pt 与售前密集排版不矛盾 |
| 第二部分 §4 颜色规则 "2-3 色封顶" | ❌ **作废** | 售前 deck 允许 3+ 色 |
| 第二部分 §5 图表注释 | ✅ 仍有效 | 注释短、有方向、关键数据点 highlight |
| 第二部分 §6 White space "≥1cm 留白 < 60% 文字" | ❌ **作废** | 售前 deck 要 50-75% 文字密度 |
| 第二部分 §7 MECE | ✅ 仍有效 | |
| 第三部分 13 项 gap 表 | ⚠️ 部分作废 | gap G3 charts 数量、G6 bullet 长度、G9 white space 已被本文覆盖 |
| 第四部分 Fix 7-13 spec | ⚠️ 部分作废 | 见上 §8"不做"小节 |
| 第五部分 MBB Rubric | ❌ **作废** | 用本文 §2 SLO 替代 |

`CONSULTING_TEMPLATE_REFERENCE.md` 顶部应加 banner 指向本文。

---

## 十、reviewer checklist

提交 PR 前自查：

- [ ] 改动是否对 Hard requirements (H1-H6) 有正向影响？哪一条？
- [ ] 改动是否引入新的 Hard requirement 风险？跑了 fallback 测试？
- [ ] 改动是否违反 §3.5 禁止 layout 列表？
- [ ] 改动是否符合"内容密度高 + 信息密集"方向，而非 MBB 极简？
- [ ] 改动是否在 v4 audit 表里有对应 fix？哪一项？
- [ ] 改动有对应单测吗？测试 fixture 是否覆盖 fallback path？
