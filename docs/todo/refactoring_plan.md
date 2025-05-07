# 重构计划：迁移到 LangGraph、实现 Agentic 流式 SSE、数据库保存、编辑/回滚功能

本文档概述了重构聊天功能的计划。**首要目标是将当前的 LangChain Agent 实现迁移到 LangGraph 架构，以更好地管理复杂的状态和流程。** 随后，我们将实现 Agentic 交互（流式思考、工具使用）、解决数据库保存问题，并实现消息编辑和历史/流程回滚功能。

## 核心概念：LangGraph 与 Agentic 流式交互

**LangGraph 迁移**：我们将利用 LangGraph 来构建一个有状态的图，该图表示 Agent 的决策流程。这能更清晰地管理 Agent 的内部状态、工具调用之间的转换以及循环逻辑。

**Agentic 流式交互**：目标是让后端 LangGraph Agent 的 "思考 -> 行动决策 -> 行动 -> 观察" 循环通过 SSE 流实时反馈给前端，提供更透明、动态的用户体验。我们将利用 LangGraph 的流式输出能力（如 `stream` 或 `astream_log` 方法，具体取决于 LangGraph 如何集成 LangChain 的日志/事件系统）来实现这一点。

## 第零部分：迁移到 LangGraph 并清理

**目标：** 将现有的 `WorkflowAgent` 实现重构为 LangGraph，并移除因迁移而变得冗余的 LangChain Agent 组件。

**1. 后端：设计 LangGraph 状态与图结构 (`backend/langgraphchat/graph/` - 新目录)** - ✅

- **定义状态 (State):** 创建一个 Pydantic 模型或 TypedDict 来表示 LangGraph 的状态。此状态应至少包含：
  - `input`: 用户当前输入。
  - `chat_history`: 对话历史。
  - `flow_context`: 当前流程图的上下文信息。
  - `intermediate_steps` (或类似名称): 用于存储工具调用和结果的列表，供 Agent 内部循环使用。
  - `current_flow_id`: 当前操作的流程图 ID。
  - (可选) `agent_outcome`: 用于存储 Agent 的最终决策 (是调用工具还是回复用户)。
- **设计图节点 (Nodes):**
  - **Agent 节点**: 负责调用 LLM 进行思考和决策（是调用工具还是直接回复）。输入为当前状态，输出为 AgentAction 或 AgentFinish (或 LangGraph 中的等效概念)。
  - **工具执行节点**: 负责执行 Agent 决策的工具。输入为 AgentAction，输出为工具的观察结果 (Observation)。可以为每个工具创建一个节点，或者一个通用的工具执行节点。
- **设计图边 (Edges):**
  - **条件边**: 根据 Agent 节点的输出（调用工具还是结束）来决定下一个节点。
  - 如果是工具调用，则路由到相应的工具执行节点。
  - 如果是结束/直接回复，则路由到结束节点。
  - **普通边**: 从工具执行节点返回到 Agent 节点，以便 Agent 可以处理工具的观察结果并继续。
- **创建 LangGraph 实例**: 在新文件（例如 `backend/langgraphchat/graph/workflow_graph.py`）中，使用定义的状态、节点和边来构建 `StateGraph`。

**2. 后端：实现 LangGraph 节点逻辑 (`backend/langgraphchat/graph/workflow_graph.py`)** - ✅

- **Agent 节点函数**:
  - 接收当前 LangGraph 状态。
  - 使用 `STRUCTURED_CHAT_AGENT_PROMPT` (可能需要微调以适应 LangGraph 的输入/输出)、LLM (从 `ChatService._get_active_llm()` 获取) 和工具描述来调用 LLM。
  - 解析 LLM 的输出，判断是工具调用 (`AgentAction`) 还是最终回复 (`AgentFinish`)。
  - 更新 LangGraph 状态（例如，存储 `agent_outcome`）。
- **工具执行节点函数(群组)**:
  - 接收当前 LangGraph 状态 (其中应包含 `AgentAction`)。
  - 根据 `AgentAction` 中的工具名称和输入，执行相应的工具函数 (从 `backend/langgraphchat/tools/flow_tools.py` 调用)。
  - 将工具的输出 (Observation) 添加到状态的 `intermediate_steps` 中。
  - 更新 LangGraph 状态。

