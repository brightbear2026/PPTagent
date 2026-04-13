# Development Guide

PPT Agent 开发规范。所有贡献者（包括 Claude Code）在开发时必须遵循本文档。

---

## 1. 代码规范

### 1.1 语言与格式

- Python 3.9+，类型注解必须使用
- 使用 `dataclass` 或 `pydantic.BaseModel` 定义数据结构，禁止裸 dict 传递业务数据
- 缩进 4 空格，行宽 120 字符
- 文件头部 docstring 说明模块用途，一句话即可
- 函数/方法只在逻辑不自明时加注释，禁止注释废话（如 `# 返回结果` `return result`）

### 1.2 命名规范

| 类型 | 规范 | 示例 |
|---|---|---|
| 文件名 | snake_case | `glm_client.py`, `task_store.py` |
| 类名 | PascalCase | `SlideSpec`, `LLMClient`, `TaskStore` |
| 函数/方法 | snake_case | `extract_elements()`, `build_narrative()` |
| 常量 | UPPER_SNAKE | `PAUSE_AFTER_STAGES`, `MAX_TOKENS` |
| 私有方法 | 前缀下划线 | `_calculate_density()` |
| Provider adapter 文件 | `{provider}.py` 或 `openai_compat.py` | `zhipu.py`, `openai_compat.py` |

### 1.3 导入顺序

```python
# 1. 标准库
import os
import json
from typing import Optional, List, Dict

# 2. 第三方库
from pydantic import BaseModel
from fastapi import FastAPI

# 3. 项目内部模块
from models.slide_spec import SlideSpec
from llm_client.factory import get_client
```

---

## 2. 架构约束

### 2.1 层间通信

- Pipeline 各层之间**只通过 `SlideSpec` 对象传递数据**
- 每层只填充自己管辖的字段，禁止覆盖其他层的字段
- 层间不允许直接函数调用，必须通过 `PipelineController` 调度

### 2.2 LLM 调用

- **禁止在 pipeline 层代码中直接实例化 provider SDK**（如 `zhipuai.ZhipuAI()`）
- 所有 LLM 调用必须通过 `llm_client.factory.get_client()` 获取客户端
- 每个 LLM 调用必须传入 `StageModelConfig`，由 `PipelineController` 注入
- Prompt 模板放在调用层内部（如 `pipeline/layer2_content/prompts.py`），不做全局 prompt 管理

```python
# 正确
def extract_elements(raw_content, model_config: StageModelConfig):
    client = get_client(model_config.provider, model_config.api_key,
                        base_url=model_config.base_url)
    return client.generate(prompt, model=model_config.model)

# 错误
def extract_elements(raw_content):
    from zhipuai import ZhipuAI
    client = ZhipuAI(api_key=os.environ["GLM_API_KEY"])
```

### 2.3 新增 LLM Provider

添加新 provider 时遵循以下步骤：

**如果新 provider 支持 OpenAI 兼容协议**（大多数国内模型都支持）：
1. 在 `llm_client/factory.py` 的 `PROVIDER_ENDPOINTS` 中添加 `base_url` 映射
2. 在 `CLAUDE.md` 的 Provider 表格中更新文档
3. 无需新建文件，`openai_compat.py` 自动覆盖

**如果新 provider 使用专有 SDK**（如智谱）：
1. 在 `llm_client/` 下新建 `{provider}.py`
2. 继承 `LLMClient` 基类，实现 `generate()` 方法
3. 在 `llm_client/factory.py` 的 `PROVIDER_MAP` 中注册
4. 在 `requirements.txt` 中添加 SDK 依赖
5. 在 `CLAUDE.md` 的 Provider 表格中更新文档

```python
# llm_client/new_provider.py (仅专有 SDK 需要)
from llm_client.base import LLMClient, LLMResponse

class NewProviderClient(LLMClient):
    def __init__(self, api_key: str, base_url: str = None):
        ...

    def generate(self, prompt: str, model: str, max_tokens: int = 4096,
                 temperature: float = 0.7) -> LLMResponse:
        ...
```

```python
# 对于 OpenAI 兼容 provider，只需在 factory.py 加一行：
PROVIDER_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/v1",
    "tongyi": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "moonshot": "https://api.moonshot.cn/v1",   # 新增示例
}
```

### 2.4 存储层

- 所有数据库操作封装在 `storage/task_store.py` 的 `TaskStore` 类中
- 禁止在 API 路由或 Pipeline 代码中直接执行 SQL
- 新增表时，在 `TaskStore.__init__` 中添加 `CREATE TABLE IF NOT EXISTS`
- API Key 的读写必须通过 `storage/encryption.py` 加解密，禁止明文存储

### 2.5 API 端点

