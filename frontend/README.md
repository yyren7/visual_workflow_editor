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
│   │   ├── apiClient.ts      # 配置全局 Axios 实例，添加请求/响应拦截器（自动附加认证Token、处理401错误）。
│   │   ├── chatApi.ts        # 封装与聊天相关的后端 API 调用，包括聊天记录CRUD和LangGraph聊天流式处理（SSE）。
│   │   ├── flowApi.ts        # 封装与工作流相关的后端 API 调用（CRUD、复制、获取用户流程列表等）。
│   │   ├── llmApi.ts         # 封装与 LLM 相关的 API 调用（生成/更新节点）。
│   │   ├── nodeTemplates.ts  # 封装获取后端节点模板的 API 调用。
│   │   ├── otherApi.ts       # 封装其他零散的 API 调用（如发送邮件）。
│   │   ├── userApi.ts        # 封装用户认证和管理相关的 API 调用（注册、登录）。
│   │   ├── variableApi.ts    # 封装工作流变量相关的 API 调用（CRUD、导入/导出）。
│   │   └── sasApi.ts         # 封装与LangGraph Agent状态管理相关的 API 调用。
│   ├── components/           # 可复用的 UI 组件
│   │   ├── chat/             # 聊天界面相关的原子组件
│   │   │   ├── ChatMessageArea.tsx # 渲染聊天消息区域，包括消息内容、工具调用卡片和编辑表单。
│   │   │   ├── MessageInputBar.tsx # 聊天输入框和发送按钮。
│   │   │   └── DeleteChatDialog.tsx # 删除聊天的确认对话框。
│   │   ├── editor/           # Flow 编辑器相关的面板和工具栏组件
│   │   │   ├── ChatPanel.tsx           # 编辑器中的聊天面板，是 `ChatInterface` 的一个封装。
│   │   │   ├── FlowToolbar.tsx         # (已弃用) 编辑器的工具栏，功能已集成到 `EditorAppBar`。
│   │   │   ├── FlowVariablesPanel.tsx # 编辑器中的流程变量面板。
│   │   │   ├── NodePropertiesPanel.tsx # 编辑器中的节点属性面板。
│   │   │   └── NodeSelectorSidebar.tsx # 编辑器中的节点选择侧边栏。
│   │   ├── nodes/            # 自定义 React Flow 节点组件
│   │   │   ├── GenericNode.tsx       # 通用的基础节点组件。
│   │   │   ├── LangGraphInputNode.tsx # LangGraph流程的输入节点，处理用户请求和Agent状态展示。
│   │   │   ├── LangGraphTaskNode.tsx  # LangGraph流程的任务节点，展示任务详情。
│   │   │   └── LangGraphDetailNode.tsx# LangGraph流程的细节节点，展示任务的具体步骤。
│   │   ├── ChatInterface/    # 模块化的聊天界面及其逻辑
│   │   │   ├── index.tsx         # 聊天界面的主组件，整合了数据、行为和SSE处理。
│   │   │   ├── useChatData.ts    # Hook，负责获取和管理聊天列表和消息数据。
│   │   │   ├── useChatActions.ts   # Hook，封装所有用户交互（发送、新建、重命名、删除、编辑）。
│   │   │   ├── useSSEHandler.ts  # Hook，管理与后端的SSE连接，处理实时事件流。
│   │   │   ├── types.ts          # 定义聊天相关的TypeScript类型。
│   │   │   └── utils.ts          # 聊天相关的工具函数（如下载Markdown）。
│   │   ├── FlowEditor/       # 核心工作流编辑器
│   │   │   ├── index.tsx         # 编辑器主组件，整合所有UI和逻辑。
│   │   │   ├── useFlowConfig.ts  # Hook，管理React Flow的配置。
│   │   │   ├── useSaveHandler.ts # Hook，处理流程的保存逻辑。
│   │   │   └── ...               # 其他辅助组件和类型定义。
│   │   ├── FlowSelect/       # 流程选择对话框
│   │   │   ├── index.tsx         # 流程选择/管理对话框主组件。
│   │   │   └── ...               # 对话框的子组件和Hooks。
│   │   ├── DraggableResizableContainer.tsx # 提供可拖拽、可调整大小的容器HOC。
│   │   ├── EditorAppBar.tsx    # 流程图编辑器的顶部应用栏。
│   │   ├── FlowCanvas.tsx      # 封装 React Flow 画布，处理渲染和基本交互。
│   │   ├── FlowLoader.tsx      # 加载指定的流程图数据，处理加载、错误和权限。
│   │   ├── FlowVariables.tsx   # (独立页面) 工作流变量管理组件。
│   │   ├── LanguageSelector.tsx # 语言切换组件。
│   │   ├── Login.tsx           # 登录表单组件。
│   │   ├── NodeProperties.tsx  # (底层) 节点属性显示/编辑组件。
│   │   ├── NodeSelector.tsx    # (底层) 节点选择器列表组件。
│   │   ├── ProtectedRoute.tsx  # 受保护路由HOC。
│   │   ├── Register.tsx        # 注册表单组件。
│   │   ├── SelectPage.tsx      # 流程图选择的专用页面。
│   │   ├── Submit.tsx          # 一个无需登录的邮件发送页面。
│   │   └── VersionInfo.tsx     # 显示应用版本信息的组件。
│   ├── contexts/             # React Context API (全局状态管理)
│   │   ├── AuthContext.tsx     # 提供全局认证状态和登录/登出逻辑。
│   │   └── FlowContext.tsx     # 管理用户的工作流列表和当前选中的工作流。
│   ├── hooks/                # 自定义 React Hooks (封装通用逻辑)
│   │   ├── useAgentStateSync.ts # 同步后端的LangGraph Agent状态到Redux。
│   │   ├── useChat.ts           # (可能已部分弃用) 简单的聊天逻辑Hook。
│   │   ├── useDraggablePanelPosition.ts # 管理可拖动面板的位置。
│   │   ├── useFlowCore.ts      # (已弃用) 旧的核心流程管理Hook。
│   │   ├── useFlowLayout.ts    # 提供自动布局算法。
│   │   ├── useFlowPersistence.ts # (已弃用) 旧的自动保存Hook。
│   │   ├── useLangGraphNodes.ts # 根据Agent状态生成和同步LangGraph节点。
│   │   ├── usePanelManager.ts  # 管理编辑器中各个面板的显隐状态。
│   │   ├── useReactFlowManager.ts # 封装React Flow实例的交互逻辑，并与Redux集成。
│   │   └── useSSEManager.ts    # 全局单例SSE连接管理器。
│   ├── store/                # 状态管理 (Redux Toolkit)
│   │   ├── slices/           # Redux Toolkit Slices
│   │   │   ├── authSlice.ts    # 定义认证相关的Redux state和actions。
│   │   │   └── flowSlice.ts    # 定义当前工作流的state和actions，包括节点、边和Agent状态。
│   │   └── store.ts          # 配置和创建Redux store。
│   ├── styles/               # 全局样式文件
│   │   └── performance-optimizations.css # 针对性能优化的特定样式。
│   ├── utils/                # 通用工具函数
│   │   └── quickResetTool.js # 用于开发过程中的快速重置工具。
│   ├── App.tsx               # 应用根组件，设置主题、路由和全局上下文。
│   ├── decs.d.ts             # TypeScript类型声明文件。
│   ├── i18n.ts               # 配置i18next，提供多语言翻译资源。
│   ├── index.css             # 全局CSS样式。
│   ├── index.tsx             # 应用入口文件，初始化React和Redux。
│   └── types.ts              # 定义共享的TypeScript类型。
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
- **UI 库:** Material-UI
- **路由:** React Router
- **流程图/编辑器:** React Flow
- **API 请求:** Axios
