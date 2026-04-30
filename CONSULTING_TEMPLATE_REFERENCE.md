# PPTagent — 四大咨询风格参考与质量基线

> **目的**：把 MBB（McKinsey/BCG/Bain）+ Big 4（Deloitte/PwC/EY/KPMG）的真实输出作为 PPTagent 的质量目标。
> **用法**：本文作为 PR review 时的"对标参照"。新功能/新 layout 完成后，对比下面的 gap 表逐项打分。
> **配套文件**：实施任务在 `CLAUDE_CODE_TASKS.md`，本文只列**目标**和**素材**。

---

## 第一部分：真实素材库（下载链接）

下面 URL 全部公开发布，可直接下载学习。建议每位实施者至少完整看 1 份 BCG slideshow + 1 份 McKinsey 报告。

### McKinsey 2025/2026 报告（PDF）

| 报告 | 适合学的层面 | URL |
|---|---|---|
| **Technology Trends Outlook 2025**（5th edition, July 2025） | 主题分章、技术 framework 图解、长报告章节扉页设计 | https://www.mckinsey.com/~/media/mckinsey/business%20functions/mckinsey%20digital/our%20insights/the%20top%20trends%20in%20tech%202025/mckinsey-technology-trends-outlook-2025.pdf |
| **The State of AI** (March 2025) | 数据图表 + 行动型 takeaway 标题 | https://www.mckinsey.com/~/media/mckinsey/business%20functions/quantumblack/our%20insights/the%20state%20of%20ai/2025/the-state-of-ai-how-organizations-are-rewiring-to-capture-value_final.pdf |
| **Global Private Markets Report 2025** | 多章节叙事、数据可视化密度 | https://www.mckinsey.com/~/media/mckinsey/industries/private%20equity%20and%20principal%20investors/our%20insights/mckinseys%20global%20private%20markets%20report/2025/global-private-markets-report-2025-braced-for-shifting-weather.pdf |
| **M&A Annual Report 2025** | 趋势报告范式、章节扉页 | https://www.mckinsey.com/alumni/~/media/mckinsey/business%20functions/m%20and%20a/our%20insights/top%20m%20and%20a%20trends%20report/m-and-a-annual-report-2025-v3.pdf |
| **The State of Organizations 2026** (Feb 2026) | 最新组织报告设计语言 | https://www.mckinsey.com/~/media/mckinsey/business%20functions/people%20and%20organizational%20performance/our%20insights/the%20state%20of%20organizations/2026/the-state-of-organizations-2026.pdf |

### BCG Slideshow PDF（直接 PPT 风格）

最贴近 PPTagent 输出形态的素材。

| 报告 | URL |
|---|---|
| **AI at Work 2025**（June 2025，slideshow 形式） | https://web-assets.bcg.com/fd/0d/bcc5dfae4cbaa08c718b95b16cf5/ai-at-work-2025-slideshow-june-2025-edit-02.pdf |
| **AI Radar 2025: From Potential to Profit**（Jan 2025） | https://web-assets.bcg.com/0b/f6/c2880f9f4472955538567a5bcb6a/ai-radar-2025-slideshow-jan-2025-r.pdf |
| **The Widening AI Value Gap**（Sept 2025） | https://media-publications.bcg.com/The-Widening-AI-Value-Gap-Sept-2025.pdf |
| **Maximizing Value Potential from AI in 2025**（Feb 2025） | https://media-publications.bcg.com/BCG-Executive-Perspectives-Future-of-Procurement-with-AI-2025-27Feb2025.pdf |
| **Driving Sustainable Cost Advantage with AI**（May 2025） | https://www.bcg.com/assets/2025/executive-perspectives-driving-sustainable-cost-advantage-with-ai-20may.pdf |

### 聚合站（含 Bain / Deloitte / EY 等）

- **Slideworks 750+ 真实咨询 PPT**（含 McKinsey/Deloitte/EY 等，可下载） — https://slideworks.io/resources/750-real-consulting-presentations-from-mckinsey-deloitte-ey-and-more
- **Slideworks 100+ McKinsey 真实 PPT** — https://slideworks.io/resources/47-real-mckinsey-presentations
- **Slideworks 55+ Bain 真实 PPT** — https://slideworks.io/resources/30-real-bain-presentations
- **Analyst Academy 600+ 咨询 PPT** — https://www.theanalystacademy.com/consulting-presentations/

