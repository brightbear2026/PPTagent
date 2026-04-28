<div align="center">

# PPT Agent

**AI-Powered Consulting-Grade Presentation Generator**

输入文本或文档，自动生成咨询级 `.pptx` 演示文稿

[English](#english) | [中文](#中文)

---

</div>

<a id="中文"></a>

## 中文

### PPT Agent 是什么？

PPT Agent 是一个自托管的 AI 演示文稿生成系统。输入一份业务文档或粘贴文本，系统通过 6 个 AI Agent 串行处理，生成信息密度对标咨询公司的专业 PPT。

与直接让 LLM "写一份 PPT" 不同，PPT Agent 的核心理念是**透明可控**：

- **论证型大纲** — 基于金字塔原理（Pyramid Principle），根据汇报场景自动选择叙事框架（SCQA/SCR/AIDA 等），每页有明确论点和叙事角色
- **2 个强制检查点** — 大纲和内容生成后必须经过用户审阅确认，可编辑任意字段后继续
- **图表数据来自原文** — 优先从上传文件的真实表格提取，不会编造数字
- **原生矢量图表** — 生成 PowerPoint 原生图表对象，可二次编辑，不是截图

### 效果预览

| Step 1：上传材料 | Step 2：审阅大纲 |
|:---:|:---:|
| <img src="docs/screenshots/step1_upload.png" width="400"> | <img src="docs/screenshots/step2_outline.png" width="400"> |

| Step 3：审阅内容 | Step 4：下载 PPT |
|:---:|:---:|
| <img src="docs/screenshots/step3_content.png" width="400"> | <img src="docs/screenshots/step4_download.png" width="400"> |

**生成效果** — 原生矢量图表、专业配色、结构完整：

<p align="center">
  <img src="docs/screenshots/ppt_result.png" width="800" alt="生成效果">
</p>

### 核心特性

- **信息不丢失** — 为每页幻灯片单独注入最相关的原文段落，核心数据和关键结论完整保留
- **图表数据来自原文** — 优先从真实表格提取，纯文本文档则从文本中提炼可量化论据
- **原生矢量图表** — PowerPoint 原生图表对象，可直接编辑数据、换色、调字体
- **论证型大纲** — 叙事框架驱动（SCQA/SCR/AIDA 等），不是章节堆砌
- **流水线透明** — 6 个 Agent 串行执行，每步输出可审阅、可编辑、可回退
- **任意 LLM** — 支持 DeepSeek、SiliconFlow、阿里云百炼、智谱、Moonshot 等所有 OpenAI 兼容接口，每个阶段可独立配置模型
- **用户认证与配额** — JWT 认证，可配置每用户并发任务上限
- **API Key 加密存储** — Fernet + PBKDF2HMAC 加密，不自托管 LLM 时密钥安全有保障
- **完全自托管** — Docker 一键部署，所有数据留在本地

### 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| 前端 | React 18 + TypeScript + Vite + Ant Design |
| 数据库 | PostgreSQL（Alembic 管理迁移） |
| LLM | 任意 OpenAI 兼容接口 |
| PPT 渲染 | Node.js + Playwright + pptxgenjs（HTML → PPTX） |
| 图表注入 | python-pptx 原生矢量图表 |
| 视觉技能 | 可扩展 Skill Registry（图表/图示/视觉块） |
| 加密 | Fernet + PBKDF2HMAC |
| 部署 | Docker + docker-compose |

### 架构

```
用户输入（文本/文件）
       │
       ▼
  ParseAgent          ── 解析文档结构，识别章节/表格/图片
       │
       ▼
  AnalyzeAgent        ── 分析受众与场景，生成叙事策略 + chunk 索引
       │
       ▼
  PlanAgent           ── 金字塔原则大纲（SCQA/SCR/AIDA + 页面论点序列）
       │
  ◆ 检查点 1：用户审阅大纲，可编辑后确认
       │
       ▼
  ContentAgent        ── per-slide 并行生成每页内容 + 图表/图示规格
       │
  ◆ 检查点 2：用户审阅内容，可单页重跑 + 反馈
       │
       ▼
  HTMLDesignAgent     ── LLM 选择模板槽位 + CSS 校验，生成结构化 HTML
       │
       ▼
  html2pptx.js        ── Playwright 渲染 HTML → pptxgenjs 输出 .pptx
  chart_renderer.py   ── 注入原生 python-pptx 矢量图表
```

### 快速开始

#### 前置要求

- Docker & docker-compose
- 至少一个 OpenAI 兼容的 LLM API Key（DeepSeek / SiliconFlow / 阿里云百炼 / 智谱等）

#### 1. 克隆并配置

```bash
git clone https://github.com/brightbear2026/PPTagent.git
cd PPTagent

cp .env.example .env
```

编辑 `.env`：

```env
# 加密主密钥（生成方式如下）
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MASTER_ENCRYPTION_KEY=<粘贴生成结果>

# JWT 认证密钥（推荐 32+ 字符随机字符串）
JWT_SECRET=<随机字符串>

# 数据库密码
POSTGRES_PASSWORD=mypassword123
```

#### 2. 启动服务

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

#### 3. 配置 LLM

打开 http://localhost:3000 → 注册账号 → 右上角 **系统设置** → 填入 API Key 和模型名称。

例如使用 DeepSeek：
- Base URL: `https://api.deepseek.com/v1`
- Model: `deepseek-chat`
- API Key: 你的 key

#### 4. 开始生成

回到首页 → 填写标题和材料 → 点击「开始生成」。

### 场景 → 叙事框架映射

| 场景 | 框架 | 结构 |
|---|---|---|
| 季度汇报 | SCR | situation → complication → resolution |
| 战略提案 | SCQA | situation → complication → question → answer |
| 竞标 Pitch | AIDA | attention → interest → desire → action |
| 内部分析 | Issue Tree | MECE 分解 |
| 培训材料 | Explanation | objective → gap → solution → evaluation |
| 项目汇报 | STAR | situation → task → action → result |
| 产品发布 | Problem-Solution | 问题树 + 方案树 |

### 支持的输入格式

| 格式 | 扩展名 | 提取内容 |
|---|---|---|
| 纯文本 | `.txt` | 全文 + 章节结构自动识别 |
| Markdown | `.md` | 标题层级、列表、表格、代码块 |
| Word | `.docx` | 段落、表格、嵌入图片 |
| Excel | `.xlsx` | 多 Sheet 表格数据 |
| CSV | `.csv` | 单表数据 |
| PowerPoint | `.pptx` | 逐页文本 + 表格 |

### 项目结构

```
PPTagent/
├── api/                            # FastAPI 端点 + 认证 + 任务调度
├── pipeline/
│   ├── agents/                     # 6 个 AI Agent
│   │   ├── parse_agent.py          # 多格式文档解析
│   │   ├── analyze_agent.py        # 文档策略分析 + chunk 生成
│   │   ├── plan_agent.py           # 金字塔原则大纲
│   │   ├── content_agent.py        # per-slide 并发内容生成
│   │   ├── html_design_agent.py    # HTML 幻灯片设计（模板槽位系统）
│   │   └── base.py                 # Agent 基类
│   ├── prompts/                    # 版本化 prompt 文件
│   ├── skills/                     # 可扩展视觉技能注册表
│   ├── layer6_output/              # 渲染层
│   │   ├── html2pptx.js            # Playwright → pptxgenjs
│   │   ├── chart_renderer.py       # 原生矢量图表注入
│   │   └── css_linter.py           # CSS 白名单校验
│   └── orchestrator.py             # Agent 编排 + 检查点管理
├── models/                         # SlideSpec 核心数据模型
├── llm_client/                     # 多 Provider LLM 客户端
├── storage/                        # PostgreSQL 存储层 + 加密
├── frontend-react/                 # React 18 向导式前端
├── migrations/                     # Alembic 数据库迁移
└── docker-compose.yml
```

### 开发

```bash
# 仅重建后端
docker-compose -f docker-compose.dev.yml up --build -d backend

# 仅重建前端
docker-compose -f docker-compose.dev.yml up --build -d frontend

# 查看后端日志
docker-compose logs -f backend

# 数据库迁移
docker-compose exec backend alembic upgrade head
```

---

<a id="english"></a>

## English

### What is PPT Agent?

PPT Agent is a self-hosted AI presentation generator. Feed it a business document or paste text, and it produces consulting-grade `.pptx` files through a 6-agent pipeline.

Unlike simply asking an LLM to "write a PPT," PPT Agent is built on **transparency and control**:

- **Argument-driven outlines** — Based on the Pyramid Principle, auto-selects narrative frameworks (SCQA/SCR/AIDA) per presentation scenario, with clear claims and narrative roles per slide
- **2 mandatory checkpoints** — Users must review and approve the outline and content before proceeding; every field is editable
- **Charts from real data** — Prioritizes actual tables from uploaded files; never fabricates numbers
- **Native vector charts** — Generates PowerPoint native chart objects (editable, not screenshots)

### Core Features

- **No information loss** — Each slide gets the most relevant source paragraphs injected; key data and conclusions are preserved
- **Charts from source data** — Extracts from real tables in Excel/CSV, or quantifies evidence from plain text
- **Native vector charts** — PowerPoint native chart objects: editable data, colors, and fonts
- **Argument-driven outlines** — Narrative framework-driven (SCQA/SCR/AIDA), not chapter stacking
- **Transparent pipeline** — 6 agents run sequentially; every stage output is reviewable, editable, and reversible
- **Any LLM provider** — DeepSeek, SiliconFlow, Alibaba Cloud, Zhipu, Moonshot, or self-hosted Ollama/vLLM. Per-stage model configuration supported
- **Authentication & quotas** — JWT auth with configurable per-user concurrency limits
- **Encrypted API keys** — Fernet + PBKDF2HMAC encryption at rest
- **Fully self-hosted** — Docker one-command deployment, all data stays local

### Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | React 18 + TypeScript + Vite + Ant Design |
| Database | PostgreSQL (Alembic migrations) |
| LLM | Any OpenAI-compatible API |
| PPT Rendering | Node.js + Playwright + pptxgenjs (HTML → PPTX) |
| Chart Injection | python-pptx native vector charts |
| Visual Skills | Extensible Skill Registry (charts/diagrams/visual blocks) |
| Encryption | Fernet + PBKDF2HMAC |
| Deployment | Docker + docker-compose |

### Architecture

```
User Input (text/file)
       │
       ▼
  ParseAgent          ── Parse document structure, identify sections/tables/images
       │
       ▼
  AnalyzeAgent        ── Analyze audience & scenario, generate narrative strategy + chunks
       │
       ▼
  PlanAgent           ── Pyramid Principle outline (SCQA/SCR/AIDA + slide claim sequence)
       │
  ◆ Checkpoint 1: User reviews outline, can edit any field then confirm
       │
       ▼
  ContentAgent        ── Per-slide parallel content generation + chart/diagram specs
       │
  ◆ Checkpoint 2: User reviews content, can rerun single slide with feedback
       │
       ▼
  HTMLDesignAgent     ── LLM picks template slots + CSS validation, generates structured HTML
       │
       ▼
  html2pptx.js        ── Playwright renders HTML → pptxgenjs outputs .pptx
  chart_renderer.py   ── Injects native python-pptx vector charts
```

### Quick Start

#### Prerequisites

- Docker & docker-compose
- At least one OpenAI-compatible LLM API key (DeepSeek / SiliconFlow / Alibaba Cloud / Zhipu, etc.)

#### 1. Clone & Configure

```bash
git clone https://github.com/brightbear2026/PPTagent.git
cd PPTagent

cp .env.example .env
```

Edit `.env`:

```env
# Encryption master key (generate with:)
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MASTER_ENCRYPTION_KEY=<paste generated key>

# JWT authentication secret (recommended: 32+ char random string)
JWT_SECRET=<random-string>

# Database password
POSTGRES_PASSWORD=mypassword123
```

#### 2. Start Services

```bash
# Development mode (hot reload)
docker-compose -f docker-compose.dev.yml up --build

# Production mode
docker-compose up -d --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

#### 3. Configure LLM

Open http://localhost:3000 → Register → **Settings** (top right) → Enter API Key and model name.

Example with DeepSeek:
- Base URL: `https://api.deepseek.com/v1`
- Model: `deepseek-chat`
- API Key: your key

#### 4. Generate

Go to the home page → Enter title and content → Click "Start Generation".

### Scenario → Framework Mapping

| Scenario | Framework | Structure |
|---|---|---|
| Quarterly Review | SCR | situation → complication → resolution |
| Strategy Proposal | SCQA | situation → complication → question → answer |
| Sales Pitch | AIDA | attention → interest → desire → action |
| Internal Analysis | Issue Tree | MECE decomposition |
| Training Material | Explanation | objective → gap → solution → evaluation |
| Project Report | STAR | situation → task → action → result |
| Product Launch | Problem-Solution | Problem tree + Solution tree |

### Supported Input Formats

| Format | Extension | Extracted Content |
|---|---|---|
| Plain Text | `.txt` | Full text + auto section detection |
| Markdown | `.md` | Heading hierarchy, lists, tables, code blocks |
| Word | `.docx` | Paragraphs, tables, embedded images |
| Excel | `.xlsx` | Multi-sheet table data |
| CSV | `.csv` | Single table data |
| PowerPoint | `.pptx` | Per-slide text + tables |

### Project Structure

```
PPTagent/
├── api/                            # FastAPI endpoints + auth + task dispatch
├── pipeline/
│   ├── agents/                     # 6 AI Agents
│   │   ├── parse_agent.py          # Multi-format document parser
│   │   ├── analyze_agent.py        # Strategy analysis + chunk generation
│   │   ├── plan_agent.py           # Pyramid Principle outline
│   │   ├── content_agent.py        # Per-slide parallel content generation
│   │   ├── html_design_agent.py    # HTML slide design (template slot system)
│   │   └── base.py                 # Agent base classes
│   ├── prompts/                    # Versioned prompt files
│   ├── skills/                     # Extensible visual skill registry
│   ├── layer6_output/              # Rendering layer
│   │   ├── html2pptx.js            # Playwright → pptxgenjs
│   │   ├── chart_renderer.py       # Native vector chart injection
│   │   └── css_linter.py           # CSS whitelist validation
│   └── orchestrator.py             # Agent orchestration + checkpoint management
├── models/                         # SlideSpec core data models
├── llm_client/                     # Multi-provider LLM client
├── storage/                        # PostgreSQL storage + encryption
├── frontend-react/                 # React 18 wizard UI
├── migrations/                     # Alembic database migrations
└── docker-compose.yml
```

### Development

```bash
# Rebuild backend only
docker-compose -f docker-compose.dev.yml up --build -d backend

# Rebuild frontend only
docker-compose -f docker-compose.dev.yml up --build -d frontend

# View backend logs
docker-compose logs -f backend

# Database migration
docker-compose exec backend alembic upgrade head
```

## License

MIT
