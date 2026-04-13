# PPT Agent 项目状态报告

最后更新：2026-04-09

## 项目概览

**目标**：四大咨询公司级别的专业PPT自动生成系统

**技术栈**：Python 3.9+ | FastAPI | Streamlit(过渡) | python-pptx | 多模型(智谱+DeepSeek+通义) | SQLite | Docker

---

## 已实现功能

### 1. 6层Pipeline全部完成

| 层级 | 模块 | 状态 | 说明 |
|------|------|------|------|
| Layer 1 | 输入解析 | ✅ | 支持TXT/DOCX/XLSX/CSV/PPTX，自动检测语言 |
| Layer 2 | 内容提取 | ✅ | LLM提取事实/数据/观点/结论，带置信度 |
| Layer 2 | 叙事编排 | ✅ | LLM编排论证结构（开篇->问题->分析->方案->总结） |
| Layer 3 | 结构规划 | ✅ | Narrative->SlideSpec列表，分配takeaway和角色 |
| Layer 4 | 视觉设计 | ✅ | 12种内容布局模板 + 5套视觉主题 |
| Layer 5 | 图表生成 | ✅ | LLM生成图表规格 + 拓扑图规格 |
| Layer 6 | PPT构建 | ✅ | 布局引擎坐标计算 + python-pptx渲染 |

### 2. 后端API服务 (`api/`)

- 文本/文件上传两种生成入口
- SSE实时进度推送
- 任务CRUD + 历史查询
- Pipeline阶段端点（查看/编辑/恢复/继续）

### 3. 前端界面 (`frontend/app.py`)

- Pipeline阶段进度条可视化
- 每阶段可展开查看详细结果
- 关键阶段支持编辑
- PPT下载

### 4. 存储层 (`storage/`)

- SQLite持久化（tasks + pipeline_stages表）
- 阶段重置（用户编辑后重跑）
- 历史记录查询

### 5. LLM客户端 (`llm_client/`)

- 智谱AI GLM接口封装
- 指数退避重试（含429限流处理）

### 6. Docker部署

- `docker-compose.yml` — 生产部署
- `docker-compose.dev.yml` — 开发模式

---

## 架构重大调整（Phase 2）

基于需求评审，以下架构决策已确定，待实施：

### 调整 1：删除 auto/step 模式，改为 4 个强制检查点

**旧方案**：auto（全速跑完）/ step（每阶段都停）

**新方案**：唯一执行模式，在 4 个检查点强制暂停：
1. layer1 完成后 — 数据解析确认
2. layer2_extract 完成后 — 内容提取确认（分组呈现）
3. layer2_narrative 完成后 — 叙事结构确认
4. layer3 完成后 — 页面结构确认

layer4/5/6 连续执行不暂停。不提供跳过按钮。

### 调整 2：多 Provider LLM 架构

**旧方案**：单一智谱GLM

**新方案**：三家国内模型按能力分工

| 能力域 | Provider | 模型 | 阶段 |
|---|---|---|---|
| 中文理解/抽取 | 智谱 | GLM-4-Plus | layer2_extract |
| 叙事推理/结构 | DeepSeek | DeepSeek-R1 | layer2_narrative, layer3 |
| 数据分析/图表 | 阿里通义 | Qwen-Max | layer5 |

架构：`base.py`(抽象) + `zhipu.py`(专有SDK) + `openai_compat.py`(兼容协议覆盖DeepSeek/通义)

### 调整 3：API Key 加密存储

**旧方案**：环境变量 `GLM_API_KEY`

**新方案**：Fernet + PBKDF2HMAC 加密
- 系统主密钥 `MASTER_ENCRYPTION_KEY` 存环境变量
- 每个用户派生独立加密密钥（为多用户做准备）
- SQLite `api_keys` 表存加密后的 key

### 调整 4：新增 Markdown 输入格式

Layer 1 新增 `.md` 格式解析：标题层级、列表、表格、代码块。

### 调整 5：前端定位为过渡方案

Streamlit 不再深投入，将迁移到 React。当前只做功能正确的最小适配。

---

## 实施路线图

### Batch 1: LLM 多 Provider 基础（地基）

| # | 任务 | 文件 | 状态 |
|---|---|---|---|
| 1 | LLM 抽象基类 | `llm_client/base.py` | 待实施 |
| 2 | 智谱 adapter 重构 | `llm_client/zhipu.py` | 待实施 |
| 3 | OpenAI 兼容 adapter | `llm_client/openai_compat.py` | 待实施 |
| 4 | Provider 工厂 | `llm_client/factory.py` | 待实施 |
| 5 | 模型配置数据模型 | `models/model_config.py` | 待实施 |

### Batch 2: 加密 + 配置存储

| # | 任务 | 文件 | 状态 |
|---|---|---|---|
| 6 | 加密工具 | `storage/encryption.py` | 待实施 |
| 7 | 存储层扩展（settings/api_keys表） | `storage/task_store.py` | 待实施 |
| 8 | 模型配置 API 端点 | `api/main.py` | 待实施 |

### Batch 3: Pipeline 控制逻辑

| # | 任务 | 文件 | 状态 |
|---|---|---|---|
| 9 | 4 检查点逻辑 + 删除 auto/step | `api/pipeline_controller.py` | 待实施 |
| 10 | Markdown 格式解析 | `pipeline/layer1_input/` | 待实施 |
| 11 | Pipeline 各层接收 StageModelConfig | `pipeline/*/` | 待实施 |

### Batch 4: Streamlit 最小适配

| # | 任务 | 文件 | 状态 |
|---|---|---|---|
| 12 | 移除模式选择 | `frontend/app.py` | 待实施 |
| 13 | 多阶段模型配置 UI | `frontend/app.py` | 待实施 |
| 14 | 4 个检查点差异化展示 | `frontend/app.py` | 待实施 |
| 15 | layer2_extract 分组展示 | `frontend/app.py` | 待实施 |
| 16 | layer5 图表详情展示 | `frontend/app.py` | 待实施 |
| 17 | 文件上传支持 .md | `frontend/app.py` | 待实施 |

---

## 相关文档

- `CLAUDE.md` — 项目架构设计和技术决策（已更新）
- `DEVELOPMENT_GUIDE.md` — 开发规范（新增）
- `API_GUIDE.md` — API端点详细文档（已更新）
- `README.md` — 项目概览（已更新）
