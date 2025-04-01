#!/bin/bash

# 在容器启动后执行的脚本
echo "正在设置开发环境..."

# 检查当前用户和权限
echo "当前用户: $(whoami)"
echo "用户权限: $(id)"

# 检查 Python 环境
echo "检查 Python 环境..."
python3 --version
pip3 --version

# 跳过创建目录和更改权限的步骤，因为Windows挂载卷不支持这些操作
echo "注意: 跳过目录创建和权限设置，这些在Windows挂载卷上不起作用"

# 确保 scripts 目录存在
mkdir -p /workspace/scripts

# 直接创建主工作区中的启动脚本（避免使用符号链接）
echo "配置启动脚本..."
cat > /workspace/start-dev.sh << 'EOF'
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
    tmux new-session -d -s frontend 'npm start | tee /workspace/logs/frontend.log; read'
    echo "前端服务已在 tmux 会话 'frontend' 中启动"
    
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
EOF

# 确保脚本有执行权限
chmod +x /workspace/start-dev.sh || { echo "修改启动脚本权限失败"; }
# 切换到 vscode 用户执行后续操作
if [ "$(whoami)" != "vscode" ]; then
  echo "切换到 vscode 用户执行安装..."
  # 使用 sudo -u vscode 执行后续命令
  sudo -u vscode bash -c '
    # 安装后端依赖
    echo "安装后端 Python 依赖..."
    cd /workspace
    pip3 install --no-cache-dir -r backend/requirements.txt

    # 确保pytest在路径中
    echo "确认后端依赖已安装..."
    pip3 list | grep pytest

    # 安装前端依赖
    echo "安装前端 Node.js 依赖..."
    cd /workspace/frontend
    npm ci --no-optional
  '
else
  # 如果已经是 vscode 用户，直接执行
  # 安装后端依赖
  echo "安装后端 Python 依赖..."
  cd /workspace
  pip3 install --no-cache-dir -r backend/requirements.txt

  # 确保pytest在路径中
  echo "确认后端依赖已安装..."
  pip3 list | grep pytest

  # 安装前端依赖
  echo "安装前端 Node.js 依赖..."
  cd /workspace/frontend
  npm ci --no-optional
fi

# 跳过最后的权限设置
echo "注意: 跳过node_modules权限设置，这在Windows挂载卷上不起作用"

echo "开发环境设置完成！"
echo ""
echo "可以使用以下命令启动开发环境："
echo "  ./start-dev.sh frontend - 启动前端开发服务器"
echo "  ./start-dev.sh backend  - 启动后端开发服务器"
echo "  ./start-dev.sh logs     - 在两个独立窗口中启动前后端服务器并显示实时日志"
echo "  ./start-dev.sh stop     - 停止所有已启动的服务" 