# 重构计划：SSE、数据库保存、编辑/回滚功能

本文档概述了重构聊天功能的计划，旨在解决当前问题并实现新功能，例如消息编辑和历史/流程回滚。

## 第一部分：修复现有问题并优化 SSE 连接

**目标：** 解决数据库保存不一致的问题，并为每个聊天实现稳定、持久的 SSE 连接。

**1. 后端：修复数据库保存问题 (`backend/app/routers/chat.py`)**

- **操作：** 修改 `process_and_publish_events` 后台任务。在其 `finally` 块中，当保存最终的助手回复 (`final_content_to_save`) 时：
  - 为此保存操作获取一个**新的、独立的**数据库 Session：`db_session_for_save = SessionLocal()`。
  - 使用此 Session 初始化一个**新的** `ChatService` 实例：`chat_service_for_save = ChatService(db_session_for_save)`。
  - 使用这个新的 Service 实例调用 `add_message_to_chat`。
  - 确保 `db_session_for_save` 在其自己的 `try...finally` 块中被关闭。
- **清理：** 确保在任务开始时创建的原始 Session (`db_session_bg`) 仍然在主 `finally` 块的末尾被关闭。
- **测试：** 验证此更改后，助手回复现在能够一致地保存到数据库中。

**2. 前端：实现持久化 SSE 连接 (`frontend/src/components/ChatInterface.tsx`, `frontend/src/api/chatApi.ts`)**

- **API (`chatApi.ts`):**
  - 创建一个新函数 `connectToChatEvents(chatId, onEvent, onError, onClose)`，它建立 `GET /chats/{chatId}/events` 的 EventSource 连接并返回一个 `close` 函数。它**不**发送任何 POST 请求。
  - 创建一个新函数 `triggerChatProcessing(chatId, content, role)`，它发送 `POST /chats/{chatId}/messages` 请求并返回 `void`（发送后不管）。
  - 移除旧的 `sendMessage` 函数。
- **UI (`ChatInterface.tsx`):**
  - 使用一个 `useEffect` 钩子，以 `activeChatId` 作为依赖项，来管理 SSE 连接的生命周期：
    - 当 `activeChatId` 更改且有效时：关闭任何现有连接（使用 `closeEventSourceRef`），调用 `connectToChatEvents` 建立新连接，将返回的 `close` 函数存储在 `closeEventSourceRef` 中。
    - `useEffect` 的清理函数应调用存储的 `close` 函数。
  - 修改 `handleSendMessage`：移除关闭连接的逻辑。仅在本地添加用户消息并调用 `triggerChatProcessing`。
  - 确保 `handleChatClose`（由连接清理调用）清除 `streamingAssistantMsgIdRef`。
- **测试：** 验证基本的聊天功能（流式文本、工具调用）能够正确工作且没有消息丢失，尤其是在快速发送消息时。

## 第二部分：实现消息编辑与历史/流程回滚

**目标：** 允许用户编辑他们之前的消息，触发后续历史记录的回滚，并可能回滚相关的流程图状态。

**1. 后端：数据库模型 (`database/models.py`)**

- **操作 (选项 1: 快照):** 修改 `Chat.chat_data` 结构。在 `messages` 数组中的助手消息里添加一个可选的 `flow_snapshot: Optional[Dict]` 字段，用于存储当时相关的流程图状态（节点、连接等）。
- **操作 (选项 2: 版本控制 - 更复杂):** 引入 `FlowVersion` 表。在消息中存储版本 ID。需要更重大的模式更改。（为简单起见，先从选项 1 开始）。

**2. 后端：`ChatService` (`backend/app/services/chat_service.py`)**

- **修改 `add_message_to_chat`：** 添加可选的 `flow_snapshot` 参数。如果提供了该参数并且 `role=='assistant'`，则将其存储在消息字典中。
- **修改 `process_chat_message`：** 在潜在的流程更新（`chain_output_obj.nodes/connections` 存在）后保存助手消息（摘要或错误）时，获取 _当前_ 的 `flow_data` 并将其作为 `flow_snapshot` 参数传递给 `add_message_to_chat`。

