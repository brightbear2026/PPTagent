# PPT Agent

专业PPT自动生成系统，对标四大咨询公司（麦肯锡、BCG、贝恩、德勤）的演示文稿质量。输入文本或文档，自动生成包含叙事结构、数据图表和专业视觉设计的 .pptx 文件。

## 特性

- **多格式输入** — 支持 TXT、DOCX、XLSX/CSV、PPTX、Markdown
- **6层智能流水线** — 内容提取 → 叙事编排 → 结构规划 → 视觉设计 → 图表生成 → PPT构建
- **4个确认检查点** — 数据解析、内容提取、叙事结构、页面结构，每步人工确认
- **多模型协作** — 智谱GLM（提取）+ DeepSeek-R1（推理）+ 通义Qwen-Max（图表）
- **真实数据驱动** — 图表数据来自原始表格，LLM不编造数字
- **原生图表** — python-pptx 原生图表对象，矢量可编辑
- **加密存储** — API Key 使用 Fernet + PBKDF2 加密，支持多用户隔离
- **16:9专业版式** — 12种内容布局模板，5套视觉主题
- **Docker部署** — 一键启动前后端服务

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| 前端 | React 18 + TypeScript + Vite + Ant Design |
| LLM | 智谱GLM-4 + DeepSeek-R1 + 阿里通义Qwen-Max |
| PPT生成 | python-pptx（原生图表对象） |
| 存储 | SQLite + 文件系统 |
| 加密 | Fernet + PBKDF2HMAC |
| 部署 | Docker + docker-compose |

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- 至少一个 LLM API Key（智谱AI / DeepSeek / 阿里通义）

### 本地运行

```bash
# 1. 安装后端依赖
pip3 install -r requirements.txt

# 2. 生成加密主密钥
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. 设置环境变量
export MASTER_ENCRYPTION_KEY='your-generated-key'

# 4. 启动后端
cd api && python3 -m uvicorn main:app --reload --port 8000
# -> http://localhost:8000

# 5. 启动前端（新终端）
cd frontend-react && npm install && npm run dev
# -> http://localhost:3000
```

### Docker 部署

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

访问地址：
- 前端：http://localhost:3000
- 后端API：http://localhost:8000
- API文档：http://localhost:8000/docs

## 系统架构

```
用户输入（文本/文件）
    |
    v
+-------------------------------------------------+
|             6-Layer Pipeline                     |
|                                                  |
|  Layer 1  输入解析   DOCX/XLSX/CSV/PPTX/TXT/MD  |
|     v                                            |
|  [Checkpoint 1: 数据解析确认]                     |
|     v                                            |
|  Layer 2  内容提取   GLM提取事实/数据/观点/结论    |
|     v                                            |
|  [Checkpoint 2: 内容提取确认]                     |
|     v                                            |
|  Layer 2  叙事编排   DeepSeek-R1编排论证结构        |
|     v                                            |
|  [Checkpoint 3: 叙事结构确认]                     |
|     v                                            |
|  Layer 3  结构规划   DeepSeek-R1生成页面骨架+Takeaway |
|     v                                            |
|  [Checkpoint 4: 页面结构确认]                     |
|     v                                            |
|  Layer 4  视觉设计   规则引擎匹配布局+主题         |
|     v                                            |
|  Layer 5  图表生成   Qwen-Max生成图表规格+So-What   |
|     v                                            |
|  Layer 6  PPT构建    坐标计算+python-pptx渲染      |
|                                                  |
+-------------------------------------------------+
    |
    v
  output/*.pptx
```

### 多模型协作（全部国内模型）

| 能力域 | Provider | 模型 | 阶段 |
|---|---|---|---|
| 中文理解/信息抽取 | 智谱 | GLM-4-Plus | 内容提取 |
| 叙事推理/结构规划 | DeepSeek | DeepSeek-R1 | 叙事编排、结构规划 |
| 数据分析/图表叙事 | 阿里通义 | Qwen-Max | 图表生成 |

