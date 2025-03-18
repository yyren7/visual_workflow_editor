# 可视化工作流编辑器

[English](README.md) | [中文](README_zh.md) | [日本語](README_ja.md)

这是一个基于 Docker 容器化的可视化工作流编辑器项目，支持跨平台开发和 CI/CD 部署。

## 项目说明

本项目包含：

- 基于 FastAPI 的后端服务
- 基于 React 的前端应用
- SQLite 数据库存储

## 开发环境要求

- Docker 和 Docker Compose
- Visual Studio Code (推荐，支持 Dev Container)
- Git

无需安装 Python、Node.js 或任何其他依赖，所有内容都在 Docker 容器中运行。

## 使用 Dev Container 进行开发（推荐）

### 1. 安装必要的工具

- 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
- 安装 [Visual Studio Code](https://code.visualstudio.com/)
- 在 VSCode 中安装 [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) 扩展

### 2. 克隆项目并启动开发容器

```bash
git clone https://github.com/您的用户名/visual_workflow_editor.git
cd visual_workflow_editor
```

在 VSCode 中打开项目文件夹，当提示"检测到 Devcontainer 配置"时，点击"在容器中重新打开"。或者通过命令面板（F1）选择"Dev Containers: Open Folder in Container"。

初次启动时，Dev Container 会自动构建开发环境，安装所有依赖，并准备好前后端服务。

### 3. 访问应用

容器启动完成后：

- 前端: http://localhost:3000
- 后端 API: http://localhost:8000

## 使用脚本进行开发（替代方法）

如果不使用 VS Code Dev Container，也可以使用项目提供的脚本进行开发：

```bash
# 启动开发环境
./scripts/dev.sh

# 重建容器（当依赖更新时）
./scripts/rebuild.sh

# 检查服务状态
./scripts/check-status.sh
```

## 项目结构

```
visual_workflow_editor/
├── .devcontainer/       # Dev Container配置
├── .github/workflows/   # GitHub Actions CI/CD配置
├── backend/             # Python后端
│   ├── app/             # 应用代码
│   └── Dockerfile       # 后端Docker配置
├── config/              # 配置文件目录
│   └── global_variables.json # 全局变量配置
├── deployment/          # 部署相关配置
├── dev_docs/            # 开发文档
├── frontend/            # React前端
│   ├── src/             # 源代码
│   └── Dockerfile       # 前端Docker配置
├── logs/                # 应用日志
├── scripts/             # 开发脚本
├── CHANGELOG.md         # 版本更新日志
└── README.md            # 项目说明
```

## 开发工作流

1. **使用终端**

   ```bash
   # 在容器中打开终端
   # 如果使用VS Code Dev Container，直接在VS Code终端中操作即可
   ```

2. **启动服务**

   ```bash
   # 在开发容器中，前后端服务会自动启动
   # 如需手动启动：
   cd /workspace/frontend && npm start
   cd /workspace/backend && python run_backend.py
   ```

3. **查看日志**

   ```bash
   # 前端日志
   tail -f /workspace/logs/frontend.log

   # 后端日志
   tail -f /workspace/logs/backend.log
   ```

## CI/CD 部署

本项目配置了 GitHub Actions 工作流，当推送到 main 或 master 分支时会自动：

1. 构建并测试代码
2. 将 Docker 镜像推送到 GitHub 容器注册表
3. 部署前端到 GitHub Pages（如适用）

## 配置说明

- 后端配置在`backend/.env`文件中
- 全局变量存储在`config/global_variables.json`中
- 数据库使用 SQLite，文件位于`config/flow_editor.db`

## 版本管理

项目使用语义化版本进行管理，版本号格式为：`主版本号.次版本号.修订号`

- 主版本号：当进行不兼容的 API 更改时递增
- 次版本号：当增加向下兼容的功能时递增
- 修订号：当进行向下兼容的问题修复时递增

### 版本更新工具

项目提供了一个版本更新脚本，可以自动更新版本号、创建 Git 标签和更新变更日志：

```bash
# 更新修订号（patch）
./scripts/update-version.sh

# 更新次版本号（minor）
./scripts/update-version.sh minor "添加新功能"

# 更新主版本号（major）
./scripts/update-version.sh major "重大更新"
```

### 版本历史

查看 [CHANGELOG.md](CHANGELOG.md) 获取完整版本历史和变更说明。
