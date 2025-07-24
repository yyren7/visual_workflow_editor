#!/bin/bash

# 彩色输出函数
function print_green {
  echo -e "\033[32m$1\033[0m"
}

function print_yellow {
  echo -e "\033[33m$1\033[0m"
}

function print_red {
  echo -e "\033[31m$1\033[0m"
}

# 检查是否安装了Docker
if ! command -v docker &> /dev/null; then
    print_red "错误: 未安装Docker。请先安装Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

print_green "=================================="
print_green "  启动可视化工作流编辑器开发环境"
print_green "=================================="

# 检查docker-compose.yml文件
if [ ! -f "docker-compose.yml" ]; then
    print_red "错误: 找不到docker-compose.yml文件"
    exit 1
fi

# 定义Docker Compose命令 (检测使用哪一种命令格式)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    print_red "错误: 未找到docker-compose或docker compose命令。请确保已正确安装Docker Compose。"
    exit 1
fi

# 启动开发环境
print_yellow "正在启动开发环境..."
$DOCKER_COMPOSE up -d

# 等待服务启动
print_yellow "等待服务启动..."
sleep 5

# 显示服务状态
$DOCKER_COMPOSE ps

print_green "==============================================="
print_green "  开发环境已启动"
print_green "访问以下地址:"
print_green "  - 前端: http://localhost:3001"
print_green "  - 后端 API: http://localhost:8000/docs"
print_green "==============================================="
print_yellow "要进入开发容器，请运行: docker exec -it workflow-editor-dev bash"
print_yellow "要查看日志，请运行: $DOCKER_COMPOSE logs -f"
print_yellow "要停止环境，请运行: $DOCKER_COMPOSE down" 