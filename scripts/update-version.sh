#!/bin/bash

# 版本更新脚本
# 用法: ./update-version.sh [major|minor|patch] [commit_message]
# 例如: ./update-version.sh minor "添加新功能"

set -e

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

# 确定项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_JSON="$PROJECT_ROOT/workspace/database/version.json"

# 检查version.json文件是否存在
if [ ! -f "$VERSION_JSON" ]; then
    print_red "错误: $VERSION_JSON 文件不存在！"
    exit 1
fi

# 读取当前版本
CURRENT_VERSION=$(cat "$VERSION_JSON" | grep -o '"version": *"[^"]*"' | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
if [ -z "$CURRENT_VERSION" ]; then
    print_red "错误: 无法从version.json读取版本号"
    exit 1
fi

print_yellow "当前版本: $CURRENT_VERSION"

# 拆分版本号
IFS='.' read -r -a VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# 处理参数
VERSION_TYPE=${1:-"patch"}
COMMIT_MSG=${2:-"版本更新"}

# 计算新版本号
case "$VERSION_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        print_red "错误: 无效的版本类型 '$VERSION_TYPE'。请使用 major, minor 或 patch。"
        exit 1
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
print_yellow "新版本: $NEW_VERSION"

# 更新版本文件
TODAY=$(date +%Y-%m-%d)
TMP_FILE=$(mktemp)
cat "$VERSION_JSON" | sed "s/\"version\": *\"[^\"]*\"/\"version\": \"$NEW_VERSION\"/" | sed "s/\"lastUpdated\": *\"[^\"]*\"/\"lastUpdated\": \"$TODAY\"/" > $TMP_FILE
mv $TMP_FILE "$VERSION_JSON"

print_green "version.json已更新"

# 询问是否提交更改
read -p "是否要提交并推送更改？ (y/n): " SHOULD_COMMIT
if [[ $SHOULD_COMMIT == "y" || $SHOULD_COMMIT == "Y" ]]; then
    # 添加到Git
    git add "$VERSION_JSON"
    git commit -m "$COMMIT_MSG: v$NEW_VERSION"
    
    # 创建版本标签
    git tag -a "v$NEW_VERSION" -m "版本 $NEW_VERSION: $COMMIT_MSG"
    
    # 询问是否要推送
    read -p "是否要推送更改到远程仓库？ (y/n): " PUSH_CHANGES
    if [ "$PUSH_CHANGES" = "y" ]; then
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        git push origin $CURRENT_BRANCH
        git push origin "v$NEW_VERSION"
        print_green "更改已推送到远程仓库"
    else
        print_yellow "更改已在本地提交但未推送"
    fi
else
    print_yellow "version.json已更新但未提交到Git"
fi

print_green "版本更新完成!" 