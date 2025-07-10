# ---- START PATCH FOR DIRECT EXECUTION ----
if __name__ == '__main__' and (__package__ is None or __package__ == ''):
    import sys
    from pathlib import Path
    # Calculate the path to the project root ('/workspace')
    # This file is backend/langgraphchat/graph/workflow_graph.py
    # Relative path from this file to /workspace is ../../../.. (4 levels up)
    project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Set __package__ to the expected package name for relative imports to work
    # The package is 'backend.langgraphchat.graph'
    __package__ = "backend.langgraphchat.graph"
# ---- END PATCH FOR DIRECT EXECUTION ----

"""
定义和编译 LangGraph 工作流图。

该模块负责构建用于处理聊天交互、管理状态以及调用工具（特别是与流程图操作相关的工具）的 LangGraph 状态图。

它定义了图的结构（节点、边、入口点、条件路由），并将具体的节点实现逻辑委托给其他模块。

提供了一个编译函数 `compile_workflow_graph` 来创建可执行的图实例。

"""

# Input-》advisor-》planner-》parameter-》
# exhibitor-》code generator-》code combination

from typing import List, Optional
from pathlib import Path # Added
from dotenv import load_dotenv # Added
from datetime import datetime, timezone # Added

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from langchain_core.prompts import SystemMessagePromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, render_text_description
from langchain_core.runnables import RunnableConfig

from .agent_state import AgentState
from ..prompts.chat_prompts import STRUCTURED_CHAT_AGENT_PROMPT # For system prompt content
from ..prompts.dynamic_prompt_utils import get_dynamic_node_types_info
from ..tools import flow_tools # This should be the List[BaseTool]
from langchain_google_genai import ChatGoogleGenerativeAI # Added
from langchain_openai import ChatOpenAI # Added
from langsmith import Client as LangSmithClient # Added
from langsmith.utils import LangSmithNotFoundError # Added

import logging
import os # Make sure os is imported for listing files
import xml.etree.ElementTree as ET
import json
from functools import partial
import asyncio # <-- Added import
from langchain_core.language_models.fake_chat_models import FakeListChatModel # <-- Added import

# 导入工具，LLM, ChatService 等将在此处添加
# from ...app.services.chat_service import ChatService # 路径可能需要调整
# from ..tools.flow_tools import ... # 具体的工具或工具列表

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables from .env file at the module level
load_dotenv()

# 获取日志记录器
logger = logging.getLogger(__name__)

# --- 导入节点和条件逻辑实现 --- (这部分应该在 logger 定义之后)
from .nodes.input_handler import input_handler_node # Will be used
# from .nodes.planner import planner_node # 旧的 planner，将被移除或替换
from .nodes.tool_executor import tool_node # Already configured to be used
from .nodes.task_router import task_router_node # Import RouteDecision if needed here, or ensure AgentState handles it
from .nodes.teaching_node import teaching_node
from .nodes.other_assistant_node import other_assistant_node # Changed from ask_info_node
from .nodes.rephrase_prompt_node import rephrase_prompt_node # <-- 新增导入
from .nodes.goodbye_node import handle_goodbye_node # <-- 新增导入
from .conditions import should_continue, route_after_task_router # RouteDecision is now in types
from .graph_types import RouteDecision # Import RouteDecision from types


# --- 新增：处理重新输入的节点（如果需要明确提示用户）---
# 这个节点可以用来向用户明确地发送"请重新输入"的消息
async def rephrase_request_node(state: AgentState) -> dict:
    """
    如果 task_router 决定需要用户重新澄清，这个节点可以添加一个提示消息。
    然后流程会通过路由到 END 来结束当前轮次，等待用户的新输入。
    """
    decision = state.get("task_route_decision")
    llm_summary = decision.user_intent if decision and hasattr(decision, 'user_intent') else "我不确定您的意思。"
    
    rephrase_message_content = f"抱歉，我不太理解您的请求：'{llm_summary}'。您能换个方式详细描述一下吗？"
    
    current_messages = state.get("messages", [])
    current_messages.append(AIMessage(content=rephrase_message_content, id=f"ai_rephrase_{len(current_messages)}"))

    logger.info(f"Rephrase request: Prompting user to rephrase. Summary of unclear intent: {llm_summary}")
    
    return {"messages": current_messages}

