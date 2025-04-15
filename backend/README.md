# 后端服务

本目录包含后端服务的代码和配置。

## 项目结构

```
backend/
├── app
│   ├── dependencies.py       # FastAPI 依赖项注入
│   ├── __init__.py           # 应用模块初始化
│   ├── logs/                 # 应用特定的日志文件 (app.log, deepseek_api.log等)
│   ├── main.py               # FastAPI 应用实例和全局配置
│   ├── __pycache__/          # Python 缓存
│   ├── routers/              # API 路由定义 (auth, chat, flow, user等)
│   ├── schemas.py            # Pydantic 数据模型 (请求/响应体)
│   ├── services/             # 业务逻辑服务层 (chat, flow, user等)
│   ├── utils_auth.py         # 认证相关的工具函数
│   └── utils.py              # 通用工具函数
├── config
│   ├── ai_config.py          # AI 相关配置 (模型名称等)
│   ├── app_config.py         # 应用基本配置
│   ├── base.py               # 配置基类或共享配置
│   ├── db_config.py          # 数据库连接配置
│   ├── __init__.py           # 配置模块初始化
│   ├── langchain_config.py   # Langchain 特定配置
│   ├── __pycache__/          # Python 缓存
│   └── simple_config.py      # 简化的配置加载器
├── Dockerfile                # Docker 构建文件
├── __init__.py               # backend 包初始化
├── langchainchat             # Langchain 核心聊天逻辑
│   ├── adapters/             # 适配器 (例如: 数据库内存适配器)
│   ├── agents/               # Langchain Agent 相关 (可能包含自定义 Agent)
│   ├── api/                  # Langchain 相关的 API 路由 (可能嵌入到 FastAPI)
│   ├── callbacks/            # Langchain 回调处理
│   ├── chains/               # Langchain Chain 定义 (RAG, Workflow)
│   ├── document_loaders/     # 文档加载器
│   ├── embeddings/           # 文本嵌入模型和搜索逻辑
│   ├── __init__.py           # Langchain 模块初始化
│   ├── llms/                 # 大语言模型客户端 (Deepseek)
│   ├── logs/                 # Langchain 特定的日志
│   ├── memory/               # 对话记忆管理 (数据库存储)
│   ├── models/               # Langchain 数据模型 (LLM 响应等)
│   ├── output_parsers/       # 输出解析器
│   ├── prompts/              # Prompt 模板管理
│   ├── __pycache__/          # Python 缓存
│   ├── README.md             # Langchain 模块的说明
│   ├── retrievers/           # 检索器 (基于 Embedding)
│   ├── scripts/              # Langchain 相关的脚本
│   ├── services/             # Langchain 服务层 (上下文, QA, 统一聊天)
│   ├── sessions/             # 会话数据存储 (例如: 文件会话)
│   ├── tools/                # Langchain 工具定义和执行器
│   ├── utils/                # Langchain 工具函数 (日志, 翻译等)
│   └── vectorstore/          # 向量数据库相关 (可能配置或客户端)
├── log                       # 全局日志目录 (按模块或类型组织)
│   ├── app/
│   ├── debug/
│   └── langchainchat/
├── __pycache__/              # Python 缓存 (顶层)
├── README.md                 # 本文档
├── requirements.txt          # Python 依赖库
├── run_backend.py            # 后端服务启动脚本
├── scripts
│   └── cleanup_after_refactor.py # 特定脚本 (例如: 重构后清理)
├── tests                     # 测试代码
│   ├── check_nodes.py
│   ├── __init__.py
│   ├── list_all_nodes.py
│   ├── list_flows.py
│   ├── __pycache__/
│   ├── test_*.py             # 各种测试文件 (单元, 集成, 服务等)
│   └── verify_node.py
└── update_version.py         # 版本更新脚本
```

_注意：以上结构基于 `tree -L 3` 命令生成，并添加了部分推断的注释。`__pycache__`, `.log`, `.env` 等文件/目录通常应添加到 `.gitignore` 中。_

## 环境设置

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
- 根据项目具体情况，可能需要进行数据库初始化或迁移操作，请参考 `scripts/` 目录下的脚本或相关文档说明。
