# LangGraph 工具与 Prompt 重构计划

本文档旨在记录对 LangGraph 工具实现和 Prompt 动态填充的分析、建议及后续修改计划，以提升系统的可维护性、LLM 交互的准确性以及实现更优的流式输出效果。

## 一、工具定义与使用 (`flow_tools.py` & `workflow_graph.py`)

### 当前实现分析 (`flow_tools.py`)

1.  **定义方式**: 主要使用 `StructuredTool.from_function()` 结合 Pydantic schema 来定义同步工具。工具被收集到 `flow_tools` 列表中导出。
2.  **异步工具**: 存在一些 `async def` 工具函数，它们接受 `llm_client` 参数，但目前未被包装成 `Tool` 对象并加入 `flow_tools`，因此 Agent 可能无法直接调用。
3.  **上下文传递**: 同步工具通过 `current_flow_id_var.get()` 获取 `flow_id`。
4.  **返回值**: 工具通常返回包含 `success`, `message`, `error` 等键的字典。

### 当前实现分析 (`workflow_graph.py`)

1.  **工具集成**: `flow_tools` 被正确导入，并在 `compile_workflow_graph` 中通过 `llm.bind_tools(tools)` 绑定到 LLM，这是标准的做法。
2.  **Prompt 工具信息填充**: `compile_workflow_graph` 中使用 `render_text_description(tools)` 和工具名称列表来填充 `STRUCTURED_CHAT_AGENT_PROMPT` 中的 `{tools}` 和 `{tool_names}`，确保 LLM 了解可用工具。
3.  **Agent 节点 (`agent_node`)**:
    - 调用 `llm_with_tools.ainvoke()`。
    - 之前包含一段解析 `{"action": "final_answer", ...}` JSON 的逻辑。在 Prompt 修改为让 LLM 直接输出纯文本后，此段逻辑对于直接回答已不适用。
4.  **工具节点 (`tool_node`)**: 使用 `ToolNode(tools).ainvoke()`，这是执行工具调用的标准方法。
5.  **图结构**: `agent` -> `tools` / `END` -> `agent` 的 ReAct 循环结构是合理的。

### 结合 Context7 最佳实践的建议

1.  **工具定义 (`flow_tools.py`)**:

    - **采纳 `@tool` 装饰器**: 对于函数签名清晰、docstring 详细的工具，建议逐步迁移到使用 `from langchain_core.tools import tool` 提供的 `@tool` 装饰器。这能使代码更简洁，并自动从类型注解和 docstring 推断 schema 及描述。
      - **优先级**: 中。可以逐步进行，不影响现有功能。
    - **强化 Docstrings**: 确保所有工具（无论是 `@tool` 还是 `StructuredTool`）的 docstring 清晰、准确，对 LLM 友好，明确指出工具功能、何时使用及参数含义。
      - **优先级**: 高。直接影响 LLM 的工具选择能力。
    - **暴露异步工具**: 如果 `flow_tools.py` 中的 `async def` 工具函数需要被 Agent 调用，应将它们也包装成 `Tool` 对象（`@tool` 天然支持异步函数）并添加到 `flow_tools` 列表中。
      - **优先级**: 中。根据功能需求决定。
    - **(可选) `RunnableConfig` 传递上下文**: 研究是否可以将 `flow_id` 等运行时上下文通过 `RunnableConfig` 的 `configurable` 字段传递给工具，以替代或补充 `contextvars`，使依赖更明确。
      - **优先级**: 低。当前 `contextvars` 方式可用。

2.  **Agent 节点逻辑 (`workflow_graph.py`)**:  
    进行中！！！ - **移除/修改 `final_answer` JSON 解析**: 在 `agent_node` 中，移除或严格限定之前用于解析 `{"action": "final_answer", "action_input": "..."}` 的逻辑。既然 Prompt 已更新为让 LLM 在直接回答时输出纯文本，`ai_response.content` 就应该是这个纯文本。`AIMessage` 对象应直接返回。 - **优先级**: 高。确保与新的 Prompt 行为一致，并为流式输出纯文本做准备。

## 二、Prompt 动态填充 (`chat_prompts.py` & `dynamic_prompt_utils.py`)

