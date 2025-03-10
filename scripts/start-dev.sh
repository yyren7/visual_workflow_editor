#!/bin/bash

# 简化版启动脚本用于开发环境

mkdir -p /workspace/logs

case "$1" in
  frontend)
    cd /workspace/frontend
    echo "启动前端开发服务器..."
    npm start
    ;;
  backend)
    cd /workspace
    echo "启动后端开发服务器..."
    python3 backend/run_backend.py
    ;;
  logs)
    # 创建日志文件
    touch /workspace/logs/frontend.log
    touch /workspace/logs/backend.log
    
    # 在后台启动服务
    echo "在后台启动前端和后端服务..."
    cd /workspace/frontend
    npm start > /workspace/logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    cd /workspace
    python3 backend/run_backend.py > /workspace/logs/backend.log 2>&1 &
    BACKEND_PID=$!
    
    # 使用 tail 同时显示两个日志
    echo "显示实时日志（按 Ctrl+C 停止查看）..."
    echo "前端日志 (左) | 后端日志 (右)"
    echo "----------------------------------------"
    tail -f /workspace/logs/frontend.log /workspace/logs/backend.log
    
    # 当 tail 被中断时，杀死进程
    kill $FRONTEND_PID $BACKEND_PID
    ;;
  *)
    echo "用法: ./start-dev.sh [frontend|backend|logs]"
    echo "  frontend - 启动前端开发服务器"
    echo "  backend  - 启动后端开发服务器"
    echo "  logs     - 在后台启动两个服务器并显示实时日志"
    ;;
esac 