**3. 后端：新的编辑 API 端点 (`backend/app/routers/chat.py`)**

- **操作：** 创建 `PUT /chats/{chat_id}/messages/{message_timestamp}` 端点。
- **逻辑：** 1. 为此操作使用一个**新的数据库 Session**。 2. 通过 `message_timestamp` 找到目标用户消息。 3. **截断历史记录：** 移除目标消息之后的所有消息。更新目标消息的内容。**立即提交**此历史记录更改。 4. **查找检查点：** 定位到被编辑消息之前的、包含 `flow_snapshot` 的最后一条助手消息。将其用作回滚状态 (`checkpoint_flow_data`)。处理没有快照存在的情况（例如，使用初始状态或当前状态作为备用）。 5. **触发新的后台任务：** 启动一个新的任务 `process_edited_message_and_publish`，传递截断后的历史记录和 `checkpoint_flow_data`。 6. 返回 202 Accepted。

**4. 后端：新的后台任务 (`backend/app/routers/chat.py`)**

- **操作：** 创建 `async def process_edited_message_and_publish(...)`。
- **逻辑：** 类似于 `process_and_publish_events`，但是：
  - 接受截断后的历史记录和检查点流程数据作为输入。
  - **不再**保存（已经编辑过的）用户消息。
  - 将截断后的历史记录和检查点数据传递给 `WorkflowChain`（可能需要修改 `WorkflowChain` 的输入/逻辑）。
  - 处理生成的事件流或非流式响应。
  - 保存最终的助手回复**并附带一个新的 `flow_snapshot`**（使用一个**新的数据库 Session** 进行保存）。
  - 正确管理其自身的数据库 Session。

**5. 前端：编辑 UI (`frontend/src/components/ChatInterface.tsx`)**

- 为用户消息添加"编辑"按钮。
- 添加状态 `editingMessageTimestamp: string | null`。
- 实现 `handleStartEdit(timestamp, content)`：设置输入字段，设置 `editingMessageTimestamp`，更新 UI 以指示编辑模式。
- 实现 `handleConfirmEdit()`：调用 `chatApi.editMessage`，执行乐观 UI 更新（更新消息内容，移除后续消息），重置编辑状态，清除输入。
- 实现 `handleCancelEdit()`：重置编辑状态，清除输入。
- 修改 `handleKeyPress` 以处理编辑模式下的 Enter 键。

**6. 前端：API (`frontend/src/api/chatApi.ts`)**

- 添加 `editMessage(chatId, messageTimestamp, newContent)` 函数以发送 PUT 请求。

## 第三部分：代码清理与重构

**目标：** 提高代码可维护性并移除过时的部分。

- 移除旧的 `chatApi.sendMessage` 和相关的前端逻辑。
- 重构后端后台任务（`process_and_publish_events`, `process_edited_message_and_publish`）以将通用逻辑提取到辅助函数中（例如，处理 `WorkflowChainOutput`、将事件放入队列、使用会话管理保存最终回复）。
- 审查 `ChatService` 的状态性（可选）。
- 确保整个过程中一致且健壮的错误处理和日志记录。

## 执行顺序与测试策略

1.  **实现第一部分 1.1 (后端数据库修复):** 进行彻底测试以确认消息保存的可靠性。
2.  **实现第一部分 1.2 (前端 SSE):** 测试基本的聊天功能，重点关注流的完整性并防止消息丢失。
3.  **实现第二部分 (编辑/回滚 - 先后端):**
    - 实现后端数据库更改（快照）。
    - 实现后端 API 端点和新的后台任务。如果需要，直接通过 API 调用进行测试。
4.  **实现第二部分 (编辑/回滚 - 前端):**
    - 实现前端 UI 更改和 API 调用。
5.  **端到端测试:** 测试完整的编辑/回滚功能。
6.  **实现第三部分 (清理):** 一旦功能稳定，进行重构并移除不再使用的代码。
