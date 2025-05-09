from typing import List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description

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

# Agent node: invokes the LLM to get the next action or response
async def planner_node(state: AgentState, llm: BaseChatModel, tools: List[BaseTool], system_message_template: str) -> dict:
    """
    Invokes the LLM planner to decide on the next step using streaming.
    Aggregates streamed chunks into a final AIMessage.
    The planner decides if a tool should be called or if it can respond directly.
    """
    logger = logging.getLogger(__name__) # 获取logger实例
    llm_with_tools = llm.bind_tools(tools)
    
    final_system_message = system_message_template.format(flow_context=state.get("flow_context", {}))
    prompt_messages: List[BaseMessage] = [SystemMessage(content=final_system_message)]
    
    current_log = list(state["messages"]) # Make a copy
    if state.get("input"):
        is_new_input = True
        if current_log and isinstance(current_log[-1], HumanMessage) and current_log[-1].content == state["input"]:
            is_new_input = False
        if is_new_input:
            current_log.append(HumanMessage(content=state["input"]))
    prompt_messages.extend(current_log)

    logger.info(f"Planner node invoking LLM with streaming. Input messages: {prompt_messages}")

    full_response_content = ""
    aggregated_tool_calls = []
    final_ai_message = None # Store the last chunk, or the chunk that provided full tool_calls

    async for chunk in llm_with_tools.astream(prompt_messages):
        if not isinstance(chunk, AIMessageChunk):
            logger.warning(f"Received non-AIMessageChunk in stream: {type(chunk)}")
            continue

        # logger.debug(f"Planner node received stream chunk: {chunk.content}, TC chunks: {chunk.tool_call_chunks}")
        full_response_content += chunk.content
        
        if chunk.tool_call_chunks:
            for tc_chunk in chunk.tool_call_chunks:
                if len(aggregated_tool_calls) <= tc_chunk['index']:
                    aggregated_tool_calls.extend([{}] * (tc_chunk['index'] - len(aggregated_tool_calls) + 1))
                
                current_tc = aggregated_tool_calls[tc_chunk['index']]
                if 'id' not in current_tc and tc_chunk.get('id'):
                    current_tc['id'] = tc_chunk['id']
                if 'name' not in current_tc and tc_chunk.get('name'):
                    current_tc['name'] = tc_chunk['name']
                current_tc['args'] = current_tc.get('args', "") + tc_chunk.get('args', "")

        if chunk.tool_calls: 
            logger.info(f"Full tool_calls received in a chunk: {chunk.tool_calls}")
            # Use the content accumulated *up to this point* with the definitive tool_calls
            final_ai_message = AIMessage(content=full_response_content, tool_calls=chunk.tool_calls, id=chunk.id)
            break 

        final_ai_message = chunk # Keep a reference to the latest chunk

    # Construct the final AIMessage if not broken by full tool_calls
    if not (final_ai_message and final_ai_message.tool_calls and isinstance(final_ai_message, AIMessage)): # Check if it's already a complete AIMessage
        reconstructed_tool_calls_list = []
        if aggregated_tool_calls:
            for tc_data in aggregated_tool_calls:
                if tc_data.get('name') and tc_data.get('args') and tc_data.get('id'):
                    try:
                        import json
                        parsed_args = json.loads(tc_data['args'])
                    except (json.JSONDecodeError, TypeError):
                        parsed_args = tc_data['args'] 
                    reconstructed_tool_calls_list.append({
                        "name": tc_data['name'],
                        "args": parsed_args,
                        "id": tc_data['id']
                    })

        current_id = final_ai_message.id if final_ai_message else None
        if reconstructed_tool_calls_list:
            final_ai_message = AIMessage(content=full_response_content, tool_calls=reconstructed_tool_calls_list, id=current_id)
        elif final_ai_message: # No tool calls, but we have content
             final_ai_message = AIMessage(content=full_response_content, id=current_id)
        else: # Stream was empty or only had non-AIMessageChunks
            logger.warning("Planner stream was empty or yielded no processable AIMessageChunks.")
            final_ai_message = AIMessage(content="") 

    logger.info(f"Planner node aggregated LLM response. Type: {type(final_ai_message)}")
    if isinstance(final_ai_message, AIMessage):
        logger.info(f"Aggregated AIMessage content: '{str(final_ai_message.content)[:200]}...'")
        if final_ai_message.tool_calls:
            logger.info(f"Aggregated AIMessage has tool_calls: {final_ai_message.tool_calls}")
        else:
            logger.info("Aggregated AIMessage has no tool_calls (planner will respond directly).")
            
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
    node_types_description = "可用的节点类型及其XML定义的参数 (参数名: 默认值):\\n"
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
                        node_types_description += f"- {node_type_name} (参数: {', '.join(node_params_list)})\\n"
                    else:
                        node_types_description += f"- {node_type_name} (无XML中定义的参数或解析失败)\\n"
                    available_node_types_count +=1
            if available_node_types_count == 0:
                node_types_description += " (当前未在XML中定义特定的节点类型)\\n"
        else:
            node_types_description += f" (警告：节点定义目录 {xml_node_dir} 未找到)\\n"
    except Exception as e:
        logging.error(f"准备NODE_TYPES_INFO时出错: {e}")
        node_types_description += f" (获取节点类型信息时出错: {str(e)})\\n"
    
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
        system_prompt_template_for_planner = f"You are a helpful assistant with access to the following tools: {rendered_tools_desc}. Use these tools to help the user.\\nAvailable node types:\\n{node_types_description}"
    
    # Create the workflow graph
    workflow = StateGraph(AgentState)
    
    # 使用partial创建固定参数的函数
    # 创建一个已绑定参数的planner_node函数
    bound_planner_node = partial(
        planner_node, 
        llm=llm, 
        tools=tools_to_use, 
        system_message_template=system_prompt_template_for_planner
    )
    
    # 创建一个已绑定参数的tool_node函数
    bound_tool_node = partial(
        tool_node,
        tools=tools_to_use
    )
    
    # 正确添加节点 - 不使用kwargs参数
    workflow.add_node("planner", bound_planner_node) # Renamed "agent" to "planner"
    workflow.add_node("tools", bound_tool_node)
    
    # Set the entry point - start with the planner
    workflow.set_entry_point("planner") # Renamed "agent" to "planner"
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "planner", # Renamed "agent" to "planner"
        should_continue,
        {
            "tools": "tools",  # If planner wants to use a tool, route to tools node
            END: END,          # If planner is done, end the workflow
        }
    )
    
    # Add edge from tools back to planner (after tool execution, return to planner)
    workflow.add_edge("tools", "planner") # Renamed "agent" to "planner"
    
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