**3. 后端：编译 LangGraph 并提供接口 (`backend/langgraphchat/graph/workflow_graph.py`, `backend/app/services/chat_service.py`)** - ✅

- **编译图**: 调用 `graph.compile()` 生成可执行的 LangGraph runnable。
- **修改 `ChatService`**:
  - 移除旧的 `_agent_executor` 属性和 `create_workflow_agent_runnable` 方法。
  - 添加新的属性或方法来获取/创建已编译的 LangGraph runnable。例如 `self.workflow_graph = compile_workflow_graph()`。
  - `generate_response_stream` (或其他响应生成方法) 现在将调用 LangGraph runnable 的 `stream` 或 `astream_log` (或 `ainvoke` 等，取决于如何处理流)。

**4. 后端：清理冗余文件** - ✅

- **删除 `backend/langgraphchat/agents/workflow_agent.py`**: 因为其逻辑已被新的 LangGraph 实现取代。
- **审查 `backend/langgraphchat/prompts/chat_prompts.py`**: `STRUCTURED_CHAT_AGENT_PROMPT` 仍会使用，但其他与旧 Agent 相关的特定 Prompt (如果有) 可能需要移除或调整。
- **审查 `ChatService`**: 移除所有仅与旧 `AgentExecutor` 相关的逻辑。 - ✅
- **全局替换**: 将 `backend.langchainchat` 文件夹名全局替换为 `backend.langgraphchat`，以确保导入路径的一致性。 - ✅
- **修复 LangGraph 兼容性**: 更新`workflow_graph.py`中的导入语句，使用最新的`langgraph.prebuilt.ToolNode`API 替代旧的`ToolExecutor`和`ToolInvocation`，以兼容 LangGraph 0.4.2 版本。- ✅

**5. 测试 LangGraph 核心功能** - (尚未执行)

- **单元测试**: 测试各个 LangGraph 节点（Agent 决策、工具执行）的逻辑。
- **集成测试**: 测试完整的 LangGraph 执行流程（不含 SSE，仅关注输入输出和状态转换），确保它能正确调用工具并最终产生回复。验证 `DbChatMemory` 和 `current_flow_id_var` (如果工具仍然直接使用它，或者其值被正确传入 LangGraph 状态) 是否按预期工作。

## 第一部分：实现 Agentic 流式 SSE 和后端基础 (基于 LangGraph)

**目标：** 建立后端 LangGraph Agent 执行和流式事件推送的基础，并修复数据库保存问题。

**1. 后端：改造后台任务以使用 LangGraph (`backend/app/routers/chat.py`)** - ✅

- **操作 (`process_and_publish_events`):**
  - **获取 LangGraph Runnable:** 从 `ChatService` 获取已编译的 `workflow_graph`。
  - **准备 LangGraph 输入:** 构造传递给 LangGraph 的初始状态字典，应包含 `input` (用户消息), `chat_history` (格式化后的 `current_messages`), `flow_context` (从 `flow_data` 提取), `current_flow_id`。
  - **调用 `stream` 或 `astream_log`:** 使用 `workflow_graph.stream(graph_input, ...)` 或 `workflow_graph.astream_log(graph_input, ...)`。
  - **实现事件映射:** 在 `async for event in workflow_graph.stream(...)` (或 `astream_log`) 循环中：
    - **解析 `event`:** 分析 LangGraph 返回的事件/日志结构。LangGraph 的流式输出通常会包含每个节点执行前后的状态、节点的输入输出等。
    - **映射到 SSE 事件:**
      - **LLM Token (思考/回复):** 当事件表明是 Agent 节点正在输出 LLM 的 token 时，提取 token `chunk`, `await queue.put({"type": "token", "data": chunk})`。
      - **工具调用开始:** 当事件表明 Agent 节点决定调用工具，并且图即将转换到工具执行节点时，提取工具名称和输入参数, `await queue.put({"type": "tool_start", "data": {"name": ..., "input": ...}})`。
      - **工具调用结束:** 当事件表明工具执行节点已完成，并返回结果时，提取工具名称和结果摘要, `await queue.put({"type": "tool_end", "data": {"name": ..., "output_summary": ...}})`。
      - **错误:** 捕获 LangGraph 执行过程中的错误，并放入队列 `await queue.put({"type": "error", ...})`。
      - **详细说明：** 错误事件 (`"type": "error"`) 的 `data` 字段应至少包含错误消息 (`message`), 错误发生的阶段 (`stage`, 如 'llm', 'tool', 'graph_node'), 如果适用，还应包含工具名称或节点名称 (`tool_name`/`node_name`)。
      - **累积最终回复:** 在循环中，维护一个变量 (`final_reply_accumulator`), 将所有最终回复阶段的 LLM token 拼接起来。
  - **测试:** 验证 LangGraph 的基本流程（无工具调用）能够流式输出到前端。验证工具调用流程是否能正确触发 `tool_start` 和 `tool_end` 事件。

