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
**1. Backend: Fix Database Save Issue (`backend/app/routers/chat.py`)**
_ **Action:** Modify the `process_and_publish_events` background task. In the `finally` block, when saving the final assistant reply (`final_content_to_save`):
_ Obtain a **new, independent** database session specifically for this save operation: `db_session_for_save = SessionLocal()`.
_ Initialize a **new** `ChatService` instance with this session: `chat_service_for_save = ChatService(db_session_for_save)`.
_ Use this new service instance to call `add_message_to_chat`.
_ Ensure `db_session_for_save` is closed in its own `try...finally` block.
_ **Cleanup:** Ensure the original session (`db_session_bg`) created at the start of the task is still closed at the end of the main `finally` block. \* **Testing:** Verify that assistant replies are now consistently saved to the database after this change.

**2. Frontend: Implement Persistent SSE Connection (`frontend/src/components/ChatInterface.tsx`, `frontend/src/api/chatApi.ts`)**
_ **API (`chatApi.ts`):**
_ Create a new function `connectToChatEvents(chatId, onEvent, onError, onClose)` that establishes the `GET /chats/{chatId}/events` EventSource connection and returns a `close` function. It does _not_ send any POST request.
_ Create a new function `triggerChatProcessing(chatId, content, role)` that sends the `POST /chats/{chatId}/messages` request and returns `void` (fire-and-forget).
_ Remove the old `sendMessage` function.
_ **UI (`ChatInterface.tsx`):**
_ Use a `useEffect` hook with `activeChatId` as a dependency to manage the SSE connection lifecycle:
_ When `activeChatId` changes and is valid: Close any existing connection (using `closeEventSourceRef`), call `connectToChatEvents` to establish a new one, store the returned `close` function in `closeEventSourceRef`.
_ The `useEffect` cleanup function should call the stored `close` function.
_ Modify `handleSendMessage`: Remove logic for closing connections. Only add the user message locally and call `triggerChatProcessing`.
_ Ensure `handleChatClose` (called by the connection cleanup) clears `streamingAssistantMsgIdRef`. \* **Testing:** Verify basic chat (streaming text, tool calls) works correctly without message loss, especially when sending messages quickly.

## Part 2: Implement Message Editing & History/Flow Rollback

**Goal:** Allow users to edit their previous messages, triggering a rollback of subsequent history and potentially the associated flowchart state.

**1. Backend: Database Model (`database/models.py`)**
_ **Action (Option 1: Snapshot):** Modify `Chat.chat_data` structure. Add an optional `flow_snapshot: Optional[Dict]` field to assistant messages in the `messages` array to store relevant flowchart state (nodes, connections, etc.) at that point.
_ **Action (Option 2: Versioning - More Complex):** Introduce a `FlowVersion` table. Store version IDs in messages. Requires more significant schema changes. (Start with Option 1 for simplicity).

**2. Backend: `ChatService` (`backend/app/services/chat_service.py`)**
_ **Modify `add_message_to_chat`:** Add optional `flow_snapshot` parameter. If provided and `role=='assistant'`, store it within the message dictionary.
_ **Modify `process_chat_message`:** When saving an assistant message (summary or error) after a potential flow update (`chain_output_obj.nodes/connections` exist), fetch the _current_ `flow_data` and pass it as the `flow_snapshot` argument to `add_message_to_chat`.

**3. Backend: New Edit API Endpoint (`backend/app/routers/chat.py`)**
_ **Action:** Create `PUT /chats/{chat_id}/messages/{message_timestamp}` endpoint.
_ **Logic:** 1. Use a **new DB Session** for this operation. 2. Find the target user message by `message_timestamp`. 3. **Truncate History:** Remove all messages _after_ the target message. Update the target message's content. **Commit** this history change immediately. 4. **Find Checkpoint:** Locate the last assistant message _before_ the edited message that contains a `flow_snapshot`. Use this as the rollback state (`checkpoint_flow_data`). Handle cases where no snapshot exists (e.g., use initial state or current state as fallback). 5. **Trigger New Background Task:** Start a new task `process_edited_message_and_publish`, passing the truncated history and `checkpoint_flow_data`. 6. Return 202 Accepted.

**4. Backend: New Background Task (`backend/app/routers/chat.py`)**
_ **Action:** Create `async def process_edited_message_and_publish(...)`.
_ **Logic:** Similar to `process_and_publish_events`, but:
_ Takes truncated history and checkpoint flow data as input.
_ Does **not** save the (already edited) user message again.
_ Passes truncated history and checkpoint data to `WorkflowChain` (may require modifying `WorkflowChain` input/logic).
_ Handles the resulting event stream or non-stream response.
_ Saves the final assistant reply **with a new `flow_snapshot`** (using a **new DB Session** for the save).
_ Manages its own DB session(s) correctly.

**5. Frontend: Edit UI (`frontend/src/components/ChatInterface.tsx`)**
_ Add "Edit" button to user messages.
_ Add state `editingMessageTimestamp: string | null`.
_ Implement `handleStartEdit(timestamp, content)`: Set input field, set `editingMessageTimestamp`, update UI to indicate editing mode.
_ Implement `handleConfirmEdit()`: Call `chatApi.editMessage`, perform optimistic UI update (update message content, remove subsequent messages), reset editing state, clear input.
_ Implement `handleCancelEdit()`: Reset editing state, clear input.
_ Modify `handleKeyPress` for Enter key in editing mode.

**6. Frontend: API (`frontend/src/api/chatApi.ts`)** \* Add `editMessage(chatId, messageTimestamp, newContent)` function to send the PUT request.

## Part 3: Code Cleanup & Refactoring

**Goal:** Improve code maintainability and remove obsolete parts.

- Remove old `chatApi.sendMessage` and related frontend logic.
- Refactor backend background tasks (`process_and_publish_events`, `process_edited_message_and_publish`) to extract common logic into helper functions (e.g., processing `WorkflowChainOutput`, putting events to queue, saving final reply with session management).
- Review `ChatService` statefulness (optional).
- Ensure consistent and robust error handling and logging throughout.

## Execution Order & Testing Strategy

1.  **Implement Part 1.1 (Backend DB Fix):** Test thoroughly to confirm reliable message saving.
2.  **Implement Part 1.2 (Frontend SSE):** Test basic chat functionality, focusing on stream integrity and preventing lost messages.
3.  **Implement Part 2 (Edit/Rollback - Backend first):**
    - Implement backend DB changes (snapshots).
    - Implement backend API endpoint and new background task. Test via API calls directly if needed.
4.  **Implement Part 2 (Edit/Rollback - Frontend):**
    - Implement frontend UI changes and API call.
5.  **End-to-End Testing:** Test the complete edit/rollback feature.
6.  **Implement Part 3 (Cleanup):** Refactor and remove dead code once features are stable.
