# LangGraph 聊天模块

本模块基于 LangGraph 框架实现了聊天功能，支持通过配置的 LLM API (如 DeepSeek) 进行对话，并能够集成与流程图相关的工具。项目正在从 Langchain 向 LangGraph 迁移，部分组件可能仍有 Langchain 的痕迹或正在过渡。

## 功能特点

1.  **LangGraph 状态图驱动对话**: 使用 LangGraph 的 `StateGraph` 定义和执行对话流程，包括 Agent 决策、工具调用和条件路由。
2.  **上下文感知对话**: 能够收集系统信息、用户信息和当前流程图上下文，为 LLM 提供更丰富的对话背景。
3.  **会话管理**:
    - 支持将会话历史保存到本地 JSON 文件 (通过 `EnhancedConversationMemory`)。
    - 提供了基于数据库的聊天记录管理框架 (`DbChatMemory`)，但其依赖的 `ChatService` 目前在项目中缺失。
4.  **工具集成**: 提供了与流程图创建、修改、查询相关的工具，这些工具被设计为可以被 LangGraph Agent 调用。
5.  **可配置 LLM**: 支持通过配置使用不同的 LLM (如 DeepSeek, Azure OpenAI, ZhipuAI)，并管理 API 密钥和模型参数。
6.  **模块化设计**: 各组件如 LLM 封装、记忆管理、提示工程、工具定义、图定义等分离到不同模块。
7.  **异步操作**: 核心的图执行、LLM 调用和部分工具操作设计为异步。

## 目录结构

```
backend/langgraphchat/
├── __init__.py                   # 模块初始化，定义版本号。
├── context.py                    # 定义 ContextVar (current_flow_id_var) 用于传递当前流程图 ID。
├── README.md                     # 本文件。
│
├── api/                          # API 接口 (FastAPI)
│   ├── __init__.py               # API 模块初始化，导出 chat_router。
│   └── chat_router.py            # 定义聊天相关的 FastAPI 路由 (如 /message, /conversations)。依赖 ChatService。
│
├── adapters/                     # 数据适配器
│   └── db_memory_adapter.py      # 提供在 EnhancedConversationMemory 和数据库记录之间同步聊天消息的适配器。
│
├── embeddings/                   # 嵌入向量和搜索相关功能
│   ├── __init__.py               # 导出 search_by_text, search_nodes。
│   ├── config.py                 # 定义 SearchConfig (Pydantic模型) 用于搜索参数。
│   ├── semantic_search.py        # 实现 search_by_text 函数，调用 DatabaseEmbeddingService 进行语义搜索。
│   ├── node_search.py            # 实现 search_nodes 函数，用于搜索本地 XML 节点数据库或节点模板服务。
│   └── utils.py                  # 搜索相关的辅助函数 (normalize_json, extract_keywords, format_search_result)。
│
├── graph/                        # LangGraph 图定义
│   ├── __init__.py               # (通常为空或导出主要图组件)
│   ├── agent_state.py            # 定义 AgentState (TypedDict)，用于 LangGraph 状态图。
│   └── workflow_graph.py         # 核心：定义 LangGraph 的 StateGraph (agent_node, tool_node, should_continue, compile_workflow_graph)。
│
├── llms/                         # LLM 客户端封装 (之前在 models/llm.py)
│   └── deepseek_client.py        # 定义 DeepSeekLLM 类 (继承 BaseChatModel)，封装 OpenAI 兼容的 API 调用。
│
├── memory/                       # 记忆组件
│   ├── __init__.py               # 导出 EnhancedConversationMemory, create_memory。
│   ├── conversation_memory.py    # 定义 EnhancedConversationMemory (继承 ConversationBufferMemory)，支持本地 JSON 会话持久化。
│   └── db_chat_memory.py         # 定义 DbChatMemory (继承 BaseChatMessageHistory)，用于数据库后端的聊天记录 (依赖 ChatService)。
│
├── models/                       # 数据模型 (Pydantic)
│   ├── __init__.py               # 导出 get_chat_model, DeepSeekChatModel (旧路径, 现为 llms.deepseek_client.DeepSeekLLM), ChatResponse。
│   ├── llm.py                    # (旧版 LLM 封装, 大部分功能已移至 llms/deepseek_client.py。get_chat_model 函数仍在此处，根据配置返回不同 LLM 实例)
│   └── response.py               # 定义 ChatResponse Pydantic 模型，用于 API 响应。
│
├── prompts/                      # 提示模板
│   ├── __init__.py               # 导出各种聊天提示模板。
│   └── chat_prompts.py           # 定义多个 ChatPromptTemplate 实例 (如 STRUCTURED_CHAT_AGENT_PROMPT)。
│
├── services/                     # 服务组件 (langgraphchat 模块内部)
│   └── __init__.py               # 目前 langgraphchat/services/ 目录为空。核心的 ChatService 位于 backend/app/services/chat_service.py。
│
├── tools/                        # LangGraph 工具定义和实现
│   ├── __init__.py               # 导出 flow_tools (工具列表)。
│   ├── definitions.py            # 定义工具相关的 Pydantic 模型 (NodeParams, ToolResult 等) 和示例性的 LangChain/DeepSeek 工具定义。
│   └── flow_tools.py             # 实现具体的流程图操作工具函数 (如 create_node_tool_func) 和对应的 LangChain StructuredTool 对象。工具通过 current_flow_id_var 获取流程上下文。
│
├── utils/                        # 通用工具函数
│   ├── __init__.py               # (通常为空或导出主要工具)
│   ├── context_collector.py      # 定义 ContextCollector，用于收集系统和流程图上下文信息。
│   ├── logging.py                # 配置日志记录器 (目前仍有较多 Langchain 相关配置)。
│   └── translator.py             # 定义 Translator 类，使用 LLM 进行文本翻译。
│
├── agents/                       # (目录存在，但目前为空)
├── callbacks/                    # (目录存在，但目前为空)
├── document_loaders/             # (目录存在，但目前为空)
├── output_parsers/               # (目录存在，但目前为空)
├── retrievers/                   # 检索器实现
│   ├── __init__.py               # (空)
│   └── embedding_retriever.py    # 定义 EmbeddingRetriever (继承 BaseRetriever)，使用 DatabaseEmbeddingService 进行异步文档检索。
│
├── vectorstore/                  # (目录存在，但目前为空)
└── sessions/                     # 本地会话存储目录 (如果启用 EnhancedConversationMemory 持久化)
    └── [session_id]/             # 包含具体会话的 JSON 文件
        └── ...
```

