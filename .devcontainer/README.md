# 流程编辑器 DevContainer 开发环境

这个 DevContainer 配置为前后端开发提供了一个完整的开发环境。

## 环境特点

- 整合了前端（React）和后端（Python FastAPI）开发环境
- 提供了实时查看前后端日志的功能
- 预安装了常用的开发工具和扩展
- 配置了快捷命令简化开发流程

## 开始使用

1. 确保你的开发环境已安装 Visual Studio Code 和 Docker
2. 安装 VS Code 的 "Remote - Containers" 扩展
3. 打开项目文件夹
4. 点击 VS Code 左下角的绿色按钮，选择 "Reopen in Container"
5. 等待容器构建完成，这可能需要几分钟

## 开发命令

容器启动后，你可以使用以下命令来启动开发环境：

```bash
# 同时启动前后端，并在 tmux 分屏中显示两个服务的日志
./start-dev.sh logs

# 只启动前端开发服务器
./start-dev.sh frontend

# 只启动后端开发服务器
./start-dev.sh backend
```

## 端口映射

- 前端服务端口：3001
- 后端服务端口：8000

## 预安装的工具和扩展

### 后端开发

- Python 3.10
- FastAPI, SQLAlchemy
- pylint, flake8, black
- pytest

### 前端开发

- Node.js 16
- React
- ESLint, Prettier
- TypeScript

### 开发工具

- Git
- Docker CLI
- SQLite 工具
- tmux (用于分屏显示日志)

## 自定义配置

如果需要自定义环境，可以修改以下文件：

- `.devcontainer/devcontainer.json` - VS Code 配置和插件
- `.devcontainer/docker-compose.yml` - 容器服务配置
- `.devcontainer/Dockerfile` - 开发环境构建配置
- `.devcontainer/post-create.sh` - 容器创建后的初始化脚本

## 常见问题

1. **前端热重载不工作**

   - 确保 `.devcontainer/docker-compose.yml` 中设置了 `CHOKIDAR_USEPOLLING=true`

2. **无法连接到后端服务**

   - 检查前端配置中的 API 地址是否正确设置为 `http://localhost:8000`

3. **访问数据库问题**
   - 可以使用 VS Code 的 SQLTools 扩展，已预先配置连接到 SQLite 数据库