### 风格指南（解构 MBB 设计原则）

- **Decoding McKinsey's new visual identity** — https://slideworks.io/resources/decoding-mckinseys-visual-identity-and-powerpoint-template
- **Pillar consulting presentations guide (Deckary)** — https://deckary.com/blog/pillar-consulting-presentations-guide
- **Consulting Slide Standards: McKinsey/BCG/Bain rules** — https://deckary.com/blog/consulting-slide-standards
- **How to Write Action Titles Like McKinsey** — https://slideworks.io/resources/how-to-write-action-titles-like-mckinsey
- **Pyramid Principle & SCQA Consultant's Guide** — https://deckary.com/blog/pyramid-principle-consulting

---

## 第二部分：MBB 设计原则（蒸馏）

### 1. Action Title — 每页标题是带动词的完整结论句

BCG 1990s 提出的术语。标题不写"这页讲什么"（描述），写"读者应该相信什么"（结论）。

**反例**（描述性标题）：
- "数据投毒风险概览"
- "防护方案介绍"
- "下一步行动建议"

**正例**（行动型结论）：
- "数据投毒已成最高发威胁，可直接扭曲风控决策"
- "纵深防御四层架构使核心参数泄露率下降 80%"
- "建议三个月内完成安全评估并启动两个核心场景试点"

**判别公式**：标题里有动词 + 有可证伪的论断 = action title。如果只是名词短语或主题描述 = 不合格。

### 2. Pyramid Principle — 答案在最上方，证据往下走

Barbara Minto, McKinsey 1960s。每张 slide 是个 mini pyramid：

```
         Action Title  (主张, 1 句话)
              │
       ┌──────┴──────┐
   Subheading 1   Subheading 2   (2-3 个支持论点)
       │              │
   Bullets/Chart   Bullets/Chart  (具体证据)
```

**关键规则**：
- 一张 slide 一个论点（"and"出现 = 应拆成两张）
- 翻 50 页只看标题，能完整理解全部论证

### 3. 排版规则

| 项 | 标准 |
|---|---|
| **正文字体** | McKinsey: Arial / BCG/Bain: Helvetica or Calibri / Deloitte: Open Sans |
| **标题字体** | McKinsey: Georgia (近期新品牌) / 多数 MBB: 同正文 sans-serif 加粗 |
| **正文字号** | ≥18pt（"会议室最后一排能读清"），通常 18-24pt |
| **标题字号** | ≥24pt，通常 28-36pt |
| **行间距** | 1.3-1.5x，紧凑但不挤 |
| **同元素字号一致** | 同类元素永远同字号（标题/标题、bullet/bullet、注释/注释） |

### 4. 颜色规则

