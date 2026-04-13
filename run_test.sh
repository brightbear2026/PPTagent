#!/bin/bash
# PPT Agent 快速测试脚本

echo "🚀 PPT Agent 功能测试"
echo "======================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import pptx" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  缺少python-pptx，正在安装..."
    pip3 install -q python-pptx pydantic requests
fi

echo "✅ 依赖检查完成"
echo ""

# 运行测试
echo "🧪 运行测试套件..."
echo ""
python3 test_all_features.py

echo ""
echo "======================================"
echo "✨ 测试完成！"
echo ""
echo "📁 查看生成的PPT文件:"
echo "   open output/"
echo ""
