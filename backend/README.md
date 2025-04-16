# 后端服务

本目录包含后端服务的代码和配置。

## 技术栈 (Technology Stack)

本项目后端主要采用以下技术栈：

- **框架 (Framework):** [FastAPI](https://fastapi.tiangolo.com/) - 一个现代、快速（高性能）的 Python Web 框架，用于构建 API。利用了 Python 3.7+ 的类型提示，具有自动数据验证和 API 文档生成功能。
- **语言 (Language):** [Python](https://www.python.org/) (推荐 3.8+) - 主要开发语言。
- **AI 核心 (AI Core):** [Langchain](https://python.langchain.com/) - 用于构建基于大型语言模型 (LLM) 的应用程序的框架。本项目利用它来组织聊天逻辑、RAG (Retrieval-Augmented Generation)、Agent 执行、自定义链 (`chains/`) 和工作流 (`chains/workflow_chain.py`)。
  - **LLM:** [Deepseek](https://www.deepseek.com/) (可能) - 根据 API 密钥配置 (`config/ai_config.py`) 推断，可能作为主要的语言模型接口之一 (`langchainchat/llms/`)。
- **数据验证 (Data Validation):** [Pydantic](https://docs.pydantic.dev/) - 基于 Python 类型提示进行数据验证和设置管理。FastAPI 广泛使用它来定义请求/响应模型 (`app/schemas.py`)。
- **异步处理 (Asynchronous Processing):** [Asyncio](https://docs.python.org/3/library/asyncio.html) - Python 的原生异步 I/O 框架，FastAPI 基于此构建，实现高并发性能。
- **数据库交互 (Database Interaction):** (推断) 很可能使用了 [SQLAlchemy](https://www.sqlalchemy.org/) 或其他异步数据库驱动（如 `asyncpg`, `databases`) 与关系型数据库进行交互 (依据 `config/db_config.py` 和常见的 FastAPI 实践)。具体实现需查看 `requirements.txt` 和相关服务代码。
- **配置管理 (Configuration):** 自定义 Python 配置模块 (`config/` 目录) - 用于管理应用、数据库、AI 服务等各项配置。
- **测试 (Testing):** [Pytest](https://docs.pytest.org/) - 用于编写和运行单元测试、集成测试 (`tests/` 目录)。
- **容器化 (Containerization):** [Docker](https://www.docker.com/) - 用于打包和部署应用 (`Dockerfile`)。
- **API 文档 (API Documentation):** [Swagger UI / OpenAPI](https://swagger.io/) - 由 FastAPI 自动生成，提供交互式 API 文档界面 (通常访问后端服务的 `/docs` 路径即可查看)。

## 项目结构

```
backend/
├── app                       # FastAPI 应用核心目录
│   ├── dependencies.py       # FastAPI 依赖项注入 (例如: 获取数据库会话, 验证用户)
│   ├── __init__.py           # 应用模块初始化
│   ├── main.py               # FastAPI 应用实例、全局中间件、异常处理和启动配置
│   ├── __pycache__/          # Python 缓存
│   ├── routers/              # API 路由定义 (按功能模块划分)
│   │   ├── auth.py           # 处理用户认证、令牌生成/验证的路由
│   │   ├── chat.py           # 聊天相关 API 接口
│   │   ├── flow.py           # 工作流 (Flow) 的 CRUD (创建/读取/更新/删除) 路由
│   │   ├── flow_variables.py # 工作流变量管理的 API 接口
│   │   ├── node_templates.py # 工作流节点模板相关的 API 接口
│   │   ├── user.py           # 用户信息管理相关的 API 接口
│   │   ├── workflow_router.py # 执行或与特定工作流交互的 API 路由
│   │   └── email.py          # 邮件服务相关的 API 接口 (如果需要)
│   ├── schemas.py            # Pydantic 数据模型 (定义 API 请求/响应的数据结构)
│   ├── services/             # API 层对应的业务逻辑服务
│   │   ├── chat_service.py   # 处理聊天 API 请求，协调 Langchain 聊天逻辑
│   │   ├── flow_service.py   # 实现工作流的 CRUD 和管理逻辑
│   │   ├── flow_variable_service.py # 实现工作流变量的业务逻辑
│   │   ├── node_template_service.py # 实现节点模板相关的业务逻辑
│   │   └── user_flow_service.py # 处理用户与工作流关联的逻辑
│   ├── utils_auth.py         # 认证相关的工具函数 (例如: 密码哈希, JWT 处理)
│   └── utils.py              # 通用工具函数
├── config                    # 配置目录
│   ├── ai_config.py          # AI 相关配置 (模型名称, API Keys 等)
│   ├── app_config.py         # 应用基本配置 (主机, 端口等)
│   ├── base.py               # 配置基类或共享配置
│   ├── db_config.py          # 数据库连接配置
│   ├── __init__.py           # 配置模块初始化
│   ├── langchain_config.py   # Langchain 特定配置
│   ├── __pycache__/          # Python 缓存
│   └── simple_config.py      # 简化的配置加载器
├── Dockerfile                # Docker 构建文件
├── __init__.py               # backend 包初始化
├── langchainchat             # Langchain 核心 AI 逻辑目录
│   ├── adapters/             # 适配器 (例如: 数据库内存适配器)
│   ├── agents/               # Langchain Agent 相关 (可能包含自定义 Agent)
│   ├── api/                  # Langchain 相关的 API 路由 (可能嵌入到 FastAPI 或独立)
│   ├── callbacks/            # Langchain 回调处理 (用于监控、日志记录等)
│   ├── chains/               # Langchain Chain 定义 (核心业务流程)
│   │   ├── rag_chain.py      # 实现 RAG (Retrieval-Augmented Generation) 链
│   │   └── workflow_chain.py # 实现执行自定义工作流的链逻辑
│   ├── document_loaders/     # 文档加载器 (用于 RAG)
│   ├── embeddings/           # 文本嵌入模型和向量搜索逻辑
│   ├── __init__.py           # Langchain 模块初始化
│   ├── llms/                 # 大语言模型客户端封装 (例如: Deepseek)
│   ├── logs/                 # Langchain 特定的日志
│   ├── memory/               # 对话记忆管理 (例如: 基于数据库存储历史记录)
│   ├── models/               # Langchain 数据模型 (例如: LLM 响应结构)
│   ├── output_parsers/       # 解析 LLM 输出的解析器
│   ├── prompts/              # Prompt 模板管理
│   ├── __pycache__/          # Python 缓存
│   ├── README.md             # Langchain 模块的说明
│   ├── retrievers/           # 检索器 (用于 RAG, 基于 Embedding)
│   ├── scripts/              # Langchain 相关的脚本
│   ├── services/             # 基于 Langchain 组件构建的服务层
│   │   ├── chat_service.py   # 核心 Langchain 聊天服务 (处理 LLM 调用, 记忆, 工具使用)
│   │   ├── context_service.py # 管理聊天或 RAG 的上下文信息
│   │   ├── qa_service.py     # 问答服务 (可能基于 RAG chain)
│   │   └── unified_chat_service.py # 统一不同聊天模式的接口
│   ├── sessions/             # 会话数据存储 (例如: 文件会话)
│   ├── tools/                # Langchain 工具定义和执行器 (Agent 可用的工具)
│   ├── utils/                # Langchain 工具函数 (日志, 翻译等)
│   └── vectorstore/          # 向量数据库交互逻辑 (配置或客户端)
├── __pycache__/              # Python 缓存 (顶层)
├── README.md                 # 本文档 (你正在阅读的文件)
├── requirements.txt          # Python 依赖库列表
├── run_backend.py            # 后端服务启动脚本 (通常使用 uvicorn 启动 FastAPI)
├── scripts                   # 存放各种辅助脚本
│   └── cleanup_after_refactor.py # 特定脚本 (例如: 重构后清理)
├── tests                     # 测试代码目录
│   ├── check_nodes.py
│   ├── __init__.py
│   ├── list_all_nodes.py
│   ├── list_flows.py
│   ├── __pycache__/
│   ├── test_*.py             # 各种测试文件 (单元, 集成, 服务等)
│   └── verify_node.py
└── update_version.py         # 版本更新脚本
```

_注意：以上结构基于 `tree -L 3` 命令生成，并添加了部分推断的注释。`__pycache__`, `.log`, `.env` 等文件/目录通常应添加到 `.gitignore` 中。_

## 环境设置

除了安装依赖和配置 API 密钥外，项目的详细配置（如数据库连接、AI 模型参数等）可以在 `config/` 目录下的相应文件中找到和修改。系统启动时会自动加载这些配置。

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. API 密钥配置

为了保证安全，API 密钥应通过环境变量提供，不应在代码中明文保存。系统支持以下几种方式设置 API 密钥（按优先级排序）：

1.  **环境变量方式**（推荐，临时有效）：

    ```bash
    export DEEPSEEK_API_KEY=your_actual_key_here
    # 根据实际需要设置其他 API 密钥，例如：
    # export OTHER_SERVICE_API_KEY=your_other_key
    ```

2.  **.env 文件方式**（本地开发推荐）：

    ```bash
    # 复制示例配置文件 (如果 .env.example 存在)
    # cp .env.example .env

    # 创建或编辑 .env 文件
    nano .env
    # 添加或修改相应的 API 密钥:
    # DEEPSEEK_API_KEY=your_actual_key_here
    # OTHER_SERVICE_API_KEY=your_other_key
    ```

    _重要：请确保将 `.env` 文件添加到 `.gitignore` 中，以防密钥泄露。_

3.  **.bashrc 或 .zshrc 方式**（长期有效）：

    ```bash
    # 编辑配置文件 (例如 .bashrc)
    nano ~/.bashrc

    # 在文件末尾添加
    export DEEPSEEK_API_KEY='your_actual_key_here'
    # export OTHER_SERVICE_API_KEY='your_other_key'

    # 使更改生效
    source ~/.bashrc
    ```

系统启动时会自动尝试以上方式读取 API 密钥。请根据你的项目实际需要配置相应的密钥。

## 启动服务

确保环境和依赖设置完成后，在 `backend` 目录下运行以下命令启动后端服务：

```bash
python run_backend.py
```

## Docker 部署

项目提供了 `Dockerfile`，可以使用 Docker 进行构建和部署。

```bash
# 构建镜像 (在 backend 目录执行)
docker build -t backend-service .

# 运行容器 (需要传递环境变量, 推荐使用 --env-file)
# 确保你的 .env 文件包含所有必需的环境变量
docker run -d --env-file .env -p 8000:8000 backend-service
```

_请根据实际情况调整主机端口 (`8000`) 和容器暴露的端口 (`8000`)。_

## 测试

运行测试（请根据项目实际使用的测试框架调整命令）：

```bash
# 示例: 使用 pytest
pytest tests/
```

## 注意

- `__pycache__/` 和 `log/` 目录通常不需要提交到版本控制，建议添加到 `.gitignore`。
- **数据库设置**: 根据 `config/db_config.py` 中的配置，确保你已经设置了相应的数据库（例如，创建数据库、用户、授权等）。如果项目包含数据库迁移脚本（可能位于 `scripts/` 目录或使用 Alembic 等工具），请在首次启动或模型更改后运行它们。