| 公司 | 主色 | 强调色 | 备注 |
|---|---|---|---|
| **McKinsey** | 深蓝 (#003D6E) + 白 | 金/铜 (#B8860B 或 #C8A157) | 近期新版加深蓝 |
| **BCG** | 深绿 (#00553A) + 黑 | 浅绿/灰 | 经典"BCG green" |
| **Bain** | 黑 + 白 | **红 (#CC0000)**（仅用于关键论点） | 极简风，红色含金量极高 |
| **Deloitte** | 绿/青/蓝（teal #86BC25） | 红仅用于热力图 / 警告 | 多色但功能性 |

**核心规则（所有 MBB 共通）**：
- **2-3 色封顶**，不超过 3 色
- **1 个 accent 色全 deck 只用于"想让读者注意的那一处"**——图表里的关键数据点、key takeaway 句子、不超过整页 5% 像素
- 其余元素用中性灰阶（#666666 / #999999 / #CCCCCC）

### 5. 图表注释规则

- 图表本身只画数据，**关键洞察用 callout 标记出来**
- callout 短（≤10 字）、带方向（箭头指数据点）
- 关键系列用 accent 色，其余系列用 gray scale
- **每张图配一个 source 脚注**："Source: BCG AI at Work Survey 2025, n=10,635"

### 6. White space 与密度

- 上下左右留白 ≥ 1cm（页面 16:9 / 25.4×14.3cm 时）
- bullet 单条 30-60 字（PPTagent 当前 100-180 字 = 过长）
- 一页文字密度 < 60% 像素覆盖率

### 7. MECE 原则

**M**utually **E**xclusive, **C**ollectively **E**xhaustive。所有分类必须满足：
- 类别之间不重叠（互斥）
- 类别合在一起覆盖问题全集（穷尽）

PPTagent 的 issue_tree / framework_grid 模板**应当**强制 MECE 验证（目前没有）。

---

## 第三部分：PPTagent 当前 vs MBB 目标 — 差距表

按生成 GRC deck 的实测结果（27 页输出）打分。

| Gap | 当前状态 | MBB 标准 | 优先级 | 修复路径 |
|---|---|---|---|---|
| **G1 Action Title** | 部分 slide 已是 action title（如"风险全景图：从芯片到退役..."），但 closing slide "下一步行动建议" 是描述性 | 100% slide 必须是带动词的结论句 | P1 | PlanAgent prompt + verify_plan 加 verb-presence 校验 |
| **G2 Closing Slide 弱** | 最后一页只是 bullet 罗列 + 还撞 H1 bug | 强 CTA / 大数字 stat / 联系方式或 Q&A 页 | P0 | Fix 5（H1 patch）+ 加 closing-specific layout |
| **G3 Charts 数量** | 27 页只有 2 张图（7.4%） | 30-50% slide 有数据可视化 | P1 | ContentAgent prompt 强化 chart suggestion；分析层做更多 derived_metrics |
| **G4 图表注释缺失** | 当前 chart 直接渲染，无 callout | 关键点必须有 annotation 指向 | P2 | chart_renderer 加 annotation 层 |
| **G5 颜色 semantic** | 5 个 theme 各有主色但 accent 全页随便用 | accent 仅用于"key takeaway"区域 | P2 | ThemeRegistry 加 `accent_usage_rule`，design layer 强制 |
| **G6 Bullet 过长** | 单条 100-180 字 | 30-60 字 | P1 | ContentAgent prompt 加 bullet length cap + 校验拒收 |
| **G7 Source 脚注** | 0 张图带 source | 每张图必须有 source 脚注 | P1 | content_agent 收 `data_source` 已经存在，design layer 渲染缺失 |
| **G8 章节页数失衡** | Ch3=1 页 / Ch6=1 页 / Ch4=7 页 | 每章 3-6 页 | P2 | Fix 6（已在任务清单） |
| **G9 White space** | bullet 文本密度高，留白不足 | 留白≥1cm，文字 ≤60% | P2 | layout 模板 padding 加大 |
| **G10 Footer** | 仅 "P4/27" 极小字号 | 章节名 + 页码 + 公司 logo | P3 | special_pages 加 footer slot，从 sections_order 取章节名 |
| **G11 MECE 验证** | issue_tree / framework_grid 无验证 | 分类必须 MECE | P3 | LLM prompt 强化 + 后置验证（重叠检测）|
| **G12 章节扉页设计** | 简洁但平淡 | MBB 章节扉页常带大数字 / 关键引言 | P3 | section_divider_html 加可选 stat slot |
| **G13 Cover 页设计** | 当前简洁但缺信息层次 | 标题 + 副标题 + 日期 + 客户 logo + 报告类型标签 | P3 | cover_slide_html 扩展 fields |

### 总分（粗估）

按 13 个维度，每项满分 10 分：

| 维度 | 当前估分 |
|---|---|
| 内容结构（pyramid + action title） | 7/10 |
| 视觉密度 + 留白 | 5/10 |
| 数据可视化 | 4/10 |
| 颜色 semantic | 5/10 |
| Source / 学术规范 | 2/10 |
| Footer / Cover 设计 | 4/10 |
| **整体 vs MBB** | **约 4.5/10** |

把 G1-G7（P0/P1）解决后，预计可达 7/10。再做 G8-G10 可达 8/10。G11-G13 是锦上添花，9+/10 需要 Phase 3 LayoutTemplate registry 上线后才有架构基础。

---

## 第四部分：建议加入 `CLAUDE_CODE_TASKS.md` 的新任务

在现有 Fix 5/6 之后，按 ROI 顺序：

### Fix 7 (P1) — Action Title 强制校验

`pipeline/agents/plan_agent.py` `_verify_plan` 加：

```python
import re

VERB_PATTERN = re.compile(
    r'(.*?)(应|须|需要|建议|可以|将|实现|建立|构建|完成|降低|提升|减少|增加|发现|揭示|表明|证明|要求|推动|赢得|带来|阻断|防止|避免|是|为|缺乏|存在|占|超过|达到)'
)

for s in slides:
    if s.get("slide_type") not in ("content", "data"):
        continue
    title = s.get("takeaway_message", "") or s.get("title", "")
    if not VERB_PATTERN.search(title):
        issues.append(
            f"P{s.get('page_number')} 标题缺动词，是描述而非结论。"
            f"当前: {title!r}。改写为含动词的完整句子。"
        )
```

工作量：20 行 + 3 测试。

### Fix 8 (P1) — Source 脚注渲染

ContentAgent 已经收 `data_source` 字段（`outline.items[].data_source`），但 design layer 没渲染。

`pipeline/agents/design_strategies/templates.py` 在 `chart_focus` / `content_key_metrics` 模板的 build_slots 里把 source 字段透传：

```python
slots["source_note"] = slide_data.get("data_source", "")
```

`pipeline/layer6_output/slide_templates.py` 对应模板加 footer：

```html
<p style="position:absolute; bottom:30px; right:40px; font-size:10px; color:#999;">
  Source: <<SOURCE_NOTE>>
</p>
```

工作量：30 行 + 1 测试。

### Fix 9 (P0+) — Closing Slide 专属 Layout

PlanAgent 出口标记最后一个 content slide 为 closing：

```python
if content_items:
    content_items[-1]["narrative_arc"] = "closing"
    content_items[-1]["layout_hint"] = "call_to_action"  # 新 hint
```

`pipeline/layer6_output/slide_templates.py` 加新模板 `call_to_action`：
- 一个超大 takeaway（48pt）居中
- 下方 1-3 个 step bullet（每条 ≤20 字）
- 右下角联系信息或日期

工作量：40 行（new layout）+ 20 行 PlanAgent 改 + 2 测试。可与 Cleanup 2 合并。

### Fix 10 (P1) — Bullet 长度 cap

ContentAgent prompt 加硬性约束 + post-validate：

```python
for tb in slide.get("text_blocks", []):
    if tb.get("level", 0) > 0 and len(tb.get("content", "")) > 80:
        # Bullet 超过 80 字 → 拒收，让 LLM 重写
        issues.append(f"P{pn} bullet 过长（{len(tb['content'])}字），上限 60-80 字")
```

工作量：15 行。

### Fix 11 (P2) — 颜色 semantic 强制（accent 仅用于 key takeaway）

`templates/themes/*.json` 加 `accent_rules`：

```json
{
  "primary": "#003D6E",
  "secondary": "#666666",
  "accent": "#FF6B35",
  "accent_usage": "key_takeaway_only"
}
```

`pipeline/agents/html_design_agent.py` 在 LLM prompt 注入约束："accent 色（橙 #FF6B35）仅用于 takeaway / 关键数字 / 重点 callout，不允许用于背景、装饰、次要文本"。

post-render check：解析 HTML 统计 accent 色像素占比，> 10% 拒收重试。

工作量：60 行 + 2 测试。

### Fix 12 (P2) — Chart Annotation Callouts

`pipeline/layer6_output/chart_renderer.py` 在 chart 注入时同时加 annotation shape：
- 找 series 里值最大/增长最快的 1-2 个数据点
- 在该点加文字 callout（"+47% 同比"）
- 用 accent 色

工作量：80 行 + 1 集成测试。

### Fix 13 (P3) — Footer 设计

`pipeline/agents/design_strategies/special_pages.py` 加全页 footer 渲染（非 cover/section_divider 都加）：

```
左下: 章节名 (e.g. "第二章 风险全景")  右下: P4 / 27
```

工作量：30 行。

---

## 第五部分：评测协议（如何用 MBB 决定下一次 release 是否合格）

每次主版本发布前，跑下面的 **MBB Rubric**，每项满分 10：

| 维度 | 评分标准 |
|---|---|
| **A. Action title** | 抽 5 张 slide，每张标题独立读是否能传达"读者应该相信什么"。5 张全过 = 10，1 张不过 = -2 |
| **B. Pyramid clarity** | 抽看 deck 目录 + 章节扉页，能否在 30 秒内说出 deck 的根论点 + 3 个支柱？能 = 10 |
| **C. White space** | 抽 5 张 content slide，每张目测文字像素覆盖 < 60%？全过 = 10 |
| **D. Data viz density** | content slide 中 chart + diagram 占比 ≥ 30%？计算实际占比，每差 5% 扣 1 分 |
| **E. Color semantic** | 整 deck accent 色（强调色）出现位置是否仅限 takeaway / 关键数字？随机使用 = 0，严格 semantic = 10 |
| **F. Source attribution** | 每张图表是否有 source 脚注？覆盖率即得分（70% = 7） |
| **G. Bullet 长度** | 抽 20 条 bullet，平均字数 < 60 = 10，每多 10 字 -2 |
| **H. Closing strength** | 最后一页是否是强 CTA？描述性 = 0，明确 action items = 5，含 metric/timeline = 10 |
| **I. Cover page** | 标题 + 副标题 + 日期 + 类型标签全有 = 10 |
| **J. Footer** | 章节 + 页码 + 字号合规 = 10 |

**通过线**：≥ 8 项各拿 ≥ 7 分，且 A/B 两项必须 ≥ 8。当前估算 PPTagent 输出在 5-6 分区间。

---

## References

- [Slideworks: 100+ Real McKinsey Presentations](https://slideworks.io/resources/47-real-mckinsey-presentations)
- [Slideworks: 750+ Real Consulting Presentations](https://slideworks.io/resources/750-real-consulting-presentations-from-mckinsey-deloitte-ey-and-more)
- [Slideworks: 55+ Real Bain Presentations](https://slideworks.io/resources/30-real-bain-presentations)
- [Slideworks: How McKinsey Consultants Make Presentations](https://slideworks.io/resources/how-mckinsey-consultants-make-presentations)
- [Slideworks: How to Write Action Titles Like McKinsey](https://slideworks.io/resources/how-to-write-action-titles-like-mckinsey)
- [Slideworks: Decoding McKinsey's New Visual Identity](https://slideworks.io/resources/decoding-mckinseys-visual-identity-and-powerpoint-template)
- [Analyst Academy: 600+ Real Consulting Presentations](https://www.theanalystacademy.com/consulting-presentations/)
- [Analyst Academy: 3 Great Examples of Slide Structure](https://www.theanalystacademy.com/consulting-slide-structure/)
- [Analyst Academy: How Effective Are These 6 PowerPoint Slides](https://www.theanalystacademy.com/effective-powerpoint-slides/)
- [Deckary: Pillar Consulting Presentations Guide](https://deckary.com/blog/pillar-consulting-presentations-guide)
- [Deckary: Consulting Slide Standards](https://deckary.com/blog/consulting-slide-standards)
- [Deckary: Pyramid Principle & SCQA Consultant's Guide](https://deckary.com/blog/pyramid-principle-consulting)
- [Deckary: How to Make Consulting Slides — MBB Guide](https://deckary.com/blog/consulting-quality-slides)
- [Deckary: SWOT Analysis Examples](https://deckary.com/blog/swot-analysis-examples)
- [SlideModel: McKinsey Presentation Structure Guide](https://slidemodel.com/mckinsey-presentation-structure/)
- [SlideModel: Deloitte Presentation Structure](https://slidemodel.com/deloitte-presentation-structure/)
- [Think-cell: Pyramid Principle for PowerPoint](https://www.think-cell.com/en/resources/content-hub/using-the-pyramid-principle-to-build-better-powerpoint-presentations)
- [Management Consulted: 2x2 Matrix Framework](https://managementconsulted.com/2x2-matrix/)
- [Bain ADAPT Design System Colors](https://designsystem.adapt.bain.com/designers/guides/colors/)
