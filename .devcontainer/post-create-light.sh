#!/bin/bash

# 轻量版容器启动后执行的脚本
echo "正在设置开发环境（轻量版）..."

# 检查当前用户和权限
echo "当前用户: $(whoami)"

# 创建持久化目录来存储MD5校验值
CACHE_DIR="/workspace/.devcontainer/cache"
sudo mkdir -p "$CACHE_DIR"
sudo chmod 777 "$CACHE_DIR"

# 更新项目特定的依赖（只更新可能有变化的部分）
echo "更新项目依赖..."

# 更新后端依赖（只在requirements.txt变化时执行）
if [ -f "/workspace/backend/requirements.txt" ]; then
  REQUIREMENTS_MD5=$(md5sum /workspace/backend/requirements.txt | awk '{print $1}')
  LAST_REQUIREMENTS_MD5="$CACHE_DIR/last_requirements_md5"
  
  if [ ! -f "$LAST_REQUIREMENTS_MD5" ] || [ "$(cat $LAST_REQUIREMENTS_MD5)" != "$REQUIREMENTS_MD5" ]; then
    echo "后端依赖可能已更新，正在安装..."
    cd /workspace
    pip3 install --no-cache-dir -r backend/requirements.txt
    echo "$REQUIREMENTS_MD5" | sudo tee "$LAST_REQUIREMENTS_MD5" > /dev/null
  else
    echo "后端依赖未变化，跳过安装"
  fi
fi

# 更新前端依赖（只在package.json变化时执行）
if [ -f "/workspace/frontend/package.json" ]; then
  PACKAGE_MD5=$(md5sum /workspace/frontend/package.json | awk '{print $1}')
  LAST_PACKAGE_MD5="$CACHE_DIR/last_package_md5"
  
  if [ ! -f "$LAST_PACKAGE_MD5" ] || [ "$(cat $LAST_PACKAGE_MD5)" != "$PACKAGE_MD5" ]; then
    echo "前端依赖可能已更新，正在安装..."
    cd /workspace/frontend
    npm ci --no-optional
    echo "$PACKAGE_MD5" | sudo tee "$LAST_PACKAGE_MD5" > /dev/null
  else
    echo "前端依赖未变化，跳过安装"
  fi
fi

echo "设置完成！可以使用以下命令启动开发环境："
echo "  ./start-dev.sh frontend - 启动前端开发服务器"
echo "  ./start-dev.sh backend  - 启动后端开发服务器"
echo "  ./start-dev.sh logs     - 在独立窗口中启动前后端服务并显示实时日志"
echo "  ./start-dev.sh stop     - 停止所有已启动的服务"

# 手动更新MD5文件
echo "更新依赖状态文件..."
sudo mkdir -p /workspace/.devcontainer/cache
md5sum /workspace/backend/requirements.txt | awk '{print $1}' | sudo tee /workspace/.devcontainer/cache/last_requirements_md5 > /dev/null
md5sum /workspace/frontend/package.json | awk '{print $1}' | sudo tee /workspace/.devcontainer/cache/last_package_md5 > /dev/null
echo "依赖状态更新完成" 

# 设置SQLite数据库文件权限
echo "正在设置数据库文件权限..."
# 设置现有数据库文件权限
if [ -f "/workspace/flow_editor.db" ]; then
  echo "设置数据库文件 /workspace/flow_editor.db 权限为666 (可读写)"
  chmod 666 /workspace/flow_editor.db
fi

# 设置数据库目录权限
echo "设置数据库目录权限..."
if [ -d "/workspace/database" ]; then
  chmod -R 777 /workspace/database
fi

# 确保数据库所在目录有写入权限
chmod 777 /workspace

# 添加一个小函数到.bashrc，方便随时修复权限
cat << 'EOF' | sudo tee /usr/local/bin/fix-db-permissions > /dev/null
#!/bin/bash
echo "正在修复数据库权限..."
if [ -f "/workspace/flow_editor.db" ]; then
  chmod 666 /workspace/flow_editor.db
  echo "已设置 /workspace/flow_editor.db 权限为666 (可读写)"
fi
if [ -d "/workspace/database" ]; then
  chmod -R 777 /workspace/database
  echo "已设置 /workspace/database 目录权限为777 (完全访问)"
fi
echo "数据库权限修复完成！"
EOF

sudo chmod +x /usr/local/bin/fix-db-permissions
echo "alias fixdb='fix-db-permissions'" >> ~/.bashrc

echo "数据库权限设置完成！您可以随时使用 'fixdb' 命令修复权限" 