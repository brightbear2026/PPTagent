# PPT Agent 项目状态报告

最后更新：2026-04-13

## 项目概览

**目标**：四大咨询公司级别的专业PPT自动生成系统

**技术栈**：Python 3.9+ | FastAPI | React 18 + TypeScript + Vite + Ant Design | python-pptx | 多模型(智谱+DeepSeek+通义) | SQLite | Docker

---

## 已实现功能

### 1. 6层Pipeline全部完成

| 层级 | 模块 | 状态 | 说明 |
|------|------|------|------|
| Layer 1 | 输入解析 | ✅ | 支持TXT/DOCX/XLSX/CSV/PPTX/MD，自动检测语言 |
| Layer 2 | 内容提取 | ✅ | LLM提取事实/数据/观点/结论，带置信度 |
| Layer 2 | 叙事编排 | ✅ | LLM编排论证结构（开篇->问题->分析->方案->总结） |
| Layer 3 | 结构规划 | ✅ | Narrative->SlideSpec列表，分配takeaway和角色 |
| Layer 4 | 视觉设计 | ✅ | 12种内容布局模板 + 5套视觉主题 |
| Layer 5 | 图表生成 | ✅ | LLM生成图表规格 + 拓扑图规格，真实表格数据驱动 |
| Layer 6 | PPT构建 | ✅ | 布局引擎坐标计算 + python-pptx渲染 |

### 2. 后端API服务 (`api/`)

- 文本/文件上传两种生成入口
- SSE实时进度推送
- 任务CRUD + 历史查询
- Pipeline阶段端点（查看/编辑/恢复/继续）
- JWT认证
- 图表数据校验：用enriched_tables真实数据替换LLM编造的数字

### 3. React前端 (`frontend-react/`)

- Vite + React 18 + TypeScript + Ant Design
- 向导式4步流程：上传 → 大纲 → 内容编辑 → 下载
- SSE实时进度
- 3栏内容编辑器 + 实时预览
- 历史记录、设置、登录/注册页面

### 4. 存储层 (`storage/`)

- SQLite持久化（tasks + pipeline_stages + settings + api_keys表）
- 阶段重置（用户编辑后重跑）
- API Key加密存储（Fernet + PBKDF2HMAC）

### 5. 多Provider LLM客户端 (`llm_client/`)

- 抽象基类 + 智谱专有SDK adapter + OpenAI兼容adapter
- Provider工厂模式
- 每阶段独立模型配置
- 指数退避重试（含429限流处理）

### 6. 数据流可靠性

- enriched_tables序列化：表格原始数据在阶段间不丢失
- content_filler表格注入：LLM生成图表时可见原始数字
- 逐页JSON解析降级：单页格式错误不影响其他页面
- prompt精简：从148行缩减到80行，降低LLM格式出错率

### 7. Docker部署

- `docker-compose.yml` — 生产部署
- `docker-compose.dev.yml` — 开发模式

---

## 相关文档

- `CLAUDE.md` — 项目架构设计和技术决策
- `DEVELOPMENT_GUIDE.md` — 开发规范
- `API_GUIDE.md` — API端点详细文档
- `README.md` — 项目概览
