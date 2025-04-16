# 前端服务

本目录包含前端 React 应用的代码和配置。

## 项目结构

```
frontend/
├── build/                    # 生产构建输出目录 (通常由 CI/CD 生成)
├── node_modules/             # 项目依赖 (由 npm/yarn 管理)
├── public/                   # 公共静态资源目录
│   ├── index.html            # 应用的 HTML 入口文件
│   └── manifest.json         # Web 应用清单文件
├── src/                      # 应用源代码目录
│   ├── api/                  # API 请求封装 (与后端交互)
│   │   ├── apiClient.ts      # Axios 或 Fetch 客户端配置，处理认证和基础 URL
│   │   ├── chatApi.ts        # 聊天相关 API 调用
│   │   ├── flowApi.ts        # 工作流管理 (CRUD) API 调用
│   │   ├── llmApi.ts         # 与 LLM 或 AI 相关 API 调用
│   │   ├── nodeTemplates.ts  # 节点模板相关 API 调用
│   │   ├── otherApi.ts       # 其他零散 API 调用
│   │   ├── userApi.ts        # 用户认证和管理 API 调用
│   │   └── variableApi.ts    # 工作流变量相关 API 调用
│   ├── components/           # 可复用的 UI 组件
│   │   ├── editor/           # Flow 编辑器相关的面板和工具栏组件
│   │   │   ├── ChatPanel.tsx           # 编辑器中的聊天面板
│   │   │   ├── FlowToolbar.tsx         # 编辑器的工具栏 (保存、运行等)
│   │   │   ├── FlowVariablesPanel.tsx # 编辑器中的流程变量面板
│   │   │   ├── NodePropertiesPanel.tsx # 编辑器中的节点属性面板
│   │   │   └── NodeSelectorSidebar.tsx # 编辑器中的节点选择侧边栏
│   │   ├── nodes/            # 自定义 React Flow 节点组件
│   │   │   ├── ConditionNode.tsx     # 条件判断节点
│   │   │   ├── DecisionNode.tsx      # 决策节点
│   │   │   ├── GenericNode.tsx       # 通用/基础节点
│   │   │   ├── InputNode.tsx         # 输入节点
│   │   │   ├── OutputNode.tsx        # 输出节点
│   │   │   └── ProcessNode.tsx       # 处理/任务节点
│   │   ├── ChatInterface.tsx   # 独立的聊天界面组件
│   │   ├── DraggableResizableContainer.tsx # 可拖拽调整大小的容器
│   │   ├── EditorAppBar.tsx    # 编辑器顶部的应用栏
│   │   ├── FlowCanvas.tsx      # React Flow 画布容器
│   │   ├── FlowEditor.tsx      # 核心的工作流编辑器主组件
│   │   ├── FlowLoader.tsx      # 加载工作流的选择/管理界面
│   │   ├── FlowSelect.tsx      # (可能与 FlowLoader 类似或为其子组件)
│   │   ├── FlowVariables.tsx   # 工作流变量管理组件 (可能独立于编辑器)
│   │   ├── LanguageSelector.tsx # 语言切换组件
│   │   ├── Login.tsx           # 登录表单组件
│   │   ├── NavBar.tsx          # 导航栏组件
│   │   ├── NodeProperties.tsx  # 节点属性显示/编辑组件 (可能被 Panel 使用)
│   │   ├── NodeSelector.tsx    # 节点选择器组件 (可能被 Sidebar 使用)
│   │   ├── ProtectedRoute.tsx  # 受保护路由 HOC 或组件
│   │   ├── Register.tsx        # 注册表单组件
│   │   ├── SelectPage.tsx      # (可能与 FlowLoader/FlowSelect 相关)
│   │   ├── Sidebar.tsx         # 通用侧边栏组件
│   │   ├── Submit.tsx          # (可能用于表单提交)
│   │   └── VersionInfo.tsx     # 显示版本信息的组件
│   ├── contexts/             # React Context API (全局状态管理)
│   │   ├── AuthContext.tsx     # 认证状态管理
│   │   └── FlowContext.tsx     # 当前工作流状态管理
│   ├── hooks/                # 自定义 React Hooks (封装逻辑)
│   │   ├── useDraggablePanelPosition.ts # 管理可拖动面板位置
│   │   ├── useFlowCore.ts      # React Flow 核心交互逻辑
│   │   ├── useFlowLayout.ts    # 工作流布局算法
│   │   ├── useFlowPersistence.ts # 工作流保存/加载逻辑
│   │   ├── usePanelManager.ts  # 管理编辑器中多个面板的 Hook
│   │   └── useReactFlowManager.ts # 封装 React Flow 实例管理和操作
│   ├── routes/               # 应用路由配置 (如果使用 React Router)
│   ├── store/                # 状态管理 (例如 Redux Toolkit)
│   │   ├── slices/           # Redux Toolkit Slices
│   │   │   ├── authSlice.ts    # 认证相关的状态和 Reducers
│   │   │   └── flowSlice.ts    # 工作流相关的状态和 Reducers
│   │   └── store.ts          # Redux Store 配置
│   ├── App.tsx               # 应用根组件，包含路由和布局
│   ├── i18n.ts               # 国际化配置 (i18next)
│   ├── index.css             # 全局 CSS 样式
│   ├── index.tsx             # 应用入口文件 (渲染 App 组件)
│   └── types.ts              # TypeScript 类型定义
├── .env                      # 环境变量文件 (需要添加到 .gitignore)
├── .gitignore                # Git 忽略配置
├── craco.config.js           # Craco 配置文件 (用于自定义 CRA 配置)
├── Dockerfile                # Docker 构建文件
├── package-lock.json         # 精确的依赖版本锁定
├── package.json              # 项目元数据和依赖管理
└── tsconfig.json             # TypeScript 编译器配置
```

