# PPT Agent API 文档

## 基础信息

- Base URL: `http://localhost:8000`
- 交互式文档: http://localhost:8000/docs (Swagger UI)
- 所有响应均为 JSON（SSE端点除外）

---

## 端点详情

### POST /api/generate

纯文本方式启动PPT生成任务（异步）。

**请求体** (`application/json`):

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| title | string | 否 | "未命名演示文稿" | 演示文稿标题 |
| content | string | **是** | - | 原始文本内容 |
| target_audience | string | 否 | "管理层" | 目标受众 |
| language | string | 否 | "zh" | 语言（zh/en） |
**请求示例**:
```json
{
  "title": "数字化转型战略方案",
  "content": "2024年公司启动全面数字化转型计划...",
  "target_audience": "管理层",
  "language": "zh"
}
```

**响应** `200`:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "message": "任务已创建，正在后台处理",
  "status_url": "/api/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### POST /api/generate/file

通过上传文件启动PPT生成任务（异步）。

**请求** (`multipart/form-data`):

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | **是** | 上传文件（最大50MB） |
| title | string | 否 | 标题，默认取文件名 |
| target_audience | string | 否 | "管理层" |
| language | string | 否 | "zh" |

**支持格式**: `.docx`, `.xlsx`, `.csv`, `.pptx`, `.txt`, `.md`

**curl示例**:
```bash
curl -X POST http://localhost:8000/api/generate/file \
  -F "file=@quarterly_report.xlsx" \
  -F "title=季度分析报告" \
  -F "target_audience=高管层" \
  -F "language=zh"
```

**错误响应**:
- `400` — 不支持的文件格式
- `413` — 文件超过50MB

---

### GET /api/status/{task_id}

SSE（Server-Sent Events）实时推送任务进度。连接保持到任务完成或失败。

**响应** (`text/event-stream`):

每0.5秒推送一次状态更新：
```
data: {"task_id":"...","status":"processing","progress":50,"current_step":"结构规划","message":"生成了5页PPT","output_file":null,"error":null}

data: {"task_id":"...","status":"completed","progress":100,"current_step":"生成PPT","message":"PPT生成完成！","output_file":"output/xxx.pptx","error":null}
```

**前端示例**:
```javascript
const evtSource = new EventSource(`/api/status/${taskId}`);
evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgressBar(data.progress);
    if (data.status === 'completed' || data.status === 'failed') {
        evtSource.close();
    }
};
```

---

### GET /api/status/{task_id}/json

一次性返回任务状态（JSON），适合轮询模式。

**响应** `200`:
```json
{
  "task_id": "a1b2c3d4-...",
  "status": "completed",
  "progress": 100,
  "current_step": "生成PPT",
  "message": "PPT生成完成！",
  "output_file": "output/数字化转型战略方案.pptx",
  "error": null,
  "narrative": {
    "title": "数字化转型战略方案",
    "executive_summary": "...",
    "section_count": 4
  },
  "slides": {
    "slide_count": 5,
    "slide_types": ["title", "content", "data", "content", "summary"]
  }
}
```

**status 取值**: `pending` → `processing` → `completed` / `failed` / `paused`

**progress 阶段**:

| 进度 | 阶段 | 说明 |
|------|------|------|
| 5-10 | layer1 | 输入解析 |
| 10-30 | layer2_extract | 内容提取 |
| 35-50 | layer2_narrative | 叙事编排 |
| 55-70 | layer3 | 结构规划 |
| 73-78 | layer4 | 视觉设计 |
| 80-88 | layer5 | 图表生成 |
| 90-100 | layer6 | PPT构建 |

**错误响应**: `404` 任务不存在

---

### GET /api/download/{task_id}

下载生成的PPT文件。

**响应** `200`: 返回 `.pptx` 文件
- Content-Type: `application/vnd.openxmlformats-officedocument.presentationml.presentation`

**错误响应**:
- `400` — PPT尚未生成完成
- `404` — 任务不存在或文件已删除

---

### GET /api/history

获取已完成的生成历史。

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | int | 20 | 返回条数 |

**响应** `200`:
```json
{
  "total": 15,
  "items": [
    {
      "task_id": "a1b2c3d4-...",
      "title": "数字化转型战略方案",
      "status": "completed",
      "created_at": "2024-04-08T15:30:00",
      "output_file": "output/数字化转型战略方案.pptx"
    }
  ]
}
```