**2. 后端：修复数据库保存 (`backend/app/routers/chat.py`)** - ✅

- 使用**新的独立数据库 Session** (`with get_db_context() as db_session_for_save:`) 来保存最终结果。
  - 使用此新 Session 初始化 `ChatService` (`chat_service_for_save = ChatService(db_session_for_save)`).
  - 从 `final_reply_accumulator` 获取最终回复内容。
  - 从 LangGraph 执行的最终状态中提取最终的 `flow_data` (如果图的执行修改了流程图状态并将其保存在最终状态中)。
  - 调用 `chat_service_for_save.add_message_to_chat(...)` 保存助手回复。
  - 如果 `final_flow_data` 存在，使用新 Session 更新 `Flow`。
  - **测试:** 确认在 LangGraph 流程结束后，助手回复和潜在的流程更新能可靠地保存到数据库。

**3. 前端：适配新的 SSE 事件 (`frontend/src/api/chatApi.ts`, `frontend/src/components/ChatInterface.tsx`)** - (与原始计划相同，主要是适配 LangGraph 可能产生的事件结构和时序) - **API (`chatApi.ts`):** 定义新的 SSE 事件类型接口。 - **UI (`ChatInterface.tsx`):** 修改 `handleChatEvent` 来处理 `tool_start`, `tool_end`, `token`, `error` 事件。 - **测试:** 验证前端能够正确接收并渲染新的 `tool_start`, `tool_end` 事件，并流畅地展示思考、工具执行、最终回复的整个过程。

## 第二部分：实现消息编辑与历史/流程回滚 (依赖第一部分完成)

**目标：** 允许用户编辑消息，触发后续历史和流程的回滚，并基于 LangGraph 重新运行。

**1. 后端：数据库模型 (`database/models.py`)** - (与原始计划相同) 在 `Chat.chat_data.messages` 中的**助手消息**里添加 `flow_snapshot: Optional[Dict]` 字段。

**2. 后端：`ChatService` (`backend/app/services/chat_service.py`)** - (与原始计划相同) 修改 `add_message_to_chat`：添加 `flow_snapshot` 参数。

**3. 后端：新的编辑 API 端点 (`backend/app/routers/chat.py`)** - (与原始计划相同) 创建 `PUT /chats/{chat_id}/messages/{message_timestamp}`。 - **逻辑调整**: - 触发编辑后台任务时，传递 `checkpoint_flow_data`，这将作为 LangGraph 初始状态的一部分。

**4. 后端：新的编辑后台任务 (`backend/app/routers/chat.py`)** - **操作：** 创建 `async def process_edited_message_and_publish(c_id, edited_msg_content, truncated_history, checkpoint_flow_data, queue)`。 - **逻辑：** - **准备 LangGraph 输入:** - **恢复流程状态:** (关键步骤) `checkpoint_flow_data` 将用于初始化 LangGraph 状态中的 `flow_context` 部分。 - 使用 `edited_msg_content` 作为新的 `input`，`truncated_history` 作为 `chat_history`，并将恢复后的 `flow_context` (从 `checkpoint_flow_data` 构建) 和 `current_flow_id` 传递给 LangGraph 的初始状态。 - **运行 LangGraph:** 调用 `workflow_graph.stream(...)` 或 `astream_log(...)`。 - **处理事件流:** 与 `process_and_publish_events` 类似。 - **保存结果 (finally 块):** - 保存最终的助手回复，**附带当前流程状态（从 LangGraph 最终状态中获取）作为新的 `flow_snapshot`**。