### 当前实现分析

1.  已创建 `backend/langgraphchat/prompts/dynamic_prompt_utils.py` 文件，包含 `get_dynamic_node_types_info()` 函数。
2.  该函数遍历 `/workspace/database/node_database/quickfcpr/` 目录，解析 XML 文件，提取 `<block type="...">` 和 `<field name="...">` 作为节点类型和标签。
3.  `backend/langgraphchat/prompts/chat_prompts.py` 在模块加载时调用此函数，动态填充 `NODE_TYPES_INFO` 变量。
4.  `BASE_SYSTEM_PROMPT`, `WORKFLOW_GENERATION_TEMPLATE`, `TOOL_CALLING_TEMPLATE` 等使用这个动态的 `NODE_TYPES_INFO`。

### 建议与后续

1.  **XML 解析健壮性 (`dynamic_prompt_utils.py`)**:

    - 当前的 XML 解析逻辑基于对 `block` 和 `field` 标签的简单查找。如果 `/workspace/database/node_database/quickfcpr/` 目录下的 XML 文件结构有更多变种或特定需求（例如，从特定属性而非 `field` 提取描述，或处理更复杂的嵌套结构），需要相应增强解析逻辑。
    - 错误处理目前会跳过一些简单的解析错误，对于更复杂的 XML，可能需要更细致的错误报告和跳过机制。
    - **优先级**: 中。根据实际 XML 文件的复杂度和多样性调整。

2.  **`NODE_TYPES_INFO` 的更新时机 (`chat_prompts.py`)**:

    - 目前是在模块加载时执行一次。如果节点定义文件会非常频繁地实时变动，并且要求 LLM 总是使用绝对最新的定义，则需要将 `get_dynamic_node_types_info()` 的调用移到更动态的执行点（例如，`ChatService` 中每次处理请求或编译图时）。对于多数情况，启动时加载一次是可接受的。
    - **优先级**: 低。根据实际需求评估。

3.  **Prompt 中信息的使用**:
    - 确保所有需要了解可用节点类型的 Prompt （不仅仅是 `BASE_SYSTEM_PROMPT`）都正确地使用了动态生成的 `NODE_TYPES_INFO`。
    - 对于 `STRUCTURED_CHAT_AGENT_PROMPT`，目前它主要依赖 `{tools}` 占位符获取工具描述。如果工具描述本身没有充分包含节点类型信息，或者希望 LLM 对可用节点类型有一个更概览性的了解，可以考虑将其系统提示修改为也包含 `NODE_TYPES_INFO` 的内容。
      ```python
      # 在 STRUCTURED_CHAT_AGENT_PROMPT 系统消息中添加类似内容：
      # """...
      # 可用工具：
      # {tools}
      #
      # 作为参考，以下是目前系统中主要可用的节点类型：
      # {node_types_info_placeholder}
      # (具体操作仍需依赖工具描述)
      # ..."""
      # 然后在 compile_workflow_graph 中填充 node_types_info_placeholder=NODE_TYPES_INFO
      ```
    - **优先级**: 中。评估现有工具描述是否足够。

## 三、实现细粒度流式输出 (主要涉及 `chat.py`)

### 当前状态 (切换到 `astream_events` 后)

1.  `process_and_publish_events` 已修改为使用 `compiled_graph.astream_events(..., version="v2")`。
2.  代码尝试处理 `on_chat_model_stream`, `on_tool_start`, `on_tool_end`, `on_chain_end`, 以及各种错误事件。
3.  **主要问题**: 后端日志显示，即使 `DeepSeekLLM._astream` 中设置了 `stream=True` 并调用了 `on_llm_new_token` 回调，`astream_events` 的循环中也**未实际接收到 `on_chat_model_stream` 事件**。实际的 HTTP 调用日志也显示对 DeepSeek API 的调用表现为非流式。

### 后续计划与调查方向

