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
    处理 state.input 字段，将其转换为 HumanMessage 并有条件地添加到 messages 列表中。
    确保每个用户输入只被处理（即转换为HumanMessage并准备好被追加）一次。
    由于 messages 使用 operator.add，此节点只应返回实际新追加的消息，或者不返回 messages 键。
    """
    logger = logging.getLogger(__name__)
    current_messages_from_state = list(state.get("messages", [])) 
    input_str = state.get("input")
    input_already_processed = state.get("input_processed", False)

    updated_state_dict = {}
    newly_added_message_for_operator_add = None

    if input_str and not input_already_processed:
        logger.info(f"Input handler node processing new input: '{input_str}'")
        new_human_message = HumanMessage(content=input_str)
        
        should_add_new_message = False
        if (not current_messages_from_state or 
            not (isinstance(current_messages_from_state[-1], HumanMessage) and
                 current_messages_from_state[-1].content == input_str)):
            should_add_new_message = True
        
        if should_add_new_message:
            newly_added_message_for_operator_add = new_human_message
            logger.info(f"Prepared new HumanMessage for appending: {new_human_message.content}")
        else:
            logger.info("Input string already matches the last HumanMessage in messages; not preparing for append.")
            
        updated_state_dict["input_processed"] = True
        updated_state_dict["input"] = None  
        logger.info("Input processed flag set, input field cleared.")

    elif input_str and input_already_processed:
        logger.info(f"Input handler: Input '{input_str}' found but already marked processed. Clearing input field.")
        updated_state_dict["input"] = None 
    else:
        logger.info("Input handler node: No new input string, or input already processed and cleared.")
    
    if newly_added_message_for_operator_add:
        updated_state_dict["messages"] = [newly_added_message_for_operator_add]
    
    if not updated_state_dict and input_already_processed:
        updated_state_dict["input_processed"] = True
        
    return updated_state_dict

# Agent node: invokes the LLM to get the next action or response
async def planner_node(state: AgentState, llm: BaseChatModel, tools: List[BaseTool], system_message_template: str) -> dict:
    """
    Invokes the LLM planner to decide on the next step using streaming.
    Aggregates streamed chunks into a final AIMessage.
    The planner decides if a tool should be called or if it can respond directly.
    Assumes state.messages already contains the full history including the latest HumanMessage.
    """
    logger = logging.getLogger(__name__) 
    llm_with_tools = llm.bind_tools(tools)
    
    final_system_message = system_message_template.format(flow_context=state.get("flow_context", {}))
    
    # state.messages is now the source of truth for history, prepared by input_handler_node
    current_history = list(state.get("messages", []))

    # Prepend system message for LLM call
    llm_call_input_messages: List[BaseMessage] = [SystemMessage(content=final_system_message)]
    llm_call_input_messages.extend(current_history)
    
    logger.info(f"Planner node invoking LLM with streaming. Input messages for LLM: {llm_call_input_messages}")

    final_ai_message = None
    accumulated_ai_message_chunk = None 

    async for chunk in llm_with_tools.astream(llm_call_input_messages):
        if not isinstance(chunk, AIMessageChunk):
            logger.warning(f"Received non-AIMessageChunk in stream: {type(chunk)}")
            continue
        
        if accumulated_ai_message_chunk is None:
            accumulated_ai_message_chunk = chunk
        else:
            accumulated_ai_message_chunk += chunk 

        if accumulated_ai_message_chunk and accumulated_ai_message_chunk.tool_calls:
            logger.info(f"Full tool_calls detected in accumulated_ai_message_chunk after processing current chunk. Breaking stream.")
            logger.info(f"Tool calls: {accumulated_ai_message_chunk.tool_calls}")
            logger.info(f"Content associated with these tool_calls: '{accumulated_ai_message_chunk.content}'")
            break

    if accumulated_ai_message_chunk:
        final_tool_calls = getattr(accumulated_ai_message_chunk, 'tool_calls', None)
        final_content = accumulated_ai_message_chunk.content
        final_id = accumulated_ai_message_chunk.id
        final_response_usage_metadata = getattr(accumulated_ai_message_chunk, 'response_metadata', None) 
        final_usage_metadata = getattr(accumulated_ai_message_chunk, 'usage_metadata', None) 

        if not final_tool_calls and accumulated_ai_message_chunk.tool_call_chunks:
            logger.info("Accumulated chunk has tool_call_chunks, reconstructing tool_calls.")
            reconstructed_tool_calls = []
            parsed_tool_calls_by_index = {}
            for tc_chunk in accumulated_ai_message_chunk.tool_call_chunks:
                idx = tc_chunk['index']
                if idx not in parsed_tool_calls_by_index:
                    parsed_tool_calls_by_index[idx] = {
                        "id": tc_chunk.get('id'),
                        "name": tc_chunk.get('name'),
                        "args": ""
                    }
                if tc_chunk.get('id') and not parsed_tool_calls_by_index[idx]['id']:
                    parsed_tool_calls_by_index[idx]['id'] = tc_chunk['id']
                if tc_chunk.get('name') and not parsed_tool_calls_by_index[idx]['name']:
                    parsed_tool_calls_by_index[idx]['name'] = tc_chunk['name']
                
                parsed_tool_calls_by_index[idx]["args"] += tc_chunk.get('args', "")

            for idx in sorted(parsed_tool_calls_by_index.keys()):
                tc = parsed_tool_calls_by_index[idx]
                if tc.get('name') and tc.get('id') and tc.get('args') is not None:
                    try:
                        import json
                        parsed_args = json.loads(tc['args'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse tool call args for {tc.get('name')}: {tc.get('args')}. Error: {e}. Keeping as string.")
                        parsed_args = tc['args']
                    reconstructed_tool_calls.append({
                        "name": tc['name'],
                        "args": parsed_args,
                        "id": tc['id']
                    })
            if reconstructed_tool_calls:
                final_tool_calls = reconstructed_tool_calls

        if final_tool_calls:
            logger.info(f"Constructing AIMessage with tool_calls: {final_tool_calls}")
            final_ai_message = AIMessage(
                content=final_content,
                tool_calls=final_tool_calls,
                id=final_id,
                response_metadata=final_response_usage_metadata, 
                usage_metadata=final_usage_metadata 
            )
        else:
            logger.info("Constructing AIMessage without tool_calls.")
            final_ai_message = AIMessage(
                content=final_content, 
                id=final_id,
                response_metadata=final_response_usage_metadata, 
                usage_metadata=final_usage_metadata 
            )
    else:
        logger.warning("Planner stream was empty or yielded no processable AIMessageChunks and no fallback content.")
        final_ai_message = AIMessage(content="") 

    logger.info(f"Planner node aggregated LLM response. Type: {type(final_ai_message)}")
    if isinstance(final_ai_message, AIMessage):
        logger.info(f"Aggregated AIMessage content: '{str(final_ai_message.content)[:200]}...'")
        if final_ai_message.tool_calls:
            logger.info(f"Aggregated AIMessage has tool_calls: {final_ai_message.tool_calls}")
        else:
            logger.info("Aggregated AIMessage has no tool_calls (planner will respond directly).")
            
    # Return only the new AI message for operator.add to append
    return {"messages": [final_ai_message]}

# Tool node: executes tools called by the agent
async def tool_node(state: AgentState, tools: List[BaseTool]) -> dict:
    """
    Executes tools based on the agent's decision.
    """
    # 创建ToolNode实例
    tool_executor = ToolNode(tools)
    
    # 使用ToolNode处理消息 - 使用await处理异步调用
    result = await tool_executor.ainvoke({"messages": state["messages"]})
    return result

# Conditional edge: determines whether to continue with tools or end
def should_continue(state: AgentState) -> str:
    """
    Determines the next step after the planner node.
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"  # Route to tool_node
    return END  # End the graph execution