## 文件/模块详解及注意点

### `__init__.py`

- **作用**: 模块的入口点，通常用于导出公共接口或设置模块级别的属性。
- **注意**: 目前主要定义 `__version__`。

### `context.py`

- **作用**: 定义 `current_flow_id_var` (一个 `contextvars.ContextVar`)。
- **注意**: 这个变量用于在异步任务和不同模块间安全地传递当前正在操作的流程图 ID，尤其在工具执行时。确保在调用依赖此上下文的函数 (如 `flow_tools` 中的工具) 前正确设置此变量。

### `api/`

- `chat_router.py`:
  - **作用**: 定义 `/langgraphchat` 前缀下的 FastAPI 路由，如 `/message` (处理聊天请求), `/conversations` (列出对话), `/conversations/{conversation_id}` (删除对话)。
  - **依赖**: 严重依赖 `backend.langgraphchat.services.chat_service.ChatService` (目前缺失)。如果 `ChatService` 未实现或不可用，这些 API 端点将无法正常工作。
  - **数据模型**: 使用 Pydantic 模型 `ChatRequest` 和 `ChatResponse` (来自 `models/response.py`)。
  - **认证**: 集成了用户认证 (`optional_current_user`, `get_current_user`)。

### `adapters/`

- `db_memory_adapter.py`:
  - **作用**: 提供了 `DatabaseMemoryAdapter` 类，包含 `sync_to_database` 和 `sync_from_database` 静态方法，用于在 `EnhancedConversationMemory` 和 SQLAlchemy 的 `Chat` 模型之间同步聊天记录。
  - **注意**: 这是连接内存中对话状态和持久化数据库存储的桥梁，但其有效性依赖于数据库模型的正确性和 `ChatService` (间接)。

### `embeddings/`

