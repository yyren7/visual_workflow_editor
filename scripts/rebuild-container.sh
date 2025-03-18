#!/bin/bash

# 工作流编辑器容器重建脚本
# 将当前开发容器打包成新镜像，避免每次启动都重新安装依赖

set -e

echo "===== 工作流编辑器容器重建脚本 ====="
echo "此脚本将：创建新的开发容器镜像，避免每次启动都执行post-create.sh"

# 确保在项目根目录下
if [ ! -d ".devcontainer" ]; then
  echo "错误：请在项目根目录下运行此脚本"
  exit 1
fi

# 获取当前容器ID（如果在容器内运行）
CONTAINER_ID=""
if [ -f "/.dockerenv" ]; then
  CONTAINER_ID=$(hostname)
  echo "当前运行在容器 $CONTAINER_ID 中"
  
  # 确保cache目录存在
  sudo mkdir -p /workspace/.devcontainer/cache
  sudo chmod 777 /workspace/.devcontainer/cache
  
  # 保存当前的依赖状态，以便在新容器中使用
  if [ -f "/workspace/backend/requirements.txt" ]; then
    md5sum /workspace/backend/requirements.txt | awk '{print $1}' | sudo tee /workspace/.devcontainer/cache/last_requirements_md5 > /dev/null
    echo "已保存后端依赖状态"
  fi
  
  if [ -f "/workspace/frontend/package.json" ]; then
    md5sum /workspace/frontend/package.json | awk '{print $1}' | sudo tee /workspace/.devcontainer/cache/last_package_md5 > /dev/null
    echo "已保存前端依赖状态"
  fi
fi

# 设置镜像名称和标签
IMAGE_NAME="workflow-editor-dev"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"

echo "步骤1: 提交当前开发容器为新镜像 $FULL_IMAGE_NAME"
if [ -n "$CONTAINER_ID" ]; then
  # 在容器内，需要退出容器再执行
  echo "请在容器外运行此命令提交镜像："
  echo "  docker commit $CONTAINER_ID $FULL_IMAGE_NAME"
  echo "然后修改 .devcontainer/docker-compose.yml 文件，将以下内容："
  echo "  build:"
  echo "    context: .."
  echo "    dockerfile: .devcontainer/Dockerfile"
  echo "替换为："
  echo "  image: $FULL_IMAGE_NAME"
  echo "  # build:"
  echo "  #   context: .."
  echo "  #   dockerfile: .devcontainer/Dockerfile"
  echo
  echo "完成后，重启VS Code并选择'在容器中重新打开'"
  exit 0
else
  # 在容器外，直接执行提交
  RUNNING_CONTAINER=$(docker ps --filter "name=visual_workflow_editor" --format "{{.ID}}")
  if [ -z "$RUNNING_CONTAINER" ]; then
    echo "错误：找不到正在运行的工作流编辑器容器"
    exit 1
  fi
  
  echo "正在提交容器 $RUNNING_CONTAINER 为镜像 $FULL_IMAGE_NAME..."
  docker commit $RUNNING_CONTAINER $FULL_IMAGE_NAME
  echo "镜像创建成功！"
  
  # 确保cache目录存在
  mkdir -p .devcontainer/cache
  
  # 更新docker-compose.yml文件
  echo "步骤2: 更新docker-compose.yml文件..."
  COMPOSE_FILE=".devcontainer/docker-compose.yml"
  
  # 创建备份
  cp $COMPOSE_FILE "${COMPOSE_FILE}.bak"
  
  # 使用sed替换build部分为image
  sed -i.bak 's/  build:/  image: workflow-editor-dev:latest\n  # build:/g' $COMPOSE_FILE
  sed -i.bak 's/    context: ../    # context: ../g' $COMPOSE_FILE
  sed -i.bak 's/    dockerfile: .devcontainer\/Dockerfile/    # dockerfile: .devcontainer\/Dockerfile/g' $COMPOSE_FILE
  
  echo "docker-compose.yml文件已更新，原文件备份为 ${COMPOSE_FILE}.bak"
  echo
  echo "步骤3: 请重启VS Code并选择'在容器中重新打开'"
  echo "如果需要恢复原始配置，请运行："
  echo "  mv ${COMPOSE_FILE}.bak $COMPOSE_FILE"
fi 