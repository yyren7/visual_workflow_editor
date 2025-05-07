from typing import List
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description

from .agent_state import AgentState
from ..prompts.chat_prompts import STRUCTURED_CHAT_AGENT_PROMPT # For system prompt content
from ..tools import flow_tools # This should be the List[BaseTool]
from ..context import current_flow_id_var # Context variable for flow_id

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
async def agent_node(state: AgentState, llm: BaseChatModel, tools: List[BaseTool], system_message_template: str) -> dict:
    """
    Invokes the LLM agent to decide on the next step.
    """
    # Ensure tools are bound to the LLM for tool calling
    llm_with_tools = llm.bind_tools(tools)

    # Format the system message with the current flow_context
    # The 'tools' and 'tool_names' for the prompt template itself are static parts of the system message.
    # We get the tool descriptions and names once to format the system_message_template.
    # This part of the system message template should already have {tools} and {tool_names} if needed by the base prompt.
    # For this implementation, we assume system_message_template is the fully prepared system prompt string
    # that might take flow_context.
    
    # For STRUCTURED_CHAT_AGENT_PROMPT, the system part is messages[0].prompt.template
    # It expects {tools}, {tool_names}, {flow_context}
    # rendered_tools_desc = render_text_description(tools) # Render full tool descriptions
    # tool_names_list = ", ".join([t.name for t in tools])
    # system_prompt_content = system_message_template.format(
    #     tools=rendered_tools_desc,
    #     tool_names=tool_names_list,
    #     flow_context=state.get("flow_context", {}) # Ensure flow_context is not None
    # )
    # The above formatting assumes system_message_template is the raw string from STRUCTURED_CHAT_AGENT_PROMPT.
    # A simpler approach is to pre-format the system_message_template in compile_workflow_graph once.
    # Let's assume system_message_template is passed in already partially formatted with tools/tool_names.
    
    final_system_message = system_message_template.format(flow_context=state.get("flow_context", {}))

    prompt_messages: List[BaseMessage] = [SystemMessage(content=final_system_message)]
    
    # Add current user input if it's the last message and not yet processed by agent
    # Or, assume state["messages"] is the complete history ready for the LLM
    # If state["input"] is used, it should be converted to HumanMessage and added.
    # For this structure, we expect state["messages"] to be the primary driver.
    # If the graph is invoked with {"messages": [HumanMessage(...)]}, then state["input"] might be redundant.
    
    current_log = list(state["messages"]) # Make a copy

    # If 'input' field is used and is different from the last message, append it.
    # This logic depends on how the graph is invoked and updated.
    # A common pattern is to ensure the 'input' is added to 'messages' before calling the agent.
    # For simplicity, let's assume 'messages' contains the full history needed by the LLM.
    # If state['input'] is meant to be the *very latest* user utterance not yet in messages:
    if state.get("input"):
         # Check if the input is already the content of the last HumanMessage
        is_new_input = True
        if current_log and isinstance(current_log[-1], HumanMessage) and current_log[-1].content == state["input"]:
            is_new_input = False
        
        if is_new_input:
            current_log.append(HumanMessage(content=state["input"]))

    prompt_messages.extend(current_log)

    # 使用 await 获取 AI 响应，确保不会返回协程对象
    ai_response = await llm_with_tools.ainvoke(prompt_messages)
    
    # 处理JSON格式的回复，提取action_input内容
    import re
    import json
    import logging
    logger = logging.getLogger(__name__)
    
    if isinstance(ai_response, AIMessage) and ai_response.content:
        content = ai_response.content
        # 检查是否是JSON格式的响应
        if "```json" in content and '"action": "final_answer"' in content:
            try:
                # 提取JSON部分
                json_match = re.search(r'{.*}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed = json.loads(json_str)
                    if parsed.get("action") == "final_answer" and "action_input" in parsed:
                        # 替换为实际回复内容
                        logger.info(f"提取JSON中的action_input作为实际回复: {parsed['action_input'][:100]}...")
                        ai_response.content = parsed["action_input"]
            except Exception as e:
                logger.warning(f"解析JSON回复失败: {str(e)}")
    
    # The AIMessage itself is the outcome, to be added to the messages list
    return {"messages": [ai_response]}

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
    Determines the next step after the agent node.
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
    # This system message will be formatted with flow_context dynamically in the agent_node.
    # The {tools} and {tool_names} parts are static based on the tools provided.
    raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template
    
    rendered_tools_desc = render_text_description(tools_to_use)
    tool_names_list_str = ", ".join([t.name for t in tools_to_use])
    
    # Partially format the system prompt with tool info. Flow_context will be added per call.
    # This assumes the template string has {tools}, {tool_names}, and {flow_context}
    try:
        # Attempt to format with all known static placeholders for the system prompt
        # The dynamic placeholder {flow_context} will be handled in the agent_node
        system_prompt_template_for_agent = raw_system_template.replace("{tools}", rendered_tools_desc).replace("{tool_names}", tool_names_list_str)
    except Exception as e:
        # If formatting fails, use a simpler approach
        system_prompt_template_for_agent = f"You are a helpful assistant with access to the following tools: {rendered_tools_desc}. Use these tools to help the user."
    
    # Create the workflow graph
    workflow = StateGraph(AgentState)
    
    # 使用partial创建固定参数的函数
    # 创建一个已绑定参数的agent_node函数
    bound_agent_node = partial(
        agent_node, 
        llm=llm, 
        tools=tools_to_use, 
        system_message_template=system_prompt_template_for_agent
    )
    
    # 创建一个已绑定参数的tool_node函数
    bound_tool_node = partial(
        tool_node,
        tools=tools_to_use
    )
    
    # 正确添加节点 - 不使用kwargs参数
    workflow.add_node("agent", bound_agent_node)
    workflow.add_node("tools", bound_tool_node)
    
    # Set the entry point - start with the agent
    workflow.set_entry_point("agent")
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",  # If agent wants to use a tool, route to tools node
            END: END,          # If agent is done, end the workflow
        }
    )
    
    # Add edge from tools back to agent (after tool execution, return to agent)
    workflow.add_edge("tools", "agent")
    
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