---

### DELETE /api/task/{task_id}

删除任务记录及其关联文件（生成的PPT + 上传的文件）。

**响应** `200`:
```json
{ "message": "任务已删除" }
```

**错误响应**: `404` 任务不存在

---

## Pipeline 阶段端点

### GET /api/task/{task_id}/stages

获取任务所有Pipeline阶段的状态和结果。

**响应** `200`:
```json
{
  "task_id": "a1b2c3d4-...",
  "task_status": "paused",
  "mode": "step",
  "stages": [
    {
      "stage": "layer1",
      "status": "completed",
      "started_at": "2024-04-09T10:00:00",
      "completed_at": "2024-04-09T10:00:01",
      "result": {
        "source_type": "text",
        "text_length": 5230,
        "detected_language": "zh",
        "table_count": 0,
        "image_count": 0
      },
      "error": null
    },
    {
      "stage": "layer2_extract",
      "status": "completed",
      "started_at": "2024-04-09T10:00:01",
      "completed_at": "2024-04-09T10:00:15",
      "result": {
        "count": 20,
        "elements": [
          {"index": 0, "type": "fact", "content": "...", "confidence": 0.95, "topics": []}
        ]
      },
      "error": null
    },
    {
      "stage": "layer2_narrative",
      "status": "running",
      "started_at": "2024-04-09T10:00:15",
      "completed_at": null,
      "result": null,
      "error": null
    }
  ]
}
```

**错误响应**: `404` 任务不存在

---

### GET /api/task/{task_id}/stage/{stage}

获取单个阶段详情。

**路径参数**:

| 参数 | 说明 |
|------|------|
| stage | 阶段名：`layer1`, `layer2_extract`, `layer2_narrative`, `layer3`, `layer4`, `layer5`, `layer6` |

**响应** `200`:
```json
{
  "stage": "layer2_narrative",
  "status": "completed",
  "started_at": "2024-04-09T10:00:15",
  "completed_at": "2024-04-09T10:00:30",
  "result": {
    "title": "数字化转型战略方案",
    "executive_summary": "...",
    "section_count": 4,
    "sections": [...]
  },
  "error": null
}
```

**错误响应**: `404` 阶段不存在

---

### PUT /api/task/{task_id}/stage/{stage}

修改阶段结果（用户编辑后保存）。保存后会自动重置该阶段之后的所有阶段状态。

**请求体**: 该阶段的完整result JSON（与GET获取的result结构一致）

**请求示例** — 编辑内容提取结果：
```json
{
  "count": 18,
  "elements": [
    {"index": 0, "type": "fact", "content": "修改后的内容", "confidence": 0.95, "topics": []}
  ],
  "_elements_full": [
    {"element_type": "fact", "content": "修改后的内容", "confidence": 0.95, "topics": []}
  ]
}
```

**响应** `200`:
```json
{ "message": "阶段 layer2_extract 已更新，后续阶段已重置" }
```

**注意**: 修改阶段结果后，需要调用 `/api/task/{id}/resume` 从下一阶段重跑Pipeline。

---

### POST /api/task/{task_id}/resume

从指定阶段恢复执行Pipeline。重置该阶段及后续阶段的状态后开始执行。

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| from_stage | string | 否 | 起始阶段名。不指定则从第一个未完成阶段开始 |

**curl示例**:
```bash
# 从Layer 3开始重跑
curl -X POST "http://localhost:8000/api/task/{task_id}/resume?from_stage=layer3"
```

**响应** `200`:
```json
{
  "task_id": "a1b2c3d4-...",
  "message": "从阶段 layer3 恢复执行",
  "status_url": "/api/status/a1b2c3d4-..."
}
```

**错误响应**:
- `400` — 任务状态不允许恢复（如正在处理中）
- `404` — 任务不存在

---

### POST /api/task/{task_id}/continue

用户在检查点确认后继续执行Pipeline。Pipeline在 4 个检查点（layer1, layer2_extract, layer2_narrative, layer3 完成后）自动暂停，用户审阅并确认后调用此端点继续。

**响应** `200`:
```json
{
  "task_id": "a1b2c3d4-...",
  "message": "继续执行下一阶段",
  "status_url": "/api/status/a1b2c3d4-..."
}
```

