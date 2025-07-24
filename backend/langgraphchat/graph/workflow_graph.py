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

采用"一问一答"的中心化路由模式：
- 用户输入 -> input_handler -> task_router (中心枢纽) -> 各功能节点 -> END
- 每次用户输入对应一次图执行，状态通过 AgentState 持久化
- 功能节点完成任务后直接结束，不再循环路由

提供了一个编译函数 `compile_workflow_graph` 来创建可执行的图实例。
"""

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


# Graph compilation
def compile_workflow_graph(llm: BaseChatModel, custom_tools: List[BaseTool] = None):
    """
    编译并返回 LangGraph 工作流图实例。
    
    采用中心化的"一问一答"路由模式：
    1. 用户输入 -> input_handler (处理输入) -> task_router (智能路由中心)
    2. task_router 根据用户意图路由到对应功能节点
    3. 功能节点完成任务后直接到 END，结束本次图执行
    4. 下次用户输入时，重新开始一个新的图执行流程

    Args:
        llm: 用于节点的 BaseChatModel 实例。
        custom_tools: 可选的工具列表。如果提供，则使用这些工具；否则使用默认的 `flow_tools`。

    Returns:
        一个已编译的 LangGraph 工作流图实例。
    """
    logger.info("Compiling workflow graph with centralized routing pattern...")

    # 确定要使用的工具集
    tools_to_use = custom_tools if custom_tools is not None else (flow_tools or [])

    # --- 准备系统提示模板 (保留以备将来可能的 planner 节点使用) ---
    try:
        if (STRUCTURED_CHAT_AGENT_PROMPT.messages and
                isinstance(STRUCTURED_CHAT_AGENT_PROMPT.messages[0], SystemMessagePromptTemplate)):
            raw_system_template = STRUCTURED_CHAT_AGENT_PROMPT.messages[0].prompt.template
        else:
            raise ValueError("Invalid prompt structure")
    except (AttributeError, ValueError, IndexError):
        logger.error("System prompt template structure is not as expected. Using a fallback.")
        raw_system_template = "You are a helpful assistant. Use the available tools if necessary. Context: {flow_context}"

    rendered_tools_desc = render_text_description(tools_to_use if tools_to_use else [])
    tool_names_list_str = ", ".join([t.name for t in tools_to_use] if tools_to_use else [])

    try:
        node_types_description = get_dynamic_node_types_info()
    except Exception as e:
        logger.error(f"Error getting dynamic node types info: {e}")
        node_types_description = "(获取节点类型信息时出错)\\\\n"

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
            logger.warning(f"Placeholder \'{placeholder}\' not found in the system prompt template provided by STRUCTURED_CHAT_AGENT_PROMPT.")

    # --- 创建和配置 StateGraph ---
    workflow = StateGraph(AgentState)

    # 绑定节点函数 (使用 partial 传递必要参数)
    bound_input_handler_node = partial(input_handler_node)
    bound_task_router_node = partial(task_router_node, llm=llm) 
    bound_teaching_node = partial(teaching_node, llm=llm)
    bound_other_assistant_node = partial(other_assistant_node)
    bound_rephrase_prompt_node = partial(rephrase_prompt_node)
    bound_handle_goodbye_node = partial(handle_goodbye_node)

    # 添加节点到图
    workflow.add_node("input_handler", bound_input_handler_node)
    workflow.add_node("task_router", bound_task_router_node) 
    workflow.add_node("teaching", bound_teaching_node) 
    workflow.add_node("other_assistant", bound_other_assistant_node)
    workflow.add_node("rephrase_prompt", bound_rephrase_prompt_node)
    workflow.add_node("handle_goodbye", bound_handle_goodbye_node)

    # 设置图的入口点
    workflow.set_entry_point("input_handler")

    # 定义节点间的边 - 采用中心化路由模式
    workflow.add_edge("input_handler", "task_router")

    # 从 task_router (中心枢纽) 出发的条件边
    workflow.add_conditional_edges(
        "task_router",
        route_after_task_router,
        {
            "teaching": "teaching",
            "other_assistant": "other_assistant", 
            "rephrase_prompt": "rephrase_prompt",
            "handle_goodbye_node": "handle_goodbye",
            END: END 
        }
    )
    
    # 所有功能节点完成任务后直接到 END
    # 这样每次用户输入只对应一次图执行，简化了流程
    workflow.add_edge("teaching", END)
    workflow.add_edge("other_assistant", END)
    workflow.add_edge("rephrase_prompt", END)
    workflow.add_edge("handle_goodbye", END)

    # 编译图
    logger.info("Workflow graph compilation complete. Using centralized routing pattern.")
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
        task_route_decision=None,
        user_request_for_router=None,
        rephrase_count=0
    )
    
    while True:
        # 4. 执行图
        run_config = RunnableConfig(recursion_limit=25)
        async for state_update in graph_app.astream(current_state, config=run_config):
            current_state = state_update
        
        # 5. 显示最终结果
        print("\n--- Task Completed ---")
        for msg in current_state.get("messages", []):
            if isinstance(msg, AIMessage):
                print(f"Assistant: {msg.content}")
        
        # 6. 开始新任务
        new_task = input("\nEnter new task (or 'exit' to quit): ")
        if new_task.lower() in ["exit", "quit"]:
            break
            
        # 7. 为新的用户输入重置状态，但保留对话历史
        # 这样 task_router 可以根据历史上下文做出更好的路由决策
        current_messages = current_state.get("messages", [])
        current_messages.append(HumanMessage(content=new_task))
        
        current_state = AgentState(
            input=new_task,
            messages=current_messages,  # 保留历史对话
            flow_context={"interactive_mode": True},
            current_flow_id=current_state.get("current_flow_id", f"interactive_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"),
            input_processed=False,
            task_route_decision=None,
            user_request_for_router=None,
            rephrase_count=0
        )
    
    # 8. 清理资源
    try:
        if hasattr(llm, 'aclose'):
            await llm.aclose()
    except Exception as e:
        logger.warning(f"Error closing LLM: {e}")

if __name__ == "__main__":
    asyncio.run(interactive_workflow_runner())
