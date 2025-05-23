import logging
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
# from pydantic import BaseModel, Field # RouteDecision is now imported

from ..agent_state import AgentState
# from ..graph.conditions import RouteDecision # Import RouteDecision from conditions
from ..graph_types import RouteDecision # Corrected import path

logger = logging.getLogger(__name__)

# 定义输出模式，LLM 需要根据这个模式来决定路由
# class RouteDecision(BaseModel):
#     """用户的意图以及相应的路由目标。"""
#     user_intent: str = Field(description="对用户输入的简要总结或分类。")
#     next_node: Literal["planner", "teaching", "ask_info", "rephrase", "end_session"] = Field(
#         description="根据用户意图，决定下一个要跳转到的节点。"
#     )

TASK_ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是一个任务路由助手。你需要分析用户的输入，并将其分类到以下几种任务中：
1.  **流程图编辑 (planner)**: 用户想要创建、修改、删除流程图的节点、边，或者通过描述一系列动作或逻辑来构建一个机器人执行流程，或者询问与流程图结构相关的问题。
    一些例子包括：
    - "创建一个开始节点"
    - "将节点A连接到节点B"
    - "删除那个判断节点"
    - "流程图现在是什么样的？"
    - "首先让机器人移动到P1，然后夹取工件，接着移动到P2并放置工件。"
    - "如果传感器检测到物体，就执行操作A，否则执行操作B。"
    - "先依次运动到点1、点2、点3，然后重复抓取和放置的动作5次。"
    - "点2、3、1の順で運動させ、その後、点4、5、6の順で循環運動させてください。" (按点2、3、1的顺序运动，然后按点4、5、6的顺序循环运动)

2.  **示教点操作 (teaching)**: 用户主要目的是查询、保存、修改或删除单个或多个已命名的坐标点 (示教点) 的信息，而不是用它们来构建复杂流程。
    例如："记录当前位置为P1", "P1的坐标是多少?", "更新P2到新的位置", "删除示教点Home", "查询所有示教点"
    注意：如果用户在描述流程时提到了点位（例如"移动到P1"），但主要意图是构建流程，则应归类为 planner。

3.  **信息咨询 (ask_info)**: 用户在询问你的能力、工作范围、如何与你交互，或者寻求一般性的帮助和建议，或者进行无明确任务的闲聊。
    例如："你能做什么？", "我应该怎么告诉你创建流程图？", "你好", "今天天气怎么样？"

4.  **结束会话 (end_session)**: 用户明确表示想要结束当前的对话或任务。
    例如："结束吧", "退出", "就这样了", "谢谢，再见"

如果用户的输入不属于以上四类，或者意图不明确，请将任务分类为 **重新输入 (rephrase)**，并提示用户更清晰地描述他们的需求。

根据你的判断，填充 'user_intent' 字段，总结用户的意图，并在 'next_node' 字段中指定下一个节点的名称。""",
        ),
        ("human", "用户输入：\n{input}\n\n你的分析和路由决策："),
    ]
)

async def task_router_node(state: AgentState, llm: BaseChatModel) -> dict:
    """
    使用 LLM 分析用户输入或当前对话状态，决定下一个节点。
    如果 state['user_request_for_router'] 有内容，则优先使用它作为LLM判断的主要依据。
    如果为空（例如，节点执行完毕后返回此router），则LLM根据对话历史和上下文判断。
    处理后会清除 state['user_request_for_router']。
    """
    logger.info("Task Router: Entered node.")
    user_input_to_process = state.get("user_request_for_router")
    
    effective_input_for_llm: str
    if user_input_to_process:
        logger.info(f"Task Router: Processing user_request_for_router: '{user_input_to_process[:100]}...'")
        effective_input_for_llm = user_input_to_process
    else:
        logger.info("Task Router: No 'user_request_for_router' found in state. Constructing input for LLM to decide based on context.")
        # 这个占位符会作为 TASK_ROUTER_PROMPT 中 {input} 变量的值。
        # 系统提示已指导LLM如何分类。此占位符提示LLM在无直接新输入时如何行动。
        effective_input_for_llm = (
            "当前无新的用户直接输入。请回顾整个对话历史（如果对您可见），并根据对话的整体上下文和您的任务路由指令（将用户意图分类到"
            " 'planner', 'teaching', 'ask_info', 'end_session' 或 'rephrase'），来决定最合适的下一步。"
            "如果对话历史不足或不明确，或者需要用户进一步澄清，请选择 'rephrase'。"
            "如果认为对话应结束，则选择 'end_session'。"
        )

    # TASK_ROUTER_PROMPT 包含一个系统消息和一个人类消息模板（需要填充 {input}）。
    # format_messages 会生成一个 BaseMessage 列表。
    prompt_messages = TASK_ROUTER_PROMPT.format_messages(input=effective_input_for_llm)
    
    structured_llm = llm.with_structured_output(RouteDecision)
    
    try:
        # 获取完整的对话历史
        history_messages = list(state.get("messages", []))
        
        # current_prompt_parts 本身就是 TASK_ROUTER_PROMPT.format_messages 的结果，
        # 它是一个列表，通常包含一个 SystemMessage 和一个 HumanMessage。
        # 我们将历史消息放在前面，然后是当前的路由提示。
        # 注意：如果历史消息中已经包含了与路由相关的旧提示，需要考虑是否会混淆LLM。
        #      对于结构化输出，通常LLM只关注最后的用户指令和其被告知的输出格式。
        #      为安全起见，可以考虑仅将最新的几条历史消息传入，或者确保
        #      TASK_ROUTER_PROMPT 的系统消息足够强势以覆盖旧指令。
        #      目前，我们先尝试传递完整的历史。
        
        messages_for_llm_invocation = history_messages + prompt_messages
        
        route_decision: RouteDecision = await structured_llm.ainvoke(messages_for_llm_invocation)
        logger.info(f"Task Router: LLM decision: Intent='{route_decision.user_intent}', Next Node='{route_decision.next_node}'")
        
        # 无论如何，清除 user_request_for_router，因为它已被处理或本次不需要。
        return {"task_route_decision": route_decision, "user_request_for_router": None}

    except Exception as e:
        logger.error(f"Task Router: Error invoking LLM or processing decision: {e}")
        # 出现错误时，安全回退到 "rephrase"
        return {
            "task_route_decision": RouteDecision(user_intent="LLM调用或决策处理失败", next_node="rephrase"),
            "user_request_for_router": None # 同样清除
        } 