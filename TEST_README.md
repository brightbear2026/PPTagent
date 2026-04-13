# PPT Agent 快速测试指南

## 🎯 当前实现的功能

### ✅ 已完成模块

1. **核心数据模型** (`models/`)
   - SlideSpec：贯穿整个流水线的核心对象
   - Narrative：叙事结构
   - 完整的枚举类型和辅助类

2. **Layer 6: PPT生成** (`pipeline/layer6_output/`)
   - LayoutEngine：计算元素精确坐标
   - PPTBuilder：生成.pptx文件
   - 支持标题页、内容页、数据页布局

3. **Layer 3: 结构规划** (`pipeline/layer3_structure/`)
   - StructurePlanner：Narrative → SlideSpec列表
   - 每页有明确的takeaway和narrative角色

4. **LLM客户端** (`llm_client/`)
   - GLMClient：智谱AI GLM-5 Plus封装
   - 重试、超时、成本控制

## 🧪 运行测试

### 一键测试所有功能

```bash
python3 test_all_features.py
```

这会运行4个测试：
- ✅ 数据模型导入与创建
- ✅ 结构规划层（Narrative → Slides）
- ✅ PPT生成（硬编码内容）
- ✅ 完整流水线（Narrative → Slides → PPT）

### 查看生成的PPT

测试成功后会在 `output/` 目录生成3个PPT文件：

```bash
ls -lh output/
```

**文件列表：**
1. `四大级别PPT演示.pptx` - 基础演示
2. `AI业务创新方案.pptx` - 业务场景演示
3. `完整流程测试.pptx` - 完整流水线测试

打开这些文件可以看到：
- ✅ 标题页居中布局
- ✅ 内容页带takeaway标题
- ✅ 底部来源标注
- ✅ 多层级文本块

### 测试单个模块

```bash
# 测试数据模型
python3 test_models.py

# 测试Layer 6（PPT生成）
python3 pipeline/layer6_output/ppt_builder.py

# 测试Layer 3（结构规划）
python3 pipeline/layer3_structure/structure_planner.py
```

## 📊 当前架构

```
用户输入（未来）
    ↓
Layer 2: 内容分析 (待实现)
    ↓
Narrative（已完成）
    ↓
Layer 3: 结构规划 ✅
    ↓
List[SlideSpec]（已完成）
    ↓
Layer 6: PPT生成 ✅
    ↓
.pptx文件 ✅
```

## 🎨 视觉效果预览

已生成的PPT具有以下特点：

### 标题页
- 大号标题（44pt，加粗）
- 深蓝色主题色（#003D6E）
- 居中对齐

### 内容页
- 清晰的takeaway标题（28pt，加粗）
- 正文内容（18pt/14pt）
- 底部来源标注（9pt，灰色）

### 布局特点
- 16:9 宽屏比例
- 统一间距（0.5英寸边距）
- 专业配色方案

## 🚀 下一步计划

1. **Layer 2: 内容分析层**
   - 实现ContentExtractor（信息提取）
   - 实现NarrativeArchitect（论证结构编排）
   - 集成GLM-5 Plus API

2. **Layer 4 & 5: 视觉设计 + 图表生成**
   - 模板库设计
   - 图表生成（python-pptx原生chart）

3. **API + 前端**
   - FastAPI后端
   - Streamlit前端

## 📝 注意事项

- 当前所有内容都是硬编码的演示数据
- LLM调用需要设置 `GLM_API_KEY` 环境变量
- 生成的PPT文件在 `output/` 目录

## 🔧 故障排除

**问题：ModuleNotFoundError**
```bash
# 确保在项目根目录运行
cd /Users/xiongzhou/project/PPTagent
python3 test_all_features.py
```

**问题：python-pptx未安装**
```bash
pip3 install -q python-pptx pydantic requests
```

**问题：想查看具体代码**
```bash
# 核心数据模型
cat models/slide_spec.py

# PPT生成器
cat pipeline/layer6_output/ppt_builder.py

# 结构规划器
cat pipeline/layer3_structure/structure_planner.py
```