- `config.py`: 定义 `SearchConfig`，允许通过环境变量配置搜索参数。
- `semantic_search.py`: `search_by_text` 函数现在是 `DatabaseEmbeddingService` 的客户端，将实际搜索逻辑委托给该服务。
- `node_search.py`:
  - **作用**: `search_nodes` 函数用于在本地 XML 节点数据库 (`/workspace/database/node_database`) 或通过 `NodeTemplateService` 进行关键词搜索。
  - **缓存**: 使用 `_node_cache` 缓存加载的节点定义。
  - **回退机制**: 优先从服务加载，失败则从文件系统加载。
  - **搜索逻辑**: 基于关键词匹配，而非语义相似度。
- `utils.py`: 提供文本处理和结果格式化的简单工具。

### `graph/`

- `agent_state.py`:
  - **作用**: 定义 `AgentState` TypedDict，这是 LangGraph 状态图的核心数据结构。它包含 `input`, `messages` (用于累积对话历史和工具交互), `flow_context`, 和 `current_flow_id`。
  - **关键**: `messages` 字段使用 `Annotated[List[BaseMessage], operator.add]` 来确保消息是追加的，这对于 LangGraph 的正确运行至关重要。
- `workflow_graph.py`:
  - **核心实现**: 这是 LangGraph 对话流程的核心。`compile_workflow_graph` 函数构建并编译一个 `StateGraph`。
  - **节点**:
    - `agent_node`: 调用 LLM (绑定了工具) 来决定下一步，并处理 LLM 的响应 (包括可能的 JSON 格式的 "final_answer")。
    - `tool_node`: 使用 LangGraph 的 `ToolNode` 来执行 Agent 请求的工具。
  - **边**:
    - `should_continue` (条件边): 根据 `agent_node` 的输出 (是否有 `tool_calls`) 决定是路由到 `tool_node` 还是 `END`。
    - 从 `tool_node` 回到 `agent_node` 的固定边。
  - **依赖**: `STRUCTURED_CHAT_AGENT_PROMPT` (用于构建系统提示), `flow_tools` (工具列表), 以及注入的 `BaseChatModel`。
  - **上下文传递**: `agent_node` 会将 `AgentState` 中的 `flow_context` 注入到给 LLM 的系统提示中。
  - **注意**: 这个文件是从 Langchain 迁移到 LangGraph 的关键，其正确性直接影响整个聊天功能。

### `llms/` (之前在 `models/`)

- `deepseek_client.py`:
  - **作用**: 定义 `DeepSeekLLM` 类，作为与 DeepSeek API (或其他 OpenAI 兼容 API) 交互的 LangChain `BaseChatModel` 封装。
  - **功能**: 处理 API 认证、请求参数、重试、流式响应、同步/异步调用。
  - **配置**: 从 `backend.langgraphchat.config.settings` 和环境变量加载配置。
  - **注意**: API 密钥管理和 Base URL 配置是正确运行的关键。包含一些复杂的配置加载逻辑，包括从 `.env` 文件。

### `memory/`

- `conversation_memory.py`:
  - **作用**: 定义 `EnhancedConversationMemory` (继承 `ConversationBufferMemory`)，增加了会话保存到本地 JSON 文件和从文件加载的功能。
  - **持久化**: 如果 `APP_CONFIG.PERSIST_SESSIONS` 为 `True`，会话将保存在 `APP_CONFIG.SESSIONS_DB_PATH` 指定的目录下。
  - `create_memory` 是一个工厂函数，方便创建或加载记忆实例。
- `db_chat_memory.py`:
  - **作用**: 定义 `DbChatMemory`，旨在将聊天记录存储在数据库中。它实现了 `BaseChatMessageHistory`。
  - **依赖**: 依赖于 `backend.app.services.chat_service.ChatService` (目前缺失) 来进行实际的数据库操作。
  - **注意**: 该组件目前可能无法完全工作，直到其依赖的 `ChatService` 被实现。

### `models/`

- `llm.py`:
  - **作用**: 包含 `get_chat_model()` 函数，这是一个工厂函数，根据配置 (如 `LLM_PROVIDER`) 返回不同类型的聊天模型实例 (如 `DeepSeekChatModel`, `AzureChatOpenAI`, `ChatZhipuAI`)。
  - **旧代码**: `DeepSeekChatModel` 类的旧定义也在此文件中，但项目似乎倾向于使用 `llms/deepseek_client.py` 中的版本。应注意版本统一性。