1.  **验证底层 API 调用的流式行为**:

    - **核心任务**: 必须确认对 DeepSeek API (`https://api.deepseek.com/v1/chat/completions`) 的调用是否真正以流式进行。
    - **方法**:
      - 仔细检查 `DeepSeekLLM._astream` 中传递给 `self.async_client.chat.completions.create()` 的所有参数，确保 `stream=True` 无误且没有其他参数覆盖或阻止流式行为。
      - 创建一个最小化的、不依赖 LangGraph 的 Python 脚本，直接使用 `AsyncOpenAI` 客户端（配置为 DeepSeek 的 `api_key` 和 `base_url`）调用 `chat.completions.create(..., stream=True)`，并迭代其返回的异步迭代器，打印每个 `chunk`。观察其行为和 `httpx` 日志。这能隔离问题是否出在 API/SDK 本身。
      - 检查是否有网络代理、防火墙或 DeepSeek API 方面的特定限制（如账户、模型限制）阻止了 SSE 或流式响应。
    - **优先级**: 最高。这是实现真正流式输出的前提。

2.  **LLM 输出 JSON 的影响**:

    - **问题**: 后端日志中 `提取JSON中的action_input作为实际回复` 表明 LLM 被引导输出 JSON。这与细粒度流式输出自然语言文本的目标冲突。
    - **我们已修改 `STRUCTURED_CHAT_AGENT_PROMPT`**，指示 LLM 在直接回答时输出纯文本。
    - **验证**: 测试新的 Prompt 是否有效。观察 LLM 是否真的开始对直接问题回复纯文本。如果仍然输出 `{"action": "final_answer", ...}` JSON，则需要进一步强化 Prompt 或检查 `agent_node` 中是否有其他逻辑仍在促使其生成 JSON。
    - **优先级**: 高。

3.  **`astream_events` 事件的精确捕获**:

    - 如果步骤 1 确认 API 可以流式，并且步骤 2 确认 LLM 可以输出纯文本，但 `chat.py` 中仍然没有收到 `on_chat_model_stream` 事件，则需要更深入地调试 `astream_events`。
    - **方法**:
      - 在 `process_and_publish_events` 的 `astream_events` 循环中，无条件打印出**所有**接收到的 `event` 的完整内容（`event_name`, `event_data`, `run_name`, `tags` 等），以查看是否有我们期望的 token 信息被包装在其他类型的事件中，或者事件名称与 `on_chat_model_stream` 不同。
      - 查阅 LangGraph 关于 `astream_events` (v2) 的最新文档，确认事件的确切名称和结构，特别是与通过 `CallbackManager` 的 `on_llm_new_token` 触发的事件相关的部分。
    - **优先级**: 中高 (依赖于前两点的结果)。

4.  **调整 `process_and_publish_events` 的事件处理**:
    - 一旦能够从 `astream_events` 中稳定地获取到细粒度的 token 事件 (例如，确认了正确的事件名和数据路径如 `event['data']['chunk'].content`)，就需要确保 `final_reply_accumulator` 正确累加这些 token，并将每个 token 实时放入 SSE 队列。
    - 确保对工具调用、错误、链结束等其他重要事件的处理仍然稳健。
    - **优先级**: 中 (依赖于前几点的进展)。

## 四、代码整洁与可维护性

1.  **统一 LLM 客户端**:

    - `langgraphchat/llms/deepseek_client.py` 中的 `DeepSeekLLM` 和 `langgraphchat/models/llm.py` 中的 `DeepSeekChatModel` 功能上有重叠。根据 `langgraphchat/README.md`，前者是重构后的版本。应确保整个项目统一使用 `deepseek_client.py` 中的 `DeepSeekLLM`，并逐步移除旧的实现。`get_chat_model` 函数应只返回推荐的客户端实例。
    - **优先级**: 中。

2.  **README 更新**:
    - 在所有这些重构完成后，相应更新 `/workspace/backend/README.md`, `/workspace/database/README.md`, `/workspace/frontend/README.md`, `/workspace/backend/langgraphchat/README.md`，以反映最新的项目结构、工具实现、Prompt 策略和流式处理机制。
    - **优先级**: 完成主要功能修改后执行。

通过执行以上计划，我们期望能够实现更健壮、更易于维护的工具系统，并最终达成后端向前端进行真正细粒度流式输出的目标。
