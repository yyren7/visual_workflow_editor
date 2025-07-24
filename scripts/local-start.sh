#!/bin/bash

# 定义彩色输出函数
function print_green {
  echo -e "\033[32m$1\033[0m"
}

function print_yellow {
  echo -e "\033[33m$1\033[0m"
}

function print_red {
  echo -e "\033[31m$1\033[0m"
}

# 输出启动信息
print_green "=================================="
print_green "  启动可视化工作流编辑器项目"
print_green "=================================="

# 检查当前目录
SCRIPT_DIR=$(pwd)
print_yellow "当前工作目录: $SCRIPT_DIR"

# 定义后端启动命令
BACKEND_CMD="python run_backend.py"

# 启动后端
print_yellow "正在启动后端服务 (http://localhost:8000)..."
print_yellow "执行命令: $BACKEND_CMD"
$BACKEND_CMD &
BACKEND_PID=$!

# 检查后端启动状态
sleep 2
if ps -p $BACKEND_PID > /dev/null; then
  print_green "✓ 后端服务已启动 (PID: $BACKEND_PID)"
else
  print_red "✗ 后端服务启动失败!"
  exit 1
fi

# 启动前端
print_yellow "正在启动前端服务..."
print_yellow "执行命令: cd frontend && npm start"

# 进入前端目录并启动服务
pushd frontend > /dev/null
npm start &
FRONTEND_PID=$!
popd > /dev/null

# 等待用户输入
print_green "==============================================="
print_green "  前后端服务已启动"
print_green "  - 前端: http://localhost:3001"
print_green "  - 后端: http://localhost:8000"
print_green "==============================================="
print_yellow "按 Ctrl+C 停止所有服务"

# 等待中断信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" INT TERM
wait