- `response.py`: 定义 `ChatResponse` Pydantic 模型，用于 API 的标准聊天响应。

### `prompts/`

- `chat_prompts.py`:
  - **作用**: 定义了多个 `ChatPromptTemplate` 实例，用于不同的聊天场景和 Agent 类型。
  - **关键模板**: `STRUCTURED_CHAT_AGENT_PROMPT` 是为 LangGraph Agent 设计的，包含了 `tools`, `tool_names`, `flow_context`, `chat_history`, `input`, `agent_scratchpad` 等占位符，并指导 LLM 如何使用 JSON 格式进行工具调用或最终回答。
  - **注意**: 这些提示是指导 LLM 行为的核心，其质量直接影响 Agent 的表现。

### `services/` (模块: `backend.langgraphchat.services`)

- `__init__.py`: 当前 `backend/langgraphchat/services/` 目录为空。
- **核心 `ChatService` 位置**: 项目核心的聊天服务逻辑由位于 `backend/app/services/chat_service.py` 的 `ChatService` 类提供。此类负责：
  - 管理和实例化 LLM (如 DeepSeek, Gemini)。
  - 编译和缓存 LangGraph 工作流 (`compiled_workflow_graph` 属性)，该工作流定义在 `backend.langgraphchat.graph.workflow_graph.py`。
  - 提供对数据库中 `Chat` 模型的 CRUD 操作。
  - 是 FastAPI 路由 (`api/chat_router.py`) 和数据库记忆组件 (`memory/db_chat_memory.py`) 的主要依赖。
- **注意**: `langgraphchat` 模块内的代码如果需要聊天核心服务，应依赖 `backend.app.services.chat_service.ChatService`。

### `tools/`

- `definitions.py`: 提供工具参数的 Pydantic 模型和工具类型枚举。包含一些 LangChain 和 DeepSeek 工具定义的**示例结构**，实际工具在 `flow_tools.py` 中实现。
- `flow_tools.py`:
  - **核心工具实现**: 包含与流程图交互的实际工具函数 (如 `create_node_tool_func`, `connect_nodes_tool_func`, `get_flow_info_tool_func`, `retrieve_context_func`)。
  - **LangChain 兼容**: 将这些函数包装成 LangChain `StructuredTool` 对象，并提供了相应的 Pydantic 输入 Schema。
  - **`flow_tools` 列表**: 最终导出一个 `flow_tools` 列表，供 LangGraph Agent 使用。
  - **上下文依赖**: 工具函数通过 `current_flow_id_var` 上下文变量获取当前流程图 ID。
  - **数据库交互**: 依赖 `FlowService` (来自 `backend.app.services.flow_service`) 进行数据库操作。
  - **异步函数**: 也包含一些异步版本的工具函数 (如 `generate_node_properties_async`)，它们通常接受注入的 LLM 客户端。
  - **注意**: 确保 `current_flow_id_var` 在调用这些工具前被正确设置。工具的健壮性依赖于下游服务 (如 `FlowService`)。

### `utils/`

- `context_collector.py`: `ContextCollector` 类用于收集系统信息和当前活动流程图的详细信息 (通过 `FlowService`)，为 LLM 提供上下文。
- `logging.py`:
  - **作用**: 配置日志系统。
  - **Langchain 痕迹**: 当前实现（如记录器名称、配置项）仍然基于 Langchain。在完全迁移到 LangGraph 后，可能需要更新此模块以更好地匹配 LangGraph 的实践。
  - **依赖**: `backend.config`。
- `translator.py`: `Translator` 类使用配置的 LLM (通过 `models.llm.get_chat_model`) 进行文本翻译。

### `retrievers/`

- `embedding_retriever.py`:
  - **作用**: 定义 `EmbeddingRetriever` (继承 `BaseRetriever`)。
  - **异步检索**: 主要通过 `_aget_relevant_documents` 方法，使用注入的 `DatabaseEmbeddingService` 实例进行异步相似性搜索。
  - **依赖**: `DatabaseEmbeddingService` (来自 `database.embedding.service`)。

