"""
定义和编译 LangGraph 工作流图。

该模块负责构建用于处理聊天交互、管理状态以及调用工具（特别是与流程图操作相关的工具）的 LangGraph 状态图。

它定义了图的结构（节点、边、入口点、条件路由），并将具体的节点实现逻辑委托给其他模块。

提供了一个编译函数 `compile_workflow_graph` 来创建可执行的图实例。

"""

# Input-》advisor-》planner-》parameter-》
# exhibitor-》code generator-》code combination

from typing import List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description
from langchain_core.runnables import RunnableConfig

from .agent_state import AgentState
from ..prompts.chat_prompts import STRUCTURED_CHAT_AGENT_PROMPT # For system prompt content
from ..tools import flow_tools # This should be the List[BaseTool]
from ..context import current_flow_id_var # Context variable for flow_id
import logging # Ensure logging is imported
import os # Make sure os is imported for listing files
import xml.etree.ElementTree as ET
import json
from functools import partial

# 导入工具，LLM, ChatService 等将在此处添加
# from ...app.services.chat_service import ChatService # 路径可能需要调整
# from ..tools.flow_tools import ... # 具体的工具或工具列表

# TODO: 定义 Agent 节点函数
# async def agent_node(state: AgentState):
#     # 实现 Agent 逻辑：调用 LLM，解析输出
#     pass

# TODO: 定义工具执行节点函数
# async def tool_node(state: AgentState):
#     # 实现工具执行逻辑
#     pass

# TODO: 定义条件边逻辑
# def should_continue(state: AgentState):
#     # 判断是继续调用工具还是结束
#     pass

# 创建 StateGraph 实例
workflow = StateGraph(AgentState)

# TODO: 添加节点
# workflow.add_node("agent", agent_node)
# workflow.add_node("tools", tool_node)

# TODO: 设置入口点
# workflow.set_entry_point("agent")

# TODO: 添加条件边
# workflow.add_conditional_edges(
#     "agent",
#     should_continue,
#     {
#         "continue": "tools", # 假设 "continue" 表示调用工具
#         "end": END # 假设 "end" 表示结束
#     }
# )

# TODO: 添加从工具节点回到 Agent 节点的边
# workflow.add_edge("tools", "agent")

# TODO: 编译图
# compiled_workflow = workflow.compile()

# 稍后，我们将把编译后的图暴露出去，例如通过一个函数
# def get_workflow_graph():
#     # 可能需要确保 ChatService 和工具已初始化
#     # llm = ChatService._get_active_llm() # 假设可以这样获取或通过依赖注入
#     # tools = ... # 获取工具列表
#     # compiled_workflow.with_config(...) # 如果需要配置
#     return compiled_workflow 

# 新的输入处理节点
async def input_handler_node(state: AgentState) -> dict:
    """
    处理 state['input'] 字段，将其转换为 HumanMessage 并有条件地添加到 messages 列表中。

    此节点确保每个用户输入只被转换为 HumanMessage 并添加到状态一次，
    避免因图的循环执行导致重复添加相同的用户消息。
    它通过检查 'input_processed' 标志位和比较最后一条消息来实现。
    返回的字典仅包含需要通过 operator.add 更新到状态的字段（通常是 'messages' 和 'input_processed'）。
    """
    logger = logging.getLogger(__name__)
    current_messages_from_state = list(state.get("messages", []))
    input_str = state.get("input")
    input_already_processed = state.get("input_processed", False)

    updated_state_dict = {}
    newly_added_message_for_operator_add = None

    if input_str and not input_already_processed:
        logger.info(f"Input handler: Processing new input: '{input_str}'")
        new_human_message = HumanMessage(content=input_str)

        # 检查是否需要添加新的消息（避免重复添加完全相同的最后一条消息）
        should_add_new_message = False
        if (not current_messages_from_state or
            not (isinstance(current_messages_from_state[-1], HumanMessage) and
                 current_messages_from_state[-1].content == input_str)):
            should_add_new_message = True

        if should_add_new_message:
            newly_added_message_for_operator_add = new_human_message
            logger.info(f"Input handler: Prepared new HumanMessage for appending: {new_human_message.content}")
        else:
            logger.info("Input handler: Input string matches last HumanMessage; not preparing for append.")

        # 标记输入已处理，并清除输入字段
        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None
        logger.info("Input handler: Input processed flag set, input field cleared.")

    elif input_str and input_already_processed:
        # 如果输入存在但已标记为处理过（可能因为某种原因未被清除），则清除它
        logger.info(f"Input handler: Input '{input_str}' found but already marked processed. Clearing input field.")
        updated_state_dict["input"] = None
    # else: # 无新输入或已处理并清除
    #     logger.info("Input handler: No new input string, or input already processed and cleared.")

    # 如果有新消息需要添加，放入返回字典
    if newly_added_message_for_operator_add:
        # 返回列表形式以配合 operator.add
        updated_state_dict["messages"] = [newly_added_message_for_operator_add]

    # # 确保 input_processed 标志在状态中至少更新一次（如果它变为 True）
    # if not updated_state_dict and input_already_processed:
    #      updated_state_dict["input_processed"] = True # 通常 input_processed 在首次处理时就已设为 True

    return updated_state_dict

