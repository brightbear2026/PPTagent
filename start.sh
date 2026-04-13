#!/bin/bash
# PPT Agent 一键启动脚本

echo "======================================"
echo "  PPT Agent - 专业PPT生成系统"
echo "======================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "⚠️  缺少依赖，正在安装..."
    pip3 install -q fastapi uvicorn python-multipart streamlit
}
python3 -c "import streamlit" 2>/dev/null || {
    pip3 install -q streamlit
}

echo "✅ 依赖检查完成"
echo ""

# 检查GLM API Key
if [ -z "$GLM_API_KEY" ]; then
    echo "⚠️  警告: GLM_API_KEY未设置"
    echo "   将使用硬编码演示模式"
    echo "   要使用真实LLM，请运行: export GLM_API_KEY='your-api-key'"
    echo ""
fi

# 启动后端
echo "🚀 启动后端 API (FastAPI)..."
python3 api/main.py &
BACKEND_PID=$!
sleep 2

echo "✅ 后端已启动: http://localhost:8000"
echo ""

# 启动前端
echo "🎨 启动前端界面 (Streamlit)..."
python3 -m streamlit run frontend/app.py --server.port 8501

# 清理
kill $BACKEND_PID 2>/dev/null
