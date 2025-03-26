#!/bin/bash

# 开发环境启动脚本

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
    # 再次确保数据库权限正确
    if [ -f "/workspace/flow_editor.db" ]; then
      chmod 666 /workspace/flow_editor.db
    fi
    # 从.bashrc加载环境变量后再启动后端，设置PRINT_DEBUG_INFO=1只在主进程打印调试信息
    bash -c "source ~/.bashrc && cd /workspace/backend && PRINT_DEBUG_INFO=1 PYTHONPATH=/workspace python3 run_backend.py"
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
    tmux new-session -d -s frontend 'npm start | tee /workspace/logs/frontend.log; read'
    echo "前端服务已在 tmux 会话 'frontend' 中启动"
    
    # 创建后端 tmux 会话
    cd /workspace
    # 再次确保数据库权限正确
    if [ -f "/workspace/flow_editor.db" ]; then
      chmod 666 /workspace/flow_editor.db
    fi
    tmux new-session -d -s backend 'bash -c "source ~/.bashrc && cd /workspace/backend && PRINT_DEBUG_INFO=1 PYTHONPATH=/workspace python3 run_backend.py" | tee /workspace/logs/backend.log; read'
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