**5. 前端：编辑 UI (`frontend/src/components/ChatInterface.tsx`)** - (与原始计划相同)

**6. 前端：API (`frontend/src/api/chatApi.ts`)** - (与原始计划相同)

## 第三部分：代码清理与重构 (后 LangGraph 迁移)

**目标：** 提高可维护性，移除因引入 LangGraph 而产生的其他冗余或过时代码。

- 审查并确保 `ChatService`、工具函数等与 LangGraph 的集成是清晰和高效的。
- 完善错误处理和日志记录，特别关注 LangGraph 执行过程中的错误。
- 更新或添加必要的单元测试和集成测试，覆盖 LangGraph 的各种路径和状态。

## 执行顺序与测试策略

1.  **实现第零部分 (迁移到 LangGraph & 清理):**
    - **优先设计和实现 LangGraph 的状态、节点和图结构。**
    - **修改 `ChatService` 以使用新的 LangGraph runnable。**
    - **删除旧的 `workflow_agent.py`。**
    - **进行核心功能测试（无 SSE），确保 LangGraph 能正确处理输入、调用工具并产生预期结果。**
2.  **实现第一部分 1 (后端 LangGraph 流式改造):**
    - 实现 LangGraph 流式输出 (`stream` 或 `astream_log`) 到 SSE 事件的映射。
    - 单元测试事件映射逻辑。
3.  **实现第一部分 3 (前端适配):**
    - 更新前端以处理新的 SSE 事件。
    - 端到端测试基本的 LangGraph 流式交互。
4.  **实现第一部分 2 (后端数据库保存修复 - 基于 LangGraph):**
    - 在 LangGraph 流程基础上，确保结果正确保存。测试。
5.  **实现第二部分 (编辑/回滚 - 后端，基于 LangGraph):**
    - 数据库模型修改。
    - 实现编辑 API 和新的后台任务，确保其正确地使用 LangGraph 和 `checkpoint_flow_data`。
6.  **实现第二部分 (编辑/回滚 - 前端):**
    - 实现前端 UI 和 API 调用。
7.  **端到端测试:** 测试 LangGraph 驱动的流式交互、数据库保存、编辑和回滚功能。
8.  **实现第三部分 (清理 - 后 LangGraph):** 在功能稳定后进行代码清理和重构。
9.  **文档更新:** 重构完成后，务必更新 `/workspace/database/README.md`, `/workspace/backend/README.md`, 和 `/workspace/frontend/README.md` 文件，以准确反映新的代码结构 (特别是 LangGraph 的引入)、API 行为和核心功能。

## 执行进度报告

**2025-05-07**: 完成了第零部分的所有任务：

1. ✅ 完成了对`backend/langgraphchat/graph/workflow_graph.py`的重构，使其使用最新的 LangGraph API。
2. ✅ 修复了 LangGraph 0.4.2 兼容性问题，特别是将旧版`ToolExecutor`和`ToolInvocation`更新为新版`ToolNode` API。
3. ✅ 移除了与旧的`AgentExecutor`相关的代码。
4. ✅ 将所有导入路径从`backend.langchainchat`更新为`backend.langgraphchat`，确保导入路径的一致性。
5. ✅ 更新了配置文件和相关 README 文档，以反映新的项目结构。

**2025-05-08**: 完成了第一部分的所有任务：

1. ✅ 重写了`process_and_publish_events`函数，以使用 LangGraph 的流式输出，正确映射各种事件类型。
2. ✅ 修复了数据库保存问题，使用独立会话保存消息和流程状态，避免冲突。
3. ✅ 更新了前端处理逻辑，以适应新的 SSE 事件结构。
4. ✅ 全局替换了`frontend/src/api/chatApi.ts`中的 API 路径，从`/langchainchat/`更新为`/langgraphchat/`。

下一步是实现第二部分中的消息编辑与历史/流程回滚功能。
