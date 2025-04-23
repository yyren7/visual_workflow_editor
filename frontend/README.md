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
│   │   ├── apiClient.ts      # 配置 Axios 实例，添加请求/响应拦截器（如自动附加认证Token、处理401错误）。
│   │   ├── chatApi.ts        # 封装与聊天相关的后端 API 调用（普通聊天记录CRUD，Langchain聊天，SSE事件处理）。
│   │   ├── flowApi.ts        # 封装与工作流相关的后端 API 调用（CRUD、获取用户流程列表、复制、设置最后选择等）。
│   │   ├── llmApi.ts         # 封装与 LLM 相关的后端 API 调用（生成节点、更新节点、处理工作流提示）。
│   │   ├── nodeTemplates.ts  # 封装获取后端节点模板的 API 调用。
│   │   ├── otherApi.ts       # 封装其他零散的 API 调用（如发送邮件）。
│   │   ├── userApi.ts        # 封装用户认证和管理相关的 API 调用（注册、登录）。
│   │   └── variableApi.ts    # 封装工作流变量相关的后端 API 调用（CRUD、导入、导出）。
│   ├── components/           # 可复用的 UI 组件
│   │   ├── editor/           # Flow 编辑器相关的面板和工具栏组件
│   │   │   ├── ChatPanel.tsx           # 编辑器中的聊天面板，使用 DraggableResizableContainer。
│   │   │   ├── FlowToolbar.tsx         # 编辑器的工具栏 (保存、运行等)，现已集成到 EditorAppBar。
│   │   │   ├── FlowVariablesPanel.tsx # 编辑器中的流程变量面板，使用 DraggableResizableContainer。
│   │   │   ├── NodePropertiesPanel.tsx # 编辑器中的节点属性面板，使用 DraggableResizableContainer。
│   │   │   └── NodeSelectorSidebar.tsx # 编辑器中的节点选择侧边栏，是一个可折叠的 Drawer。
│   │   ├── nodes/            # 自定义 React Flow 节点组件
│   │   │   ├── ConditionNode.tsx     # 条件判断节点 (例如，基于真/假输出)。
│   │   │   ├── DecisionNode.tsx      # 决策节点 (可能有多个输出路径)。
│   │   │   ├── GenericNode.tsx       # 通用/基础节点，可显示基本信息和输入/输出句柄。
│   │   │   ├── InputNode.tsx         # 输入节点 (通常只有一个输出)。
│   │   │   ├── OutputNode.tsx        # 输出节点 (通常只有一个输入)。
│   │   │   └── ProcessNode.tsx       # 处理/任务节点 (通常有输入和输出)。
│   │   ├── ChatInterface.tsx   # 聊天界面组件，包含聊天列表侧边栏和主聊天窗口，支持发送消息、SSE流式响应、聊天记录管理(创建/删除/重命名/下载)。
│   │   ├── DraggableResizableContainer.tsx # 提供可拖拽、可调整大小的容器 HOC，用于包裹面板组件。
│   │   ├── EditorAppBar.tsx    # 流程图编辑器的顶部应用栏，包含流程图名称编辑、菜单(切换面板)、节点添加、布局、语言选择、用户菜单(选择流程图、登出)、保存状态显示。
│   │   ├── FlowCanvas.tsx      # 封装 React Flow 画布，处理节点/边的渲染、连接、拖拽、缩放、背景、控件、面板(版本信息、布局按钮)等。
│   │   ├── FlowEditor.tsx      # 核心的工作流编辑器主组件，整合 EditorAppBar, NodeSelectorSidebar, FlowCanvas, 以及各种面板(NodeProperties, FlowVariables, Chat)。管理 React Flow 状态和交互逻辑。
│   │   ├── FlowLoader.tsx      # 负责加载指定的流程图数据，处理加载状态、错误和权限，加载成功后渲染 FlowEditorWrapper。
│   │   ├── FlowSelect.tsx      # 流程图选择/管理对话框，允许用户查看、搜索、创建、重命名、复制和删除流程图。
│   │   ├── FlowVariables.tsx   # 工作流变量管理组件 (独立于编辑器面板)，允许添加/编辑/删除/导入/导出流程图变量。
│   │   ├── LanguageSelector.tsx # 语言切换组件，允许用户切换界面语言 (中/英/日)。
│   │   ├── Login.tsx           # 登录表单组件，处理用户登录逻辑，包含表单验证和错误处理。
│   │   ├── NavBar.tsx          # 全局导航栏组件 (可能已弃用或被 EditorAppBar 替代)，提供基本导航和用户状态显示。
│   │   ├── NodeProperties.tsx  # 节点属性显示/编辑组件，用于在 NodePropertiesPanel 中显示选定节点的属性。
│   │   ├── NodeSelector.tsx    # 节点选择器组件，从 API 获取可用节点模板并显示列表，支持拖拽到画布。
│   │   ├── ProtectedRoute.tsx  # 受保护路由 HOC 或组件，检查用户认证状态，未登录则重定向到登录页。
│   │   ├── Register.tsx        # 注册表单组件，处理用户注册逻辑。
│   │   ├── SelectPage.tsx      # 流程图选择的专用页面，包含顶部导航(登出)和始终打开的 FlowSelect 对话框。
│   │   ├── Sidebar.tsx         # 通用侧边栏组件 (可能已弃用或被 NodeSelectorSidebar 替代)，用于展示 NodeSelector。
│   │   ├── Submit.tsx          # 一个无需登录的页面，允许用户填写标题和内容并发送邮件。
│   │   ├── ToolCallCard.tsx    # 用于在 ChatInterface 中展示 LLM 工具调用和结果的卡片组件。
│   │   └── VersionInfo.tsx     # 显示应用版本信息的简单组件 (通常放在角落或 AppBar)。
│   ├── contexts/             # React Context API (全局状态管理)
│   │   ├── AuthContext.tsx     # 提供全局认证状态 (是否登录，用户信息)，管理 token 验证、登录、登出逻辑。
│   │   └── FlowContext.tsx     # 管理用户的工作流列表和当前选中的工作流 ID，负责从后端获取流程列表。
│   ├── hooks/                # 自定义 React Hooks (封装逻辑)
│   │   ├── useDraggablePanelPosition.ts # 管理可拖动面板的位置、边界约束和响应窗口大小变化。
│   │   ├── useFlowCore.ts      # 核心流程管理 Hook，负责加载指定 flowId 的数据，处理外部事件(如刷新、重命名)，并集成持久化逻辑。
│   │   ├── useFlowLayout.ts    # 提供自动布局算法 (分层布局) 和边交叉优化功能，用于整理 React Flow 画布元素。
│   │   ├── useFlowPersistence.ts # 负责流程图的自动保存 (防抖) 和初始加载，处理外部事件以保持数据同步。
│   │   ├── usePanelManager.ts  # 管理编辑器界面中各个面板 (侧边栏、节点信息、全局变量、聊天) 的显隐状态和位置。
│   │   └── useReactFlowManager.ts # 封装 React Flow 实例的交互逻辑，处理节点/边的变化、连接、拖放、点击等，并使用 Redux 进行状态管理。
│   ├── routes/               # 应用路由配置 (如果使用 React Router)
│   ├── store/                # 状态管理 (Redux Toolkit)
│   │   ├── slices/           # Redux Toolkit Slices (状态片段)
│   │   │   ├── authSlice.ts    # 定义认证相关的 Redux state、reducers 和 actions (登录成功、登出、加载状态、错误处理、Token 验证结果)。
│   │   │   └── flowSlice.ts    # 定义当前工作流相关的 Redux state、reducers、actions 和异步 thunks (获取、保存流程数据，节点/边操作)。
│   │   └── store.ts          # 配置 Redux store，组合各个 slice 的 reducers。
│   ├── App.tsx               # 应用根组件，设置主题、路由、全局上下文(Auth, Flow)和布局。
│   ├── i18n.ts               # 配置 i18next，提供多语言（中、英、日）翻译资源。
│   ├── index.css             # 全局 CSS 样式，包括基础样式、React Flow 节点/边/控件样式、拖拽样式等。
│   ├── index.tsx             # 应用入口文件，初始化 React、Redux Store、i18next，渲染 App 组件，并提供加载指示器。
│   └── types.ts              # 定义共享的 TypeScript 类型（如 Message, Chat, User）。
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
- **API 请求:** Axios (可能，基于 `apiClient.ts`
