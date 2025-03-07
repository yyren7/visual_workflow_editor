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

# 检查是否安装了Docker和Docker Compose
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

# 启动开发环境
print_yellow "正在启动开发环境..."
docker-compose up -d

# 等待服务启动
print_yellow "等待服务启动..."
sleep 5

# 显示服务状态
docker-compose ps

print_green "==============================================="
print_green "  开发环境已启动"
print_green "  - 前端: http://localhost:3000"
print_green "  - 后端: http://localhost:8000"
print_green "==============================================="
print_yellow "要进入开发容器，请运行: docker exec -it workflow-editor-dev bash"
print_yellow "要查看日志，请运行: docker-compose logs -f"
print_yellow "要停止环境，请运行: docker-compose down" 