# 可视化工作流编辑器

这是一个基于Docker容器化的可视化工作流编辑器项目，支持跨平台开发和CI/CD部署。

## 项目说明

本项目包含：
- 基于FastAPI的后端服务
- 基于React的前端应用
- SQLite数据库存储

## 开发环境要求

- Docker 和 Docker Compose
- Git

无需安装Python、Node.js或任何其他依赖，所有内容都在Docker容器中运行。

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/您的用户名/visual_workflow_editor.git
cd visual_workflow_editor
```

### 2. 启动开发环境

```bash
# 在Windows中
.\dev.sh

# 在Linux/Mac中
chmod +x dev.sh
./dev.sh
```

### 3. 访问应用

- 前端: http://localhost:3000
- 后端API: http://localhost:8000

## 开发工作流

1. **进入开发容器**
   ```bash
   docker exec -it workflow-editor-dev bash
   ```

2. **查看日志**
   ```bash
   docker-compose logs -f
   ```

3. **停止环境**
   ```bash
   docker-compose down
   ```

## 项目结构

```
visual_workflow_editor/
├── backend/             # Python后端
│   ├── app/             # 应用代码
│   └── Dockerfile       # 后端Docker配置
├── frontend/            # React前端
│   ├── src/             # 源代码
│   └── Dockerfile       # 前端Docker配置
├── .github/workflows/   # GitHub Actions CI/CD配置
├── docker-compose.yml   # Docker Compose配置
├── dev.sh               # 开发环境启动脚本
└── README.md            # 项目说明
```

## CI/CD部署

本项目配置了GitHub Actions工作流，当推送到main或master分支时会自动：

1. 构建并测试代码
2. 将Docker镜像推送到GitHub容器注册表
3. 部署前端到GitHub Pages（如适用）

## 配置说明

- 后端配置在`.env`文件中
- 全局变量存储在`global_variables.json`中
- 数据库使用SQLite，文件位于`flow_editor.db`

## 版本管理

项目使用语义化版本进行管理，版本号格式为：`主版本号.次版本号.修订号`

- 主版本号：当进行不兼容的API更改时递增
- 次版本号：当增加向下兼容的功能时递增
- 修订号：当进行向下兼容的问题修复时递增

### 版本更新工具

项目提供了一个版本更新脚本，可以自动更新版本号、创建Git标签和更新变更日志：

```bash
# 更新修订号（patch）
./update-version.sh

# 更新次版本号（minor）
./update-version.sh minor "添加新功能"

# 更新主版本号（major）
./update-version.sh major "重大更新"
```

### 版本历史

查看 [CHANGELOG.md](CHANGELOG.md) 获取完整版本历史和变更说明。 