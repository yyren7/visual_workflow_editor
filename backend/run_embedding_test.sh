#!/bin/bash

# 确保在backend目录下
cd "$(dirname "$0")"

# 检查Python命令
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "错误: 找不到Python命令"
    exit 1
fi

echo "使用Python命令: $PYTHON_CMD"

# 检查依赖
$PYTHON_CMD -c "import sys; sys.exit(0 if all(map(lambda m: m in sys.modules or __import__(m, fromlist=['']) or True, ['matplotlib', 'sklearn'])) else 1)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装所需依赖..."
    pip3 install matplotlib scikit-learn || pip install matplotlib scikit-learn
fi

# 安装langchain相关依赖
echo "确保安装了最新的langchain依赖..."
pip3 install -U langchain langchain-community langchain-huggingface langchain_google_genai || pip install -U langchain langchain-community langchain-huggingface langchain_google_genai

# 运行基本测试
echo -e "\n运行基本嵌入模型测试..."
$PYTHON_CMD test_embedding.py

# 运行性能基准测试
echo -e "\n\n运行嵌入模型性能和准确性基准测试..."
$PYTHON_CMD test_embedding_benchmark.py

echo -e "\n测试完成！" 