## 使用方法 (基于当前结构和 LangGraph)

核心交互将通过 `workflow_graph.compile_workflow_graph()` 创建的 LangGraph 实例进行。

```python
# (示意代码，实际实现可能在 ChatService 中)
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM # 或者通过 models.llm.get_chat_model()
from backend.langgraphchat.tools.flow_tools import flow_tools # 工具列表
from backend.langgraphchat.context import current_flow_id_var

# 1. 初始化 LLM
# llm = DeepSeekLLM(openai_api_key="your_key", model_name="deepseek-chat", ...)
# 或者
# from backend.langgraphchat.models.llm import get_chat_model
# llm = get_chat_model()


# 2. 编译 LangGraph 工作流
# compiled_workflow = compile_workflow_graph(llm=llm, custom_tools=flow_tools)

# 3. 设置当前流程图 ID 上下文
# flow_id = "some_active_flow_id"
# token = current_flow_id_var.set(flow_id) # 保存 token 以便后续重置

# 4. 准备 AgentState 输入
# initial_state = {
#     "input": "用户最初的请求，例如：创建一个名为'开始处理'的开始节点",
#     "messages": [], # 通常初始为空，或包含一个 HumanMessage
#     "flow_context": {"name": "当前流程图名称", "nodes": [], ...}, # 从 ContextCollector 获取
#     "current_flow_id": flow_id
# }

# 5. 调用工作流 (异步)
# async def run_chat():
#     async for event in compiled_workflow.astream_events(initial_state, version="v1"):
#         kind = event["event"]
#         if kind == "on_chat_model_stream":
#             content = event["data"]["chunk"].content
#             if content:
#                 print(content, end="")
#         elif kind == "on_tool_end":
#             print(f"Tool {event['name']} ended with output: {event['data'].get('output')}")
#     # 最终结果可以在 state 中找到，通常是 messages 列表的最后一个 AIMessage
#     # final_state = await compiled_workflow.ainvoke(initial_state)
#     # print(f"Final response: {final_state['messages'][-1].content}")


# 6. 重置上下文变量
# current_flow_id_var.reset(token)
```

## 主要依赖和缺失部分

- **`ChatService` (`backend/app/services/chat_service.py`)**: **已找到并部分实现**。此类是核心，负责 LLM 管理、LangGraph 工作流的编译与调用、以及聊天记录的数据库操作。重构计划应围绕此类进行扩展，以支持流式处理和更复杂的 Agent 交互。
  - **待增强功能**: 需要实现更完善的 LangGraph 调用逻辑 (特别是流式处理 `astream_events`)、SSE 事件封装、以及与编辑/回滚功能相关的状态管理。
  - **LLM 提供商统一**: `ChatService._get_active_llm()` 与 `models/llm.py::get_chat_model()` 在支持的 LLM 上有差异，建议统一。
- **`FlowService` (`backend.app.services.flow_service`)**: 外部依赖，被 `ContextCollector` 和 `flow_tools` 用于获取和修改流程图数据。其可用性和正确性至关重要。
- **`DatabaseEmbeddingService` (`database.embedding.service`)**: 外部依赖，被 `semantic_search.py` 和 `embedding_retriever.py` 用于语义搜索。
- **配置 (`backend.config`, `backend.langgraphchat.config`)**: 正确配置 API 密钥、模型名称、数据库路径等对系统运行至关重要。

## 开发与迁移说明

- 项目正在从 Langchain 向 LangGraph 迁移。这意味着部分代码（如 `utils/logging.py`，以及一些旧的 Langchain Agent 相关提示或工具定义思路）可能尚未完全与 LangGraph 的最佳实践对齐。
- 异步编程是核心：LangGraph、LLM 调用和许多工具函数都设计为异步，需要在使用时注意 `async/await`。
- 上下文管理 (`current_flow_id_var`) 对工具的正确执行非常重要。
- 核心的 `ChatService` (在 `backend/app/services/chat_service.py`) 是进一步开发和集成 LangGraph 功能的中心。

要完整运行此模块并实现重构计划，主要任务是增强现有的 `ChatService` 以完全支持 LangGraph 的流式 Agentic 交互，并确保所有外部服务依赖和配置都已就绪。