_注意：以上结构基于实际文件探查生成，`node_modules` 和 `build` 目录通常不包含在源代码管理中。_

## 环境设置

### 1. 安装 Node.js 和 npm/yarn

确保你的开发环境已经安装了 Node.js (推荐 LTS 版本) 和 npm (通常随 Node.js 安装) 或 yarn。

### 2. 安装依赖

在 `frontend` 目录下运行以下命令安装项目所需的依赖库：

```bash
# 使用 npm
npm install

# 或者使用 yarn
yarn install
```

### 3. 配置环境变量

前端应用可能需要连接到后端 API。通常后端 API 的地址需要在环境变量中配置。

1.  创建 `.env` 文件：
    在 `frontend` 目录下创建一个 `.env` 文件 (可以从 `.env.example` 复制，如果存在的话)。

2.  配置 API 地址：
    在 `.env` 文件中添加类似以下的行，指向你的后端服务地址：

    ```
    REACT_APP_API_BASE_URL=http://localhost:8000
    ```

    _请将 `http://localhost:8000` 替换为你的后端实际运行的地址和端口。_
    _根据 `src/api/apiClient.ts` 的实现，可能需要检查实际使用的环境变量名称。_

_重要：确保将 `.env` 文件添加到 `.gitignore` 中，以防敏感信息泄露。_

## 开发服务器启动

完成环境设置后，运行以下命令启动本地开发服务器：

```bash
# 使用 npm
npm start

# 或者使用 yarn
yarn start
```

这将启动一个热重载的开发服务器，通常监听在 `http://localhost:3000`。

## 构建项目

要构建用于生产部署的优化版本，运行：

```bash
# 使用 npm
npm run build

# 或者使用 yarn
yarn build
```

构建产物将默认输出到 `build/` 目录。

## Docker 部署

项目提供了 `Dockerfile`，可以使用 Docker 进行构建和部署。

```bash
# 1. 构建镜像 (在 frontend 目录执行)
docker build -t frontend-app .

# 2. 运行容器
# 通常 Nginx 或类似服务器用于服务静态文件
# 以下是一个示例，假设 Dockerfile 内部使用 Nginx
docker run -d -p 80:80 frontend-app

# 注意：实际运行命令取决于 Dockerfile 的具体内容。
# 可能需要将后端的 API 地址作为环境变量传递给容器，
# 或在 Nginx 配置中设置反向代理。
```

请检查 `Dockerfile` 以了解确切的构建和运行方式。

## 技术栈

- **框架:** React (使用 Create React App + Craco 自定义配置)
- **语言:** TypeScript
- **状态管理:** Redux Toolkit, React Context
- **UI 库:** (可能使用了 Material UI, Ant Design 或其他，需查看 `package.json` 或组件代码确认)
- **路由:** React Router (可能)
- **流程图/编辑器:** React Flow
- **API 请求:** Axios (可能，基于 `apiClient.ts` 的常见实践)
- **国际化:** i18next
- **样式:** CSS / CSS Modules / Styled Components (需检查具体实现)