- 所有端点定义在 `api/main.py`
- 业务逻辑不写在路由函数中，调用 `PipelineController` 或 `TaskStore` 的方法
- 请求/响应使用 Pydantic Model 定义，不用裸 dict
- 错误响应统一使用 `HTTPException`，格式 `{"detail": "错误描述"}`

### 2.6 前端（Streamlit）

- 当前前端是过渡方案，**不深投入**
- 只做功能正确，不追求视觉精美
- 所有业务逻辑通过调用后端 API 实现，前端不直接操作数据库或 Pipeline
- 新功能先确保后端 API 完整，再在前端适配
- 禁止在前端引入大型 JS 组件或 npm 依赖

---

## 3. Pipeline 开发规范

### 3.1 新增/修改 Pipeline 阶段

每个阶段是一个独立模块，结构如下：

```
pipeline/layer{N}_{name}/
  __init__.py          # 导出主函数
  processor.py         # 核心处理逻辑
  prompts.py           # LLM prompt 模板（如果需要 LLM）
```

主函数签名必须遵循：

```python
def process(input_data: dict, model_config: Optional[StageModelConfig] = None) -> dict:
    """
    Args:
        input_data: 上一阶段的输出（或初始输入）
        model_config: LLM 配置（规则引擎层传 None）
    Returns:
        该阶段的结果 dict（会被 JSON 序列化存入 pipeline_stages.result）
    Raises:
        ValueError: 输入数据不合法
        LLMError: LLM 调用失败
    """
```

### 3.2 确认点规则

```python
PAUSE_AFTER_STAGES = {"layer1", "layer2_extract", "layer2_narrative", "layer3"}
```

- 在这 4 个阶段完成后，`PipelineController` 将任务状态设为 `paused`
- 用户通过 `POST /api/task/{id}/continue` 确认后继续
- `layer4` -> `layer5` -> `layer6` 连续执行不暂停
- **禁止添加 auto 模式或跳过按钮**

### 3.3 阶段结果格式

每个阶段的 result 必须是可 JSON 序列化的 dict。关键字段：

| 阶段 | result 必含字段 |
|---|---|
| layer1 | `source_type`, `detected_language`, `text_length`, `raw_text_preview`, `tables[]`, `table_count` |
| layer2_extract | `count`, `elements[]`（每个含 `type`, `content`, `confidence`, `topics`） |
| layer2_narrative | `title`, `executive_summary`, `sections[]`（每个含 `role`, `core_argument`, `transition_to_next`, `supporting_elements[]`） |
| layer3 | `slides[]`（每个含 `slide_type`, `takeaway_message`, `narrative_arc`, `index`） |
| layer4 | `theme`, `slide_count`, `assignments[]` |
| layer5 | `charts[]`（每个含 `chart_type`, `so_what`, `data_source`, `key_insights[]`） |
| layer6 | `file_name`, `file_path`, `slide_count` |

---

## 4. 数据库规范

### 4.1 表结构

| 表名 | 用途 | 关键列 |
|---|---|---|
| `tasks` | 任务元数据 | `task_id`, `title`, `status`, `current_stage`, `created_at`, `output_file` |
| `pipeline_stages` | 阶段结果 | `task_id`, `stage`, `status`, `result`(JSON), `started_at`, `completed_at`, `error` |
| `settings` | 全局配置 | `user_id`, `key`, `value` |
| `api_keys` | 加密的 API Key | `user_id`, `provider`, `encrypted_key`, `created_at` |

### 4.2 约定

- `task_id` 使用 UUID4
- `user_id` 单用户阶段固定为 `"default"`，多用户阶段迁移时只需改此值
- `status` 枚举值：`pending`, `processing`, `completed`, `paused`, `failed`
- `pipeline_stages.result` 存 JSON 字符串，读取时 `json.loads()`
- 时间戳使用 ISO 8601 格式字符串

---

## 5. 加密规范

### 5.1 API Key 存储

```python
# 加密
from storage.encryption import encrypt_api_key, decrypt_api_key

encrypted = encrypt_api_key(api_key="sk-xxx", user_id="default")
# -> 存入 api_keys.encrypted_key

# 解密
api_key = decrypt_api_key(encrypted_key=encrypted, user_id="default")
```

### 5.2 Master Key 管理

- `MASTER_ENCRYPTION_KEY` 只存在于环境变量，**禁止写入代码或配置文件**
- 生成方式：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Docker 部署通过 `docker-compose.yml` 的 `environment` 或 `.env` 文件注入
- `.env` 文件必须在 `.gitignore` 中

---

## 6. 错误处理规范

### 6.1 层间错误

- 每层入口校验输入数据，不合法时抛 `ValueError` 并附清晰消息
- LLM 调用失败时抛 `LLMError`（自定义异常），包含 provider、model、HTTP status
- `PipelineController` 捕获异常，记录到 `pipeline_stages.error`，设任务状态为 `failed`

