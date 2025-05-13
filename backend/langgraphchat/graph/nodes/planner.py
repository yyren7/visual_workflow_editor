import logging
import json
from typing import List

from langchain_core.messages import SystemMessage, AIMessage, BaseMessage, AIMessageChunk
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from ..agent_state import AgentState # Adjusted relative import for AgentState

logger = logging.getLogger(__name__)

async def planner_node(state: AgentState, llm: BaseChatModel, tools: List[BaseTool], system_message_template: str) -> dict:
    """
    Planner (Agent) 节点：调用绑定了工具的 LLM 来决定下一步行动。

    使用流式处理（astream）来获取 LLM 响应，并将 AIMessageChunk 聚合成
    一个最终的 AIMessage。这个 AIMessage 要么包含直接的文本回复，要么包含
    工具调用请求 (tool_calls)。
    它从 state['messages'] 获取完整的对话历史，并在调用 LLM 前预置格式化后的系统提示。
    返回包含新生成的 AIMessage 的字典，用于更新状态。
    """
    llm_with_tools = llm.bind_tools(tools)

    try:
        final_system_message = system_message_template.format(flow_context=state.get("flow_context", {}))
    except KeyError as e:
        logger.error(f"Failed to format system prompt with flow_context. Placeholder {e} might be missing or misspelled. Template: '{system_message_template}'")
        final_system_message = "You are a helpful assistant."

    current_history = list(state.get("messages", []))
    llm_call_input_messages: List[BaseMessage] = [SystemMessage(content=final_system_message)]
    llm_call_input_messages.extend(current_history)

    logger.info(f"Planner: Invoking LLM with streaming. History length: {len(current_history)}")

    final_ai_message = None
    accumulated_ai_message_chunk = None

    async for chunk in llm_with_tools.astream(llm_call_input_messages):
        if not isinstance(chunk, AIMessageChunk):
            logger.warning(f"Planner: Received non-AIMessageChunk in stream: {type(chunk)}")
            continue

        if accumulated_ai_message_chunk is None:
            accumulated_ai_message_chunk = chunk
        else:
            accumulated_ai_message_chunk += chunk
    
    if accumulated_ai_message_chunk:
        final_tool_calls = getattr(accumulated_ai_message_chunk, 'tool_calls', None)
        final_content = accumulated_ai_message_chunk.content
        final_id = accumulated_ai_message_chunk.id
        final_response_metadata = getattr(accumulated_ai_message_chunk, 'response_metadata', None)
        final_usage_metadata = getattr(accumulated_ai_message_chunk, 'usage_metadata', None)

        if not final_tool_calls and accumulated_ai_message_chunk.tool_call_chunks:
            logger.info("Planner: Reconstructing tool_calls from tool_call_chunks.")
            reconstructed_tool_calls = []
            parsed_tool_calls_by_index = {}
            for tc_chunk in accumulated_ai_message_chunk.tool_call_chunks:
                idx = tc_chunk.get('index')
                if idx is None: continue

                if idx not in parsed_tool_calls_by_index:
                    parsed_tool_calls_by_index[idx] = { "id": None, "name": None, "args": "" }

                if tc_chunk.get('id'): parsed_tool_calls_by_index[idx]['id'] = tc_chunk['id']
                if tc_chunk.get('name'): parsed_tool_calls_by_index[idx]['name'] = tc_chunk['name']
                parsed_tool_calls_by_index[idx]["args"] += tc_chunk.get('args', "")

            for idx in sorted(parsed_tool_calls_by_index.keys()):
                tc = parsed_tool_calls_by_index[idx]
                if tc.get('name') and tc.get('id') and tc.get('args') is not None:
                    try:
                        parsed_args = json.loads(tc['args'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Planner: Failed to parse tool call args for {tc.get('name')}: {tc.get('args')}. Error: {e}. Keeping as string.")
                        parsed_args = tc['args']
                    reconstructed_tool_calls.append({
                        "name": tc['name'],
                        "args": parsed_args,
                        "id": tc['id']
                    })
            if reconstructed_tool_calls:
                final_tool_calls = reconstructed_tool_calls
                logger.info(f"Planner: Reconstructed tool_calls: {final_tool_calls}")

        if final_tool_calls:
            logger.info(f"Planner: Constructing AIMessage with tool_calls: {final_tool_calls}")
            final_ai_message = AIMessage(
                content=final_content if final_content else "",
                tool_calls=final_tool_calls,
                id=final_id,
                response_metadata=final_response_metadata,
                usage_metadata=final_usage_metadata
            )
        else:
            logger.info("Planner: Constructing AIMessage without tool_calls (direct response).")
            final_ai_message = AIMessage(
                content=final_content if final_content else "",
                id=final_id,
                response_metadata=final_response_metadata,
                usage_metadata=final_usage_metadata
            )
    else:
        logger.warning("Planner: LLM stream was empty or yielded no processable AIMessageChunks.")
        final_ai_message = AIMessage(content="")

    if final_ai_message.tool_calls:
         logger.info(f"Planner: Final AIMessage contains {len(final_ai_message.tool_calls)} tool call(s).")
    else:
         logger.info(f"Planner: Final AIMessage contains direct response content: '{str(final_ai_message.content)[:100]}...'")

    return {"messages": [final_ai_message]} 