def route_after_functional_node(state: AgentState) -> str:
    """
    在功能节点执行完毕后进行路由。
    """
    logger.info("--- Routing after Functional Node.")
    
    # 简单的功能节点完成后，重置任务上下文并结束
    logger.info("Functional node completed. Resetting task context.")
    state["task_route_decision"] = None
    state["user_request_for_router"] = None
    state["is_suspended"] = False
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
    tools_to_use = custom_tools if custom_tools is not None else flow_tools # tools_to_use is for the old planner's tool_node
    # The new robot_flow_invoker_node and its subgraph will manage their own tools.
    # So, `tools_to_use` and related system prompt parts might be less relevant for the main graph's planner path.
    # However, if other parts of the main graph use tools, this remains necessary.
    # For now, we keep it as is, as the `tool_node` is still part of the graph, though not directly after the new planner.

    # --- 准备 Planner 的系统提示模板 (这部分是为旧 planner 准备的) ---
    # 如果新的 robot_flow_invoker_node 不需要特定的系统提示模板注入，
    # 或者它内部处理自己的提示，这部分可能不再直接用于 "planner" 路径。
    # 暂时保留，以防其他节点可能间接使用。
    if not (STRUCTURED_CHAT_AGENT_PROMPT.messages and
            isinstance(STRUCTURED_CHAT_AGENT_PROMPT.messages[0], SystemMessagePromptTemplate) and
            hasattr(STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt, 'template')):
        logger.error("System prompt template structure is not as expected. Using a fallback.")
        raw_system_template = "You are a helpful assistant. Use the available tools if necessary. Context: {flow_context}"
    else:
        raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template

    rendered_tools_desc = render_text_description(tools_to_use if tools_to_use else []) # Handle empty tools_to_use
    tool_names_list_str = ", ".join([t.name for t in tools_to_use] if tools_to_use else [])

    try:
        node_types_description = get_dynamic_node_types_info()
    except Exception as e:
        logger.error(f"Error getting dynamic node types info: {e}")
        node_types_description = "(获取节点类型信息时出错)\\\\n"

    system_prompt_template_for_planner = raw_system_template # This might not be used by new invoker node
    placeholders_to_fill = {
        "{tools}": rendered_tools_desc,
        "{tool_names}": tool_names_list_str,
        "{NODE_TYPES_INFO}": node_types_description
    }
    for placeholder, value in placeholders_to_fill.items():
        if placeholder in system_prompt_template_for_planner:
            system_prompt_template_for_planner = system_prompt_template_for_planner.replace(placeholder, value)
        else:
            logger.warning(f"Placeholder \'{placeholder}\' not found in the system prompt template provided by STRUCTURED_CHAT_AGENT_PROMPT.")

    # --- 创建和配置 StateGraph ---
    workflow = StateGraph(AgentState)

    bound_input_handler_node = partial(input_handler_node)
    
    # 新节点绑定
    bound_task_router_node = partial(task_router_node, llm=llm) 
    bound_teaching_node = partial(teaching_node, llm=llm)
    bound_other_assistant_node = partial(other_assistant_node) # Changed from bound_ask_info_node and ask_info_node
    bound_rephrase_prompt_node = partial(rephrase_prompt_node) # <-- 新增绑定
    bound_handle_goodbye_node = partial(handle_goodbye_node) # <-- 新增绑定


    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("task_router", bound_task_router_node) 
    workflow.add_node("teaching", bound_teaching_node) 
    workflow.add_node("other_assistant", bound_other_assistant_node) # Changed from ask_info
    workflow.add_node("rephrase_prompt", bound_rephrase_prompt_node) # <-- 添加新节点
    workflow.add_node("handle_goodbye", bound_handle_goodbye_node) # <-- 添加新节点


    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边
    workflow.add_edge("input_handler", "task_router")

    # 从 task_router 出发的条件边
    workflow.add_conditional_edges(
        "task_router",
        route_after_task_router,
        {
            "teaching": "teaching",
            "other_assistant": "other_assistant", 
            "rephrase_prompt": "rephrase_prompt",  # 确保这里与 route_after_task_router 的返回字符串一致
            "handle_goodbye_node": "handle_goodbye", # 修改键名以匹配 conditions.py 的返回
            END: END 
        }
    )
    
    # 添加挂起状态节点
    workflow.add_node("SUSPENDED", lambda state: state)  # 空操作节点
    
    # 删除了robot_flow_planner相关的路由
    workflow.add_conditional_edges(
        "teaching",
        route_after_functional_node,
        {
            "input_handler": "input_handler", # Should not happen for simple nodes unless they can ask for clarification
            END: END # Normal completion routes to END
        }
    )
    workflow.add_conditional_edges(
        "other_assistant",
        route_after_functional_node,
        {
            "input_handler": "input_handler", # Should not happen for simple nodes
            END: END # Normal completion routes to END
        }
    )

    # 新增：从 rephrase_prompt 节点出来的边，固定到 END
    workflow.add_edge("rephrase_prompt", END)

    # 添加从挂起状态回到输入处理器的边
    workflow.add_edge("SUSPENDED", "input_handler")

    # 新增：从 goodbye 节点出来的边，固定到 END
    workflow.add_edge("handle_goodbye", END)

    # 编译图
    logger.info("Workflow graph compilation complete.")
    return workflow.compile()


