#!/bin/bash

# 开发环境启动脚本

mkdir -p /workspace/logs

case "$1" in
  frontend)
    cd /workspace/frontend
    echo "启动前端开发服务器..."
    
    # 创建前端运行时日志文件
    mkdir -p /workspace/logs
    touch /workspace/logs/frontend-runtime.log
    
    # 启动日志监听器（后台运行）
    (
      echo ""
      echo "=== 🌐 前端运行时日志 (浏览器Console) ==="
      echo "等待前端应用启动..."
      sleep 5  # 等待前端应用启动
      echo "开始监听浏览器日志..."
      
      # 使用tail -f监听日志文件，并添加前缀
      tail -f /workspace/logs/frontend-runtime.log 2>/dev/null | while read line; do
        echo "🌐 $line"
      done
    ) &
    LOG_PID=$!
    
    # 启动前端服务器（前台运行）
    echo ""
    echo "=== 📦 前端构建日志 (Webpack/Node.js) ==="
    npm start
    
    # 当前端退出时，停止日志监听
    kill $LOG_PID 2>/dev/null
    ;;
  backend)
    cd /workspace
    echo "启动后端开发服务器..."
    python3 backend/run_backend.py
    ;;
  logs)
    # 创建日志文件
    mkdir -p /workspace/logs
    touch /workspace/logs/frontend.log
    touch /workspace/logs/backend.log
    
    # 检查 tmux 是否已安装
    if ! command -v tmux &> /dev/null; then
      echo "tmux 未安装，正在安装..."
      sudo apt-get update && sudo apt-get install -y tmux
    fi
    
    # 结束已有的 tmux 会话
    tmux kill-session -t frontend 2>/dev/null || true
    tmux kill-session -t backend 2>/dev/null || true
    
    echo "在独立会话中启动前端和后端服务..."
    
    # 创建前端 tmux 会话
    cd /workspace/frontend
    tmux new-session -d -s frontend 'PORT=3001 npm start | tee /workspace/logs/frontend.log; read'
    echo "前端服务已在 tmux 会话 'frontend' 中启动（端口 3001）"
    
    # 创建后端 tmux 会话
    cd /workspace
    tmux new-session -d -s backend 'python3 backend/run_backend.py | tee /workspace/logs/backend.log; read'
    echo "后端服务已在 tmux 会话 'backend' 中启动"
    
    echo ""
    echo "使用以下命令连接到服务日志："
    echo "  tmux attach -t frontend  - 查看前端日志（按 Ctrl+B 然后 D 分离）"
    echo "  tmux attach -t backend   - 查看后端日志（按 Ctrl+B 然后 D 分离）"
    ;;
  stop)
    # 停止所有服务
    echo "停止前端和后端服务..."
    tmux kill-session -t frontend 2>/dev/null || true
    tmux kill-session -t backend 2>/dev/null || true
    echo "所有服务已停止"
    ;;
  *)
    echo "用法: ./start-dev.sh [frontend|backend|logs|stop]"
    echo "  frontend - 启动前端开发服务器"
    echo "  backend  - 启动后端开发服务器"
    echo "  logs     - 在独立窗口中显示前端和后端日志"
    echo "  stop     - 停止所有已启动的服务"
    ;;
esac
