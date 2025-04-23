# 重构计划：Agentic 流式 SSE、数据库保存、编辑/回滚功能

本文档概述了重构聊天功能的计划，旨在实现 Agentic 交互（流式思考、工具使用）、解决当前数据库保存问题，并实现消息编辑和历史/流程回滚功能。

## 核心概念：Agentic 流式交互

目标是让后端 Agent 的 "思考 -> 行动决策 -> 行动 -> 观察" 循环通过 SSE 流实时反馈给前端，提供更透明、动态的用户体验。我们将利用 LangChain 的 `AgentExecutor`（或类似的自定义 Runnable 结构）及其 `astream_log` 方法来实现这一点。

## 第一部分：实现 Agentic 流式 SSE 和后端基础

**目标：** 建立后端 Agent 执行和流式事件推送的基础，并修复数据库保存问题。

**1. 后端：引入 Agent Executor (`backend/app/services/chat_service.py`, 新文件 `backend/langchainchat/agents/workflow_agent.py`)**

- **操作 (`workflow_agent.py`):**
  - 创建一个新的 Agent Executor 或自定义 Runnable。参考 LangChain 的 ReAct Agent 或带有 Function Calling 的 Agent。
  - **Agent Prompt:** 设计包含系统提示、工具描述、历史记录、当前流程图上下文和用户输入的 Prompt 模板。
  - **Agent LLM:** 配置 Agent 使用的 LLM（例如，`self.llm` from `ChatService`）。
  - **Agent Tools:** 将 `ToolExecutor` 中的工具列表传递给 Agent。
  - **Agent 解析器:** 配置合适的输出解析器以处理 LLM 的思考、工具调用指令或最终答案。
  - **内存:** Agent 将依赖于外部传入的 `history`，而不是自己管理持久化内存。
- **操作 (`chat_service.py`):**
  - 在 `__init__` 中初始化这个新的 Agent Executor (`self.workflow_agent_executor`)，取代或补充现有的 `self.workflow_chain`。
  - 移除 `_initialize_workflow_chain` 和 `self.workflow_chain`（如果完全替换）。
- **考虑:** 是否还需要单独的 `RAGChain`，或者 RAG 功能可以通过工具集成到 Agent 中。

**2. 后端：改造后台任务以使用 Agent (`backend/app/routers/chat.py`)**

- **操作 (`process_and_publish_events`):**
  - **获取 Agent Executor:** 从 `chat_service_bg` 获取 `workflow_agent_executor`。
  - **准备 Agent 输入:** 构造传递给 Agent 的输入字典，应包含 `input` (用户消息), `chat_history` (格式化后的 `current_messages`), `flow_context` (从 `flow_data` 提取), 以及可能需要的 `flow_id`, `chat_id` (如果工具需要)。
  - **调用 `astream_log`:** 使用 `agent_executor.astream_log(agent_input, ...)` 替代 `chain.astream_events(...)`。
  - **实现事件映射:** 在 `async for log_entry in agent_executor.astream_log(...)` 循环中：
    - **解析 `log_entry`:** 分析 `log_entry` 的内容和路径 (`log_entry.ops`) 来识别不同的 Agent 步骤。
    - **映射到 SSE 事件:**
      - **LLM Token (思考/回复):** 当日志显示 LLM 正在输出时 (e.g., `op['path']` contains `/streamed_output_str/-` or similar)，提取 token `chunk`，`await queue.put({"type": "token", "data": chunk})`。
      - **工具调用开始:** 当日志显示 Agent 决定调用工具时 (e.g., `op['path']` ends with `/tool_calls/-`), 提取工具名称和输入参数，`await queue.put({"type": "tool_start", "data": {"name": ..., "input": ...}})`。
      - **工具调用结束:** 当日志显示工具执行完成时 (e.g., `op['path']` ends with `/tool_result`), 提取工具名称和结果摘要，`await queue.put({"type": "tool_end", "data": {"name": ..., "output_summary": ...}})`。
      - **错误:** 捕获 Agent 执行过程中的错误，并放入队列 `await queue.put({"type": "error", ...})`。
  - **累积最终回复:** 在循环中，维护一个变量 (`final_reply_accumulator`)，将所有最终回复阶段的 LLM token 拼接起来。
- **测试:** 验证 Agent 的基本流程（无工具调用）能够流式输出到前端。验证工具调用流程是否能正确触发 `tool_start` 和 `tool_end` 事件。

**3. 后端：修复数据库保存 (`backend/app/routers/chat.py`)**

- **操作 (`process_and_publish_events` 的 `finally` 块):**
  - 使用**新的独立数据库 Session** (`with get_db_context() as db_session_for_save:`) 来保存最终结果。
  - 使用此新 Session 初始化 `ChatService` (`chat_service_for_save = ChatService(db_session_for_save)`).
  - 从 `final_reply_accumulator` 获取最终回复内容。
  - 从 Agent 执行结果中提取最终的 `flow_data` (如果 Agent 修改了流程)。
  - 调用 `chat_service_for_save.add_message_to_chat(...)` 保存助手回复。
  - 如果 `final_flow_data` 存在，使用新 Session 更新 `Flow`。
- **测试:** 确认在 Agent 流程结束后，助手回复和潜在的流程更新能可靠地保存到数据库。

**4. 前端：适配新的 SSE 事件 (`frontend/src/api/chatApi.ts`, `frontend/src/components/ChatInterface.tsx`)**

- **API (`chatApi.ts`):**
  - 定义新的 SSE 事件类型接口，如 `ToolStartEvent`, `ToolEndEvent`。更新 `ChatEvent` 类型联合。
  - **(维持现状)** `connectToChatEvents` 和 `triggerChatProcessing` 的分离设计是好的，保持不变。旧的 `sendMessage` 应该已经被移除。