async def interactive_workflow_runner():
    """交互式工作流运行器，支持多轮输入"""
    # 1. 初始化LLM
    llm: Optional[BaseChatModel] = None
    
    if os.getenv("GOOGLE_API_KEY"):
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-pro")
            llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, convert_system_message_to_human=True)
            logger.info(f"Using ChatGoogleGenerativeAI ({model_name}).")
        except Exception as e:
            logger.warning(f"Failed to initialize ChatGoogleGenerativeAI: {e}. Trying OpenAI.")
            llm = None
    
    if not llm and os.getenv("OPENAI_API_KEY"):
        try:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            logger.info("Using ChatOpenAI (gpt-3.5-turbo).")
        except Exception as e:
            logger.warning(f"Failed to initialize ChatOpenAI: {e}. Falling back to FakeListChatModel.")
            llm = None

    if not llm:
        # 使用预定义的响应
        fake_responses = [
            AIMessage(content=json.dumps({
                "decision": "planner",
                "user_intent": "ロボットタスクのためのプランナーにルーティングします。"
            })).model_dump_json(),
            AIMessage(content='タスクリストを生成しました。確認しますか？').model_dump_json(),
            AIMessage(content="了解しました。次のフェーズに進みます。").model_dump_json()
        ]
        llm = FakeListChatModel(responses=fake_responses)
        logger.info("Using FakeListChatModel with predefined responses.")

    # 2. 编译图
    logger.info("Compiling workflow graph for interactive session...")
    graph_app = compile_workflow_graph(llm=llm)
    logger.info("Workflow graph compiled.")

    # 3. 准备初始状态
    current_state = AgentState(
        input="ロボットは初期位置からベアリング（BRG）とベアリングハウジング（BH）を取得します。",
        messages=[HumanMessage(content="ロボットは初期位置からベアリング（BRG）とベアリングハウジング（BH）を取得します。", id="user_input_001")],
        flow_context={"interactive_mode": True},
        current_flow_id=f"interactive_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        input_processed=False,
        is_suspended=False  # 初始非挂起状态
    )
    
    while True:
        # 4. 执行图
        run_config = RunnableConfig(recursion_limit=100)
        async for state_update in graph_app.astream(current_state, config=run_config):
            current_state = state_update
        
        # 5. 检查是否挂起
        if current_state.get("is_suspended", False):
            print("\n--- Graph Suspended ---")
            print(f"Clarification needed: {current_state.get('clarification_question', 'No question provided')}")
            
            # 获取用户输入
            user_input = input("Your response: ")
            if user_input.lower() in ["exit", "quit"]:
                break
                
            # 更新状态继续处理
            current_state["input"] = user_input
            current_state["messages"].append(HumanMessage(content=user_input))
            current_state["input_processed"] = False
            current_state["is_suspended"] = False
        else:
            # 6. 显示最终结果
            print("\n--- Task Completed ---")
            for msg in current_state.get("messages", []):
                if isinstance(msg, AIMessage):
                    print(f"Assistant: {msg.content}")
            
            # 7. 开始新任务
            new_task = input("\nEnter new task (or 'exit' to quit): ")
            if new_task.lower() in ["exit", "quit"]:
                break
                
            # 8. 重置状态
            current_state = AgentState(
                input=new_task,
                messages=[HumanMessage(content=new_task)],
                flow_context={"interactive_mode": True},
                current_flow_id=f"interactive_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                input_processed=False,
                is_suspended=False
            )
    
    # 9. 清理资源
    if hasattr(llm, 'aclose'):
        await llm.aclose()

if __name__ == "__main__":
    asyncio.run(interactive_workflow_runner())
