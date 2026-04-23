# PPT Agent

输入文本或文档，自动生成咨询级 `.pptx` 演示文稿。系统对标四大咨询公司的信息密度和视觉规范，强调透明可控：每个关键决策节点暂停，用户审阅确认后再继续。

## 为什么选择 PPT Agent

市面上的 AI 幻灯片工具大多是"黑盒一键生成"——你不知道它丢了哪些信息，也没法控制它在想什么。PPT Agent 的设计哲学完全相反：**把控制权还给用户，让 AI 做苦力，让人来做判断**。

### 信息不丢失

大多数工具在把文章"喂给" LLM 时会大幅压缩，生成出来的 PPT 泛泛而谈，像是没读过原文。PPT Agent 为每页幻灯片单独注入最相关的原文段落（最多 2300 字），并在大纲阶段就告知 LLM 每个章节的实际内容摘要，而不是只给标题。长篇报告的核心数据、关键结论、具体数字，该出现的都会出现。

### 图表数据来自原文，不是编造的

这是行业通病：LLM 生成图表时往往会"发明"一些听起来合理的数字。PPT Agent 的图表数据**强制来源于上传文件中的真实表格**，数字直接从 Excel/CSV 行列中提取，LLM 只负责选择图表类型和写 so-what 结论，不碰任何数值。

### 原生矢量图表，不是截图

生成的图表是 python-pptx **原生图表对象**——打开 PowerPoint 可以直接点击修改数据、换颜色、调字体，和手工插入的图表没有任何区别。不是截图，不是图片，缩放不失真，可以二次编辑。

### 流水线透明，每步可审阅

6 个 Agent 串行执行，每个 Agent 的输出都持久化并暴露给用户：
- 看到 AI 理解了哪些章节结构
- 看到它规划的叙事框架是否符合你的汇报场景
- 在内容生成前审阅并修改每页大纲
- 在构建 PPT 前审阅并修改每页具体内容

任意一步不满意，可以回退到那一步重新生成，**不需要从头来**。

### 叙事结构而非堆砌信息

AI 生成内容的常见问题：把原文要点逐条列出，缺乏逻辑连贯性。PPT Agent 的 AnalyzeAgent 会根据汇报场景（季度汇报 / 战略提案 / 竞标 Pitch 等）选择合适的叙事框架（SCR / SCQA / AIDA 等），每页幻灯片都有明确的叙事角色（context / evidence / solution / closing），整个演示文稿有起承转合，不是 bullet 点的罗列。

### 可接入任意 LLM，不锁定单一厂商

只要支持 OpenAI 兼容协议，都可以直接配置使用——SiliconFlow、DeepSeek、阿里云百炼、智谱、Moonshot，或者自部署的 Ollama / vLLM。每个流水线阶段可以独立配置不同的模型，比如用便宜快速的模型做内容填充，用推理能力强的模型做大纲规划。

### 完全自托管，数据不出本地

所有处理在你自己的服务器上完成，文档内容不会上传到任何第三方平台（LLM API 调用除外，这是 LLM 工具的固有特性）。API Key 使用 Fernet + PBKDF2HMAC 加密存储，主密钥只存在于你的环境变量中。

---

## 效果预览

**输入** → 一篇业务报告、数据分析、会议纪要（TXT / DOCX / XLSX / Markdown）

**输出** → 结构完整的 `.pptx` 文件，包含：
- 叙事驱动的大纲（SCR / SCQA / STAR 等框架）
- 数据驱动的图表（柱状图、折线图、饼图等，数据来自原始表格）
- 专业布局（16种模板）和视觉主题（4套配色）
- 流程图、架构图、关系图等概念图示

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| 前端 | React 18 + TypeScript + Vite + Ant Design |
| 数据库 | PostgreSQL（Alembic 管理迁移） |
| LLM | 任意 OpenAI 兼容接口（SiliconFlow / DeepSeek / 通义 / 智谱等） |
| PPT 生成 | python-pptx（原生矢量图表对象） |
| 加密 | Fernet + PBKDF2HMAC |
| 部署 | Docker + docker-compose |

## 架构

### Agent 流水线

```
用户输入（文本/文件）
       │
       ▼
  ParseAgent          ── 解析文档结构，识别章节/表格/图片
       │
       ▼
  AnalyzeAgent        ── 分析受众与场景，生成叙事策略
       │
       ▼
  OutlineAgent        ── 生成 PPT 大纲（页数/类型/核心观点）
       │
  ◆ 检查点 1：用户审阅大纲，可编辑后确认
       │
       ▼
  ContentAgent        ── per-slide 并行生成每页内容 + 图表数据
       │
  ◆ 检查点 2：用户审阅内容，可编辑后确认
       │
       ▼
  DesignAgent         ── 规则引擎分配布局模板和视觉主题
       │
       ▼
  RenderAgent         ── python-pptx 渲染输出 .pptx
```

每个 Agent 独立运行，结果持久化到 PostgreSQL，支持从任意检查点回退重跑。

### 2 个必经检查点

| 检查点 | 审阅内容 | 可操作 |
|---|---|---|
| **大纲确认** | 全部页面的标题、类型、核心观点、视觉类型 | 编辑任意字段、调整页序、删除页面 |
| **内容确认** | 每页的文本块、图表数据、图示规格 | 编辑文本、修改图表数据、切换图示类型 |

确认后自动推进，无法跳过（这是产品设计，不是限制）。