每个阶段可独立配置模型，支持全局默认 + 阶段级覆盖。DeepSeek 和通义均使用 OpenAI 兼容协议，一个 adapter 覆盖。

### 4个确认检查点

所有生成任务在 4 个关键节点暂停，用户审阅确认后才继续：

| 检查点 | 用户审阅内容 | 可编辑 |
|---|---|---|
| 数据解析确认 | 源类型、语言、表格预览 | Sheet选择、表头行、语言 |
| 内容提取确认 | 按类型分组的结构化元素 | 删除/修改/添加元素 |
| 叙事结构确认 | 核心论点、各段角色、过渡逻辑 | 修改论点、调整顺序 |
| 页面结构确认 | 每页Takeaway和类型 | 修改Takeaway、合并/拆分页面 |

## 项目结构

```
PPTagent/
  api/                         # FastAPI 后端
    main.py                    # API 端点 + 流水线调度
    pipeline_controller.py     # Pipeline 阶段控制器（4个检查点）
    auth.py                    # JWT 认证
  pipeline/                    # 核心 6 层流水线
    layer1_input/              # 输入解析
    layer2_content/            # 内容提取 + 叙事编排
    layer3_structure/          # 结构规划
    layer4_visual/             # 视觉设计
    layer5_chart/              # 图表生成
    layer6_output/             # 布局引擎 + PPT构建
  models/                      # 数据模型
    slide_spec.py              # SlideSpec 核心模型
    model_config.py            # 多模型配置
  llm_client/                  # 多 Provider LLM 客户端
    base.py                    # 抽象基类
    zhipu.py                   # 智谱 GLM（专有SDK）
    openai_compat.py           # OpenAI 兼容适配器（DeepSeek、通义等）
    factory.py                 # Provider 工厂
  storage/                     # 持久化层
    task_store.py              # SQLite 存储
    encryption.py              # API Key 加密
  templates/                   # 布局骨架 + 视觉主题
  frontend-react/              # React 前端
    src/
      components/wizard/       # 向导式步骤组件
      pages/                   # 页面路由
      api/                     # 后端 API 客户端
      hooks/                   # SSE 等自定义 hooks
  output/                      # 生成的 PPT 文件
```

## API 概览

### 基础端点

| 方法 | 端点 | 说明 |
|---|---|---|
| POST | `/api/generate` | 纯文本生成PPT |
| POST | `/api/generate/file` | 上传文件生成PPT |
| GET | `/api/status/{id}` | SSE实时进度 |
| GET | `/api/status/{id}/json` | JSON一次性状态 |
| GET | `/api/download/{id}` | 下载PPT文件 |
| GET | `/api/history` | 生成历史记录 |
| DELETE | `/api/task/{id}` | 删除任务 |

### Pipeline 阶段端点

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/api/task/{id}/stages` | 获取所有阶段状态 |
| PUT | `/api/task/{id}/stage/{stage}` | 修改阶段结果 |
| POST | `/api/task/{id}/continue` | 确认检查点后继续 |
| POST | `/api/task/{id}/resume` | 从指定阶段重跑 |

### 模型配置端点

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/api/config/models` | 获取各阶段模型配置 |
| PUT | `/api/config/models` | 更新模型配置 |

详细API文档见 [API_GUIDE.md](API_GUIDE.md)

## 支持的输入格式

| 格式 | 扩展名 | 提取内容 |
|---|---|---|
| 纯文本 | `.txt` | 全文文本 + 语言检测 |
| Markdown | `.md` | 标题层级 + 列表 + 表格 + 代码块 |
| Word | `.docx` | 段落文本 + 表格 + 图片 |
| Excel | `.xlsx` | 多Sheet表格数据 |
| CSV | `.csv` | 单表数据（自动编码检测） |
| PowerPoint | `.pptx` | 逐页文本 + 表格 |

## 相关文档

- [CLAUDE.md](CLAUDE.md) — 项目架构设计和技术决策
- [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) — 开发规范
- [API_GUIDE.md](API_GUIDE.md) — API 端点详细文档

## License

MIT