# Graph compilation
def compile_workflow_graph(llm: BaseChatModel, custom_tools: List[BaseTool] = None) -> StateGraph:
    """
    Compiles and returns the LangGraph workflow.
    """
    # 导入functools.partial用于创建偏函数
    from functools import partial
    
    tools_to_use = custom_tools if custom_tools is not None else flow_tools
    
    # Prepare the system prompt template string from STRUCTURED_CHAT_AGENT_PROMPT
    # This system message will be formatted with flow_context dynamically in the planner_node.
    # The {tools} and {tool_names} parts are static based on the tools provided.
    raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template
    
    rendered_tools_desc = render_text_description(tools_to_use)
    tool_names_list_str = ", ".join([t.name for t in tools_to_use])

    # Generate NODE_TYPES_INFO string
    node_types_description = "可用的节点类型及其XML定义的参数 (参数名: 默认值):\n"
    # Reference the constant from flow_tools.py if possible, or redefine path carefully
    # For now, hardcoding path as in previous discussions for create_node_tool_func
    xml_node_dir = "database/node_database/quick-fcpr/" 
    available_node_types_count = 0
    try:
        if os.path.exists(xml_node_dir):
            for filename in sorted(os.listdir(xml_node_dir)): # Sort for consistent order
                if filename.endswith(".xml"):
                    node_type_name = filename.replace(".xml", "")
                    node_params_list = []
                    try:
                        tree = ET.parse(os.path.join(xml_node_dir, filename))
                        root = tree.getroot()
                        block_element = root.find(".//block")
                        if block_element is not None:
                            for field in block_element.findall("field"):
                                param_name = field.get("name")
                                default_value = field.text if field.text is not None else ""
                                if param_name:
                                    node_params_list.append(f"{param_name}: '{default_value}'")
                    except Exception as e_xml:
                        logging.warning(f"读取或解析XML {filename} 时出错: {e_xml}")
                    
                    if node_params_list:
                        node_types_description += f"- {node_type_name} (参数: {', '.join(node_params_list)})\n"
                    else:
                        node_types_description += f"- {node_type_name} (无XML中定义的参数或解析失败)\n"
                    available_node_types_count +=1
            if available_node_types_count == 0:
                node_types_description += " (当前未在XML中定义特定的节点类型)\n"
        else:
            # Corrected path for user log
            logging.warning(f"节点定义目录 {os.path.abspath(xml_node_dir)} 未找到。这可能影响系统提示中的 NODE_TYPES_INFO。")
            node_types_description += f" (警告：节点定义目录 {xml_node_dir} 未找到)\n"
    except Exception as e:
        logging.error(f"准备NODE_TYPES_INFO时出错: {e}")
        node_types_description += f" (获取节点类型信息时出错: {str(e)})\n"
    
    # Partially format the system prompt with tool info. Flow_context will be added per call.
    # This assumes the template string has {tools}, {tool_names}, {flow_context} and {NODE_TYPES_INFO}
    try:
        # Attempt to format with all known static placeholders for the system prompt
        # The dynamic placeholder {flow_context} will be handled in the planner_node
        system_prompt_template_for_planner = raw_system_template.replace("{tools}", rendered_tools_desc)
        system_prompt_template_for_planner = system_prompt_template_for_planner.replace("{tool_names}", tool_names_list_str)
        system_prompt_template_for_planner = system_prompt_template_for_planner.replace("{NODE_TYPES_INFO}", node_types_description)
    except Exception as e:
        logging.error(f"格式化系统提示模板时出错: {e}")
        # If formatting fails, use a simpler approach but still try to include NODE_TYPES_INFO if possible
        system_prompt_template_for_planner = f"You are a helpful assistant with access to the following tools: {rendered_tools_desc}. Use these tools to help the user.\nAvailable node types:\n{node_types_description}"
    
    # Create the workflow graph
    workflow = StateGraph(AgentState)
    
    # Bind arguments to the node functions
    bound_input_handler_node = partial(input_handler_node) # No specific args to bind other than state
    bound_planner_node = partial(
        planner_node, 
        llm=llm, 
        tools=tools_to_use, 
        system_message_template=system_prompt_template_for_planner
    )
    bound_tool_node = partial(
        tool_node,
        tools=tools_to_use
    )
    
    # Add nodes to the graph
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("planner", bound_planner_node)
    workflow.add_node("tools", bound_tool_node)
    
    # Set the entry point to the new input_handler_node
    workflow.set_entry_point("input_handler")
    
    # Add edge from input_handler to planner
    workflow.add_edge("input_handler", "planner")
    
    # Conditional routing from planner
    workflow.add_conditional_edges(
        "planner",
        should_continue,
        {
            "tools": "tools",
            END: END,
        }
    )
    
    # Add edge from tools back to planner
    workflow.add_edge("tools", "planner")
    
    # Compile the workflow
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