# Agent node: invokes the LLM to get the next action or response
async def planner_node(state: AgentState, llm: BaseChatModel, tools: List[BaseTool], system_message_template: str) -> dict:
    """
    Planner (Agent) 节点：调用绑定了工具的 LLM 来决定下一步行动。

    使用流式处理（astream）来获取 LLM 响应，并将 AIMessageChunk 聚合成
    一个最终的 AIMessage。这个 AIMessage 要么包含直接的文本回复，要么包含
    工具调用请求 (tool_calls)。
    它从 state['messages'] 获取完整的对话历史，并在调用 LLM 前预置格式化后的系统提示。
    返回包含新生成的 AIMessage 的字典，用于更新状态。
    """
    logger = logging.getLogger(__name__)
    llm_with_tools = llm.bind_tools(tools)
    
    # 动态格式化系统提示，填入当前的 flow_context
    # system_message_template 已在编译时部分格式化（包含工具信息）
    try:
        final_system_message = system_message_template.format(flow_context=state.get("flow_context", {}))
    except KeyError as e:
        logger.error(f"Failed to format system prompt with flow_context. Placeholder {e} might be missing or misspelled in the template provided during compilation. Template: '{system_message_template}'")
        # 提供一个回退的系统提示，避免完全失败
        final_system_message = "You are a helpful assistant."

    # 获取当前对话历史
    current_history = list(state.get("messages", []))

    # 准备 LLM 调用输入：系统提示 + 对话历史
    llm_call_input_messages: List[BaseMessage] = [SystemMessage(content=final_system_message)]
    llm_call_input_messages.extend(current_history)
    
    logger.info(f"Planner: Invoking LLM with streaming. History length: {len(current_history)}")
    # logger.debug(f"Planner: Input messages for LLM: {llm_call_input_messages}") # Debug level for full messages

    final_ai_message = None
    accumulated_ai_message_chunk = None

    # 使用流式调用获取 LLM 响应
    async for chunk in llm_with_tools.astream(llm_call_input_messages):
        if not isinstance(chunk, AIMessageChunk):
            logger.warning(f"Planner: Received non-AIMessageChunk in stream: {type(chunk)}")
            continue

        # 累积消息块
        if accumulated_ai_message_chunk is None:
            accumulated_ai_message_chunk = chunk
        else:
            accumulated_ai_message_chunk += chunk

        # 优化：如果已累积完整的 tool_calls，可以提前中断流
        # （注意：这取决于 LLM 是否总是在单个 chunk 或连续 chunk 中发送完整的 tool_calls 信息）
        # 当前实现是累积所有 chunk，然后在最后处理
        # if accumulated_ai_message_chunk and accumulated_ai_message_chunk.tool_calls:
        #     logger.info(f"Planner: Full tool_calls detected in accumulated chunk. Breaking stream.")
        #     break

    # 流结束后，处理累积的 chunk
    if accumulated_ai_message_chunk:
        # 提取最终的 tool_calls 和 content
        final_tool_calls = getattr(accumulated_ai_message_chunk, 'tool_calls', None)
        final_content = accumulated_ai_message_chunk.content
        final_id = accumulated_ai_message_chunk.id
        # 尝试获取元数据
        final_response_metadata = getattr(accumulated_ai_message_chunk, 'response_metadata', None)
        final_usage_metadata = getattr(accumulated_ai_message_chunk, 'usage_metadata', None)

        # 处理 tool_call_chunks (如果 LLM 以 chunk 形式发送工具调用)
        if not final_tool_calls and accumulated_ai_message_chunk.tool_call_chunks:
            logger.info("Planner: Reconstructing tool_calls from tool_call_chunks.")
            reconstructed_tool_calls = []
            # 按索引分组重构工具调用参数
            parsed_tool_calls_by_index = {}
            for tc_chunk in accumulated_ai_message_chunk.tool_call_chunks:
                idx = tc_chunk.get('index') # 使用 .get 以防万一
                if idx is None: continue # 跳过没有索引的块

                if idx not in parsed_tool_calls_by_index:
                    parsed_tool_calls_by_index[idx] = { "id": None, "name": None, "args": "" }

                # 合并块信息
                if tc_chunk.get('id'): parsed_tool_calls_by_index[idx]['id'] = tc_chunk['id']
                if tc_chunk.get('name'): parsed_tool_calls_by_index[idx]['name'] = tc_chunk['name']
                parsed_tool_calls_by_index[idx]["args"] += tc_chunk.get('args', "")

            # 转换重构后的数据为 LangChain ToolCall 格式
            for idx in sorted(parsed_tool_calls_by_index.keys()):
                tc = parsed_tool_calls_by_index[idx]
                if tc.get('name') and tc.get('id') and tc.get('args') is not None:
                    try:
                        # 尝试解析 JSON 参数
                        parsed_args = json.loads(tc['args'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Planner: Failed to parse tool call args for {tc.get('name')}: {tc.get('args')}. Error: {e}. Keeping as string.")
                        parsed_args = tc['args'] # 保留为原始字符串
                    reconstructed_tool_calls.append({
                        "name": tc['name'],
                        "args": parsed_args,
                        "id": tc['id']
                    })
            if reconstructed_tool_calls:
                final_tool_calls = reconstructed_tool_calls
                logger.info(f"Planner: Reconstructed tool_calls: {final_tool_calls}")


        # 根据是否有 tool_calls 构建最终的 AIMessage
        if final_tool_calls:
            logger.info(f"Planner: Constructing AIMessage with tool_calls: {final_tool_calls}")
            final_ai_message = AIMessage(
                content=final_content if final_content else "", # 确保 content 不是 None
                tool_calls=final_tool_calls,
                id=final_id,
                response_metadata=final_response_metadata,
                usage_metadata=final_usage_metadata
            )
        else:
            logger.info("Planner: Constructing AIMessage without tool_calls (direct response).")
            final_ai_message = AIMessage(
                content=final_content if final_content else "", # 确保 content 不是 None
                id=final_id,
                response_metadata=final_response_metadata,
                usage_metadata=final_usage_metadata
            )
    else:
        # 如果流完全为空或没有产生有效内容
        logger.warning("Planner: LLM stream was empty or yielded no processable AIMessageChunks.")
        final_ai_message = AIMessage(content="") # 返回空消息以避免错误

    # logger.debug(f"Planner: Aggregated AIMessage: {final_ai_message}") # Debug level for full message object
    if final_ai_message.tool_calls:
         logger.info(f"Planner: Final AIMessage contains {len(final_ai_message.tool_calls)} tool call(s).")
    else:
         logger.info(f"Planner: Final AIMessage contains direct response content: '{str(final_ai_message.content)[:100]}...'")

    # 返回包含新 AI 消息的字典，用于 operator.add 更新状态
    return {"messages": [final_ai_message]}

# Tool node: executes tools called by the agent
async def tool_node(state: AgentState, tools: List[BaseTool]) -> dict:
    """
    工具执行节点：使用 LangGraph 的 ToolNode 来执行 Agent 请求的工具。

    它接收包含工具调用请求的 AIMessage (通常是 messages 列表中的最后一条)，
    调用相应的工具，并将结果作为 ToolMessage 返回。
    """
    logger.info("Tool node: Executing tools...")
    # logger.debug(f"Tool node: Last message (containing tool calls): {state['messages'][-1]}")

    # 创建 ToolNode 实例来执行工具
    tool_executor = ToolNode(tools)

    # 调用 ToolNode 来执行工具并获取结果
    # ToolNode 内部会处理从 AIMessage 中提取 tool_calls 并执行
    result = await tool_executor.ainvoke({"messages": state["messages"]})

    # result 预期是一个包含 ToolMessage(s) 的字典，格式为 {"messages": [ToolMessage(...)]}
    # logger.debug(f"Tool node: Execution result: {result}")
    if "messages" in result and isinstance(result["messages"], list):
         logger.info(f"Tool node: Finished execution, returning {len(result['messages'])} ToolMessage(s).")
    else:
         logger.warning(f"Tool node: Execution finished but result format might be unexpected: {result}")


    return result

# Conditional edge: determines whether to continue with tools or end
def should_continue(state: AgentState) -> str:
    """
    条件边：决定 Planner 节点之后的下一个状态。

    检查状态中最后一条消息是否是包含工具调用 (tool_calls) 的 AIMessage。
    如果是，则路由到 "tools" 节点执行工具。
    否则，流程结束 (END)。
    """
    messages = state.get("messages", [])
    if not messages:
        # 如果没有任何消息，通常不应该发生，但为了安全起见结束
        logger.warning("should_continue: No messages found in state, ending.")
        return END

    last_message = messages[-1]
    if isinstance(last_message, AIMessage):
        if last_message.tool_calls:
            logger.info("should_continue: AIMessage has tool_calls, routing to 'tools'.")
            return "tools"
        else:
            logger.info("should_continue: AIMessage has no tool_calls, ending.")
            return END
    else:
        # 如果最后一条消息不是 AIMessage（例如是 HumanMessage 或 ToolMessage），
        # 这通常意味着流程应该结束或出现了意外状态
        logger.info(f"should_continue: Last message is not AIMessage (type: {type(last_message)}), ending.")
        return END

# Graph compilation
def compile_workflow_graph(llm: BaseChatModel, custom_tools: List[BaseTool] = None) -> StateGraph:
    """
    编译并返回 LangGraph 工作流图实例。

    Args:
        llm: 用于 Planner 节点的 BaseChatModel 实例。
        custom_tools: 可选的工具列表。如果提供，则使用这些工具；否则使用默认的 `flow_tools`。

    Returns:
        一个已编译的 LangGraph StateGraph 实例。
    """
    logger.info("Compiling workflow graph...")

    # 确定要使用的工具集
    tools_to_use = custom_tools if custom_tools is not None else flow_tools
    if not tools_to_use:
         logger.warning("Compiling workflow with an empty tool list.")
    else:
         logger.info(f"Compiling workflow with tools: {[t.name for t in tools_to_use]}")


    # --- 准备 Planner 的系统提示模板 ---
    # 1. 获取基础模板字符串
    # 假设 STRUCTURED_CHAT_AGENT_PROMPT 的第一个消息是系统提示模板
    if not (STRUCTURED_CHAT_AGENT_PROMPT.messages and
            isinstance(STRUCTURED_CHAT_AGENT_PROMPT.messages[0], SystemMessage) and
            hasattr(STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt, 'template')):
        logger.error("System prompt template structure is not as expected. Using a fallback.")
        raw_system_template = "You are a helpful assistant. Use the available tools if necessary. Context: {flow_context}"
    else:
        raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template

    # 2. 渲染工具描述和名称（静态部分）
    rendered_tools_desc = render_text_description(tools_to_use)
    tool_names_list_str = ", ".join([t.name for t in tools_to_use])

    # 3. 获取动态节点类型信息
    try:
        node_types_description = get_dynamic_node_types_info()
    except Exception as e:
        logger.error(f"Error getting dynamic node types info: {e}")
        node_types_description = "(获取节点类型信息时出错)\n"

    # 4. 部分格式化系统提示模板，填入静态信息
    #    动态的 {flow_context} 将在 planner_node 中根据每次调用的状态填入
    #    确保模板中确实包含这些占位符
    system_prompt_template_for_planner = raw_system_template
    placeholders_to_fill = {
        "{tools}": rendered_tools_desc,
        "{tool_names}": tool_names_list_str,
        "{NODE_TYPES_INFO}": node_types_description
    }
    for placeholder, value in placeholders_to_fill.items():
        if placeholder in system_prompt_template_for_planner:
            system_prompt_template_for_planner = system_prompt_template_for_planner.replace(placeholder, value)
        else:
            logger.warning(f"Placeholder '{placeholder}' not found in the system prompt template provided by STRUCTURED_CHAT_AGENT_PROMPT.")

    # --- 创建和配置 StateGraph ---
    workflow = StateGraph(AgentState)

    # 使用 functools.partial 绑定参数到节点函数
    # 这使得节点函数只需要接收 state 参数，其他依赖（如 llm, tools）在编译时注入
    bound_input_handler_node = partial(input_handler_node)
    bound_planner_node = partial(
        planner_node,
        llm=llm,
        tools=tools_to_use,
        system_message_template=system_prompt_template_for_planner # 传递部分格式化的模板
    )
    bound_tool_node = partial(
        tool_node,
        tools=tools_to_use
    )

    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("planner", bound_planner_node)
    workflow.add_node("tools", bound_tool_node)

    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边
    workflow.add_edge("input_handler", "planner") # 输入处理后总是到规划器

    # 从规划器出发的条件边
    workflow.add_conditional_edges(
        "planner",          # 源节点
        should_continue,    # 判断函数
        {                   # 目标映射
            "tools": "tools", # 如果 should_continue 返回 "tools"
            END: END,         # 如果 should_continue 返回 END
        }
    )

    # 从工具节点回到规划器节点
    workflow.add_edge("tools", "planner") # 工具执行完毕后，回到规划器处理结果

    # 编译图
    logger.info("Workflow graph compilation complete.")
    return workflow.compile()

# Example of how it might be used (not part of the library code itself):
# if __name__ == "__main__":
#     from backend.app.services.chat_service import ChatService 
#     # This is an example, ChatService needs a DB session.
#     # db_session = ... get a db session ...
#     # chat_service = ChatService(db=db_session)
#     # active_llm = chat_service._get_active_llm()
#     # compiled_workflow = compile_workflow_graph(active_llm, flow_tools)
#     
#     # To run:
#     # inputs = {"messages": [HumanMessage(content="Create a start node")], "current_flow_id": "some_flow_id", "flow_context": {"details": "..."}}
#     # async for event in compiled_workflow.astream(inputs):
#     #     print(event)
#     #     print("----") 