### LLM 配置

系统使用 OpenAI 兼容协议，可对接任意支持该协议的模型服务：

- **国内推荐**：SiliconFlow（GLM / Kimi / Qwen 均可）、DeepSeek、阿里云百炼
- **海外**：OpenAI、Anthropic（通过兼容层）
- **自部署**：Ollama、vLLM

每个流水线阶段（analyze / outline / content / design）可独立配置不同模型，在系统设置界面配置，API Key 加密存储。

## 快速开始

### 前置要求

- Docker & docker-compose
- 至少一个 OpenAI 兼容的 LLM API Key

### 1. 克隆并配置

```bash
git clone https://github.com/brightbear2026/PPTagent.git
cd PPTagent

# 复制环境变量模板
cp .env.example .env
```

编辑 `.env`：

```env
# 生成加密主密钥（运行一次，保存好）
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MASTER_ENCRYPTION_KEY=your-generated-fernet-key

# PostgreSQL 密码（开发环境可保持默认）
POSTGRES_PASSWORD=pptagent_local
```

### 2. 启动服务

```bash
# 开发模式（支持热重载）
docker-compose -f docker-compose.dev.yml up --build

# 生产模式
docker-compose up -d --build
```

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

### 3. 配置 LLM

打开 http://localhost:3000 → 右上角 **系统设置** → 填入 API Key 和模型名称。

例如使用 SiliconFlow：
- Base URL: `https://api.siliconflow.cn/v1`
- Model: `Pro/moonshotai/Kimi-K2-Instruct` 或 `Pro/zai-org/GLM-5.1`
- API Key: 你的 SiliconFlow key

### 4. 开始生成

回到首页 → 填写标题和材料 → 点击「开始生成」。

## 项目结构

```
PPTagent/
├── api/
│   └── main.py                   # FastAPI 端点 + 任务调度
├── pipeline/
│   ├── agents/                   # 6个专用 Agent
│   │   ├── parse_agent.py
│   │   ├── analyze_agent.py
│   │   ├── outline_agent.py
│   │   ├── content_agent.py      # per-slide 并发生成
│   │   ├── design_agent.py
│   │   └── render_agent.py
│   ├── layer1_input/             # 多格式文档解析
│   ├── layer5_chart/             # 图表规格生成
│   ├── layer6_output/            # PPT 渲染引擎
│   │   ├── ppt_builder.py
│   │   ├── chart_renderer.py     # 分层图表渲染
│   │   └── diagram_renderer.py
│   ├── orchestrator.py           # Agent 编排 + 检查点管理
│   └── skills/                   # 渲染技能注册表
│       ├── charts/               # 8种图表技能
│       ├── diagrams/             # 4种图示技能
│       └── visual_blocks/        # 6种视觉块技能
├── models/
│   ├── slide_spec.py             # SlideSpec 核心数据模型
│   └── model_config.py           # 多阶段模型配置
├── llm_client/
│   ├── base.py                   # 抽象基类（tenacity 重试）
│   ├── openai_compat.py          # OpenAI 兼容适配器
│   ├── glm_client.py             # 智谱 GLM 专有 SDK 适配
│   └── provider_gate.py          # 并发控制（Semaphore + 限流）
├── storage/
│   ├── task_store.py             # PostgreSQL 存储层
│   └── encryption.py             # Fernet + PBKDF2 加密
├── migrations/                   # Alembic 数据库迁移
├── frontend-react/               # React 18 向导式前端
│   └── src/
│       ├── components/wizard/    # Step1-Step4 向导组件
│       ├── pages/WizardPage.tsx  # 主流程控制
│       └── hooks/useSSE.ts       # 实时进度订阅
├── templates/                    # 布局骨架 + 视觉主题
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

## 支持的输入格式

| 格式 | 扩展名 | 提取内容 |
|---|---|---|
| 纯文本 | `.txt` | 全文 + 章节结构自动识别 |
| Markdown | `.md` | 标题层级、列表、表格、代码块 |
| Word | `.docx` | 段落、表格、嵌入图片 |
| Excel | `.xlsx` | 多 Sheet 表格数据 |
| CSV | `.csv` | 单表数据（自动编码检测） |
| PowerPoint | `.pptx` | 逐页文本 + 表格 |

## API 概览

| 方法 | 端点 | 说明 |
|---|---|---|
| POST | `/api/generate` | 文本输入启动任务 |
| POST | `/api/generate/file` | 文件上传启动任务 |
| GET | `/api/status/{id}` | SSE 实时进度流 |
| GET | `/api/task/{id}/stage/{stage}` | 获取阶段结果（含编辑） |
| PUT | `/api/task/{id}/stage/{stage}` | 保存编辑后的阶段结果 |
| POST | `/api/task/{id}/confirm` | 确认检查点，推进流水线 |
| POST | `/api/task/{id}/resume` | 从指定阶段回退重跑 |
| GET | `/api/download/{id}` | 下载生成的 PPT |
| GET/PUT | `/api/settings` | 系统配置（模型/API Key） |

详细文档：http://localhost:8000/docs

## 开发

```bash
# 仅重建后端
docker-compose -f docker-compose.dev.yml up --build -d backend

# 查看后端日志
docker-compose logs -f backend

# 运行测试（在容器外，需本地 PostgreSQL）
python3 -m pytest tests/

# 数据库迁移
docker-compose exec backend alembic upgrade head
```

## License

MIT