**错误响应**:
- `400` — 任务未暂停，无法继续
- `404` — 任务不存在

---

## 配置端点

### GET /api/config/models

获取各阶段的模型配置。

**响应** `200`:
```json
{
  "stages": {
    "layer2_extract": {
      "provider": "zhipu",
      "model": "glm-4-plus",
      "configured": true
    },
    "layer2_narrative": {
      "provider": "deepseek",
      "model": "deepseek-r1",
      "configured": true
    },
    "layer3": {
      "provider": "deepseek",
      "model": "deepseek-r1",
      "configured": true
    },
    "layer5_chart_narrative": {
      "provider": "tongyi",
      "model": "qwen-max",
      "configured": false
    }
  }
}
```

---

### PUT /api/config/models

更新模型配置。可更新全局默认或单个阶段的配置。API Key 会加密存储。

**请求体**:
```json
{
  "provider": "zhipu",
  "api_key": "your-api-key",
  "model": "glm-4-plus",
  "stage": "layer2_extract"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| provider | string | **是** | Provider: `zhipu`, `deepseek`, `tongyi` |
| api_key | string | **是** | API Key（会加密存储） |
| model | string | 否 | 模型名 |
| stage | string | 否 | 指定阶段，不指定则更新该 provider 的全局默认 |

**响应** `200`:
```json
{
  "message": "配置已更新",
  "provider": "zhipu",
  "stage": "layer2_extract"
}
```

---

### GET /api/health

健康检查。

**响应** `200`:
```json
{
  "status": "healthy",
  "llm_configured": true,
  "output_dir_exists": true,
  "active_tasks": 1,
  "total_tasks": 25
}
```

---

## 数据流

Pipeline 只有一种执行模式（手动确认模式），在 4 个检查点暂停：

```
POST /api/generate
    │
    ▼
Layer1 (输入解析) → 暂停
    │  [检查点1: 数据解析确认]
    ▼  POST /api/task/{id}/continue
Layer2提取 (GLM) → 暂停
    │  [检查点2: 内容提取确认]
    ▼  POST /api/task/{id}/continue
Layer2叙事 (DeepSeek-R1) → 暂停
    │  [检查点3: 叙事结构确认]
    ▼  POST /api/task/{id}/continue
Layer3 (DeepSeek-R1) → 暂停
    │  [检查点4: 页面结构确认]
    ▼  POST /api/task/{id}/continue
Layer4 + Layer5 (Qwen-Max) + Layer6 → 连续执行 → 完成
    │
    ▼
GET /api/download/{task_id}
```

在任意检查点，用户可以编辑阶段结果后再继续：
```
GET /api/task/{id}/stages                    # 查看阶段结果
PUT /api/task/{id}/stage/{stage}             # 编辑结果
POST /api/task/{id}/continue                 # 确认继续
POST /api/task/{id}/resume?from_stage=xxx    # 从指定阶段重跑
```

---

## 错误处理

所有错误响应格式：
```json
{ "detail": "错误描述" }
```

| HTTP状态码 | 场景 |
|------------|------|
| 400 | 请求参数错误、任务状态不允许操作 |
| 404 | 任务/阶段/文件不存在 |
| 413 | 上传文件超过50MB |
| 500 | LLM调用失败、Pipeline内部错误 |

---

## Pipeline阶段定义

| 阶段名 | 说明 | 进度范围 | 检查点 | 可编辑内容 |
|--------|------|----------|--------|------------|
| layer1 | 输入解析 | 5-10% | 检查点1 | Sheet选择、表头行、语言 |
| layer2_extract | 内容提取（GLM） | 10-30% | 检查点2 | 编辑/删除/添加内容元素 |
| layer2_narrative | 叙事编排（DeepSeek-R1） | 35-50% | 检查点3 | 编辑论点和过渡逻辑 |
| layer3 | 结构规划（DeepSeek-R1） | 55-70% | 检查点4 | 编辑每页takeaway |
| layer4 | 视觉设计（规则引擎） | 73-78% | 不暂停 | - |
| layer5 | 图表生成（Qwen-Max） | 80-88% | 不暂停 | - |
| layer6 | PPT构建（规则引擎） | 90-100% | 不暂停 | - |