- **UI (`ChatInterface.tsx`):**
  - **(维持现状)** 使用 `useEffect` 管理 SSE 连接生命周期的逻辑是正确的。
  - **修改 `handleChatEvent`:**
    - 添加 `case "tool_start":` 处理逻辑：找到或创建一个表示该工具调用的消息项（可能需要新的 `messageId` 或标记），并将其状态设置为"加载中"，显示工具名称和输入。
    - 添加 `case "tool_end":` 处理逻辑：更新对应的工具消息项，显示结果摘要或完成状态。
    - 确保 `case "token":` 能正确处理思考和最终回复阶段的 token 流，将其追加到当前正在生成的助手消息中。
  - **UI 组件:** 可能需要改进 `ToolCallCard` 或引入新的渲染逻辑来更好地展示工具执行的中间状态和最终结果。
- **测试:** 验证前端能够正确接收并渲染新的 `tool_start`, `tool_end` 事件，并流畅地展示思考、工具执行、最终回复的整个过程。

## 第二部分：实现消息编辑与历史/流程回滚 (依赖第一部分完成)

**目标：** 允许用户编辑消息，触发后续历史和流程的回滚，并重新运行 Agent。

**1. 后端：数据库模型 (`database/models.py`)**

- **操作 (快照):** 在 `Chat.chat_data.messages` 中的**助手消息**里添加 `flow_snapshot: Optional[Dict]` 字段。

**2. 后端：`ChatService` (`backend/app/services/chat_service.py`)**

- **修改 `add_message_to_chat`：** 添加 `flow_snapshot` 参数，如果提供且 `role=='assistant'` 则保存。

**3. 后端：新的编辑 API 端点 (`backend/app/routers/chat.py`)**

- **操作：** 创建 `PUT /chats/{chat_id}/messages/{message_timestamp}`。
- **逻辑：**
  - 使用**新 Session**。
  - 找到目标用户消息并更新其内容。
  - **截断历史:** 移除目标消息时间戳之后的所有消息。**提交**更改。
  - **查找检查点:** 找到编辑点之前的、最新的包含 `flow_snapshot` 的助手消息。获取其 `flow_snapshot` 作为 `checkpoint_flow_data`。处理无快照的情况。
  - **触发编辑后台任务:** 启动 `process_edited_message_and_publish`，传递 `chat_id`，编辑后的 `message` (或仅内容)，截断后的历史 `truncated_history`，以及 `checkpoint_flow_data`。
  - 返回 202。

**4. 后端：新的编辑后台任务 (`backend/app/routers/chat.py`)**

- **操作：** 创建 `async def process_edited_message_and_publish(c_id, edited_msg_content, truncated_history, checkpoint_flow_data, queue)`。
- **逻辑：**
  - 获取 `ChatService`, `FlowService` 等 (使用 `get_db_context`)。
  - **准备 Agent 输入:** 使用 `edited_msg_content` 作为新的 `input`，`truncated_history` 作为 `chat_history`，并**确保将 `checkpoint_flow_data` 作为初始流程上下文**传递给 Agent（可能需要修改 Agent 输入结构或 Prompt）。
  - **运行 Agent:** 调用 `agent_executor.astream_log(...)`。
  - **处理事件流:** 与 `process_and_publish_events` 类似，解析日志，映射到 SSE 事件并放入队列。
  - **累积最终回复。**
  - **保存结果 (finally 块):**
    - 使用**新 Session**。
    - 保存最终的助手回复，**附带当前流程状态作为新的 `flow_snapshot`**。
    - 如果 Agent 执行修改了流程，保存更新后的 `Flow` 数据。

**5. 前端：编辑 UI (`frontend/src/components/ChatInterface.tsx`)**

- (与原始计划类似) 添加编辑按钮、编辑状态、确认/取消逻辑。
- `handleConfirmEdit` 调用 `chatApi.editMessage`，并执行乐观 UI 更新（修改消息，移除后续消息）。

**6. 前端：API (`frontend/src/api/chatApi.ts`)**

- 添加 `editMessage(chatId, messageTimestamp, newContent)`。

## 第三部分：代码清理与重构

**目标：** 提高可维护性，移除冗余代码。

- 移除旧的 `WorkflowChain`（如果完全被 Agent 取代）。
- 重构 `process_and_publish_events` 和 `process_edited_message_and_publish`，提取通用逻辑（如事件映射、最终结果累积、数据库保存）。
- 审查并确保 `ChatService`、`ToolExecutor` 等是无状态的或正确处理状态。
- 完善错误处理和日志记录。
- 更新或添加必要的单元测试和集成测试。

## 执行顺序与测试策略

1.  **实现第一部分 1 & 2 (后端 Agent 基础 & 改造后台任务):**
    - 优先实现无工具调用的 Agent 流式输出。
    - 添加工具调用和事件映射。
    - 单元测试 Agent 和事件映射逻辑。
2.  **实现第一部分 4 (前端适配):**
    - 更新前端以处理新的 SSE 事件。
    - 端到端测试基本的 Agent 流式交互。
3.  **实现第一部分 3 (后端数据库保存修复):**
    - 在 Agent 流程基础上，确保结果正确保存。测试。
4.  **实现第二部分 (编辑/回滚 - 后端):**
    - 数据库模型修改。
    - 实现编辑 API 和新的后台任务。使用 API 调用进行测试。
5.  **实现第二部分 (编辑/回滚 - 前端):**
    - 实现前端 UI 和 API 调用。
6.  **端到端测试:** 测试编辑和回滚功能。
7.  **实现第三部分 (清理):** 在功能稳定后进行代码清理和重构。

这个更新后的计划将 Agentic 流式交互作为核心，并在此基础上构建编辑/回滚功能，同时解决了数据库保存的问题。