### 6.2 LLM 重试策略

- 指数退避：初始 1s，最大 30s，最多 3 次
- 429 限流：尊重 `Retry-After` header，退避后重试
- 超时：单次调用 60s，总超时 180s
- 重试逻辑在 `LLMClient` 基类中实现，子类不重复实现

### 6.3 API 错误响应

```python
# 统一格式
raise HTTPException(status_code=400, detail="具体错误描述")

# 禁止
return {"error": "something went wrong"}  # 不要用 200 + error 字段
```

---

## 7. 测试规范

### 7.1 测试文件命名

```
test_{module_name}.py    # 对应模块的测试
test_end_to_end.py       # 端到端集成测试
```

### 7.2 测试分层

| 层级 | 范围 | 运行频率 |
|---|---|---|
| 单元测试 | 单个函数/类（mock LLM） | 每次提交 |
| 集成测试 | Pipeline 全流程（需真实 LLM） | 每次发布前 |
| 视觉测试 | 生成 PPT 并截图对比 | 手动触发 |

### 7.3 LLM Mock

测试时使用 `MockLLMClient` 替代真实调用：

```python
from llm_client.base import LLMClient, LLMResponse

class MockLLMClient(LLMClient):
    def __init__(self, fixed_response: str):
        self.fixed_response = fixed_response

    def generate(self, prompt, model, **kwargs) -> LLMResponse:
        return LLMResponse(content=self.fixed_response, usage={"input": 0, "output": 0})
```

---

## 8. Git 规范

### 8.1 分支

| 分支 | 用途 |
|---|---|
| `main` | 稳定版本 |
| `dev` | 开发中 |
| `feature/{name}` | 功能开发 |
| `fix/{name}` | Bug 修复 |

### 8.2 Commit Message

格式：`{type}: {简要描述}`

| type | 说明 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改变行为） |
| `docs` | 文档更新 |
| `test` | 测试 |
| `chore` | 构建/依赖/配置 |

示例：
```
feat: add Anthropic LLM client adapter
fix: layer2_extract checkpoint not pausing correctly
refactor: extract LLMClient base class from glm_client
docs: update CLAUDE.md with multi-provider architecture
```

### 8.3 .gitignore 必须包含

```
.env
*.pyc
__pycache__/
output/*.pptx
storage/*.db
.superpowers/
```

---

## 9. 依赖管理

### 9.1 添加依赖

1. 在 `requirements.txt` 中添加，附注释说明用途
2. 指定精确版本号（`==`），不用 `>=`
3. 按功能分组，用注释分隔

```
# Core
python-pptx==1.0.2
pydantic==2.12.5

# LLM Providers
zhipuai==2.1.5.20250825     # 智谱 GLM（专有SDK）
openai==1.82.0              # OpenAI兼容协议（覆盖 DeepSeek、通义等）

# Encryption
cryptography==44.0.3

# Input Parsing
python-docx>=1.1.0
openpyxl>=3.1.0
mistune==3.1.3          # Markdown parsing

# FastAPI
fastapi==0.115.6
uvicorn[standard]==0.32.1
```

### 9.2 禁止引入的依赖

- `matplotlib` — 图表用 python-pptx 原生 chart 对象
- `diagrams` — 拓扑图用 shape + connector 直接绘制
- 任何 Node.js / npm 包 — 前端阶段不引入 JS 生态

---

## 10. 实施路线图

### Batch 1: LLM Multi-Provider (foundation)

1. `llm_client/base.py` — Abstract base class + LLMResponse
2. `llm_client/zhipu.py` — Refactor from existing glm_client.py
3. `llm_client/openai_compat.py` — OpenAI-compatible adapter (covers DeepSeek, Tongyi, etc.)
4. `llm_client/factory.py` — Provider factory with endpoint mapping
5. `models/model_config.py` — StageModelConfig + PipelineModelConfig

### Batch 2: Encryption + Config Storage

7. `storage/encryption.py` — Fernet + PBKDF2 wrapper
8. `storage/task_store.py` — Add `settings` and `api_keys` tables
9. `api/main.py` — Config endpoints: `GET/PUT /api/config/models`

### Batch 3: Pipeline Control

10. `api/pipeline_controller.py` — 4 checkpoint logic, remove auto/step modes
11. `pipeline/layer1_input/` — Add `.md` format parsing
12. Refactor all pipeline LLM calls to accept `StageModelConfig`

### Batch 4: Streamlit Minimal Adaptation

13. Remove mode selection UI
14. Model config UI: per-stage dropdown
15. Differentiated display for 4 checkpoints
16. layer2_extract: grouped element display (not raw JSON)
17. layer5: chart detail display (not raw JSON)
18. File upload: add `.md` to accepted types
