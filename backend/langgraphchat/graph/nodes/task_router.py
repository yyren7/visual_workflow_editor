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

**重要：会话模式持续性**
- 如果用户之前进行过示教点操作，并且当前输入涉及点位、坐标、位置等相关内容，应优先路由到 teaching 节点
- 特别注意代词引用："它们"、"them"、"这些点"、"那些"等通常指向之前讨论的示教点

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

2.  **示教点操作 (teaching)**: 用户主要目的是查询、保存、修改或删除单个或多个已命名的坐标点 (示教点) 的信息，包括坐标数据的查看和管理，而不是用它们来构建复杂流程。
    示教点操作的丰富例子包括：
    - "记录当前位置为P1" 
    - "P1的坐标是多少?" 
    - "更新P2到新的位置" 
    - "删除示教点Home"
    - "查询所有示教点"
    - "显示所有有名字的点的坐标" 
    - "列出P1到P5的详细信息"
    - "coordinate of these teaching points all which have names" (查询所有有名字的示教点的坐标)
    - "coordinate of them" (当上下文中讨论过示教点时)
    - "them" (当指向示教点时)
    - "these points" (这些点)
    - "那些点的坐标"
    - "它们的位置信息"
    - "showing me the coordinates of all defined points"
    - "给我看看有逻辑名称的点位信息"
    - "修改它的Z坐标为100" (基于上下文指代的点位操作)
    - "保存当前位置为新点home"
    - "删除它" (基于上下文指代的点位删除)
    - "P1, P2, P3的XYZ坐标分别是多少？"
    - "查询所有定义过的示教点的详细坐标信息"
    - "坐标" (当上下文讨论示教点时)
    - "coordinates" (当上下文讨论示教点时)
    - "位置信息" (当上下文讨论示教点时)
    注意：如果用户在描述流程时提到了点位（例如"移动到P1"），但主要意图是构建流程，则应归类为 planner。

3.  **信息咨询 (ask_info)**: 用户在询问你的能力、工作范围、如何与你交互，或者寻求一般性的帮助和建议，或者进行无明确任务的闲聊。
    例如："你能做什么？", "我应该怎么告诉你创建流程图？", "你好", "今天天气怎么样？"

4.  **结束会话 (end_session)**: 用户明确表示想要结束当前的对话或任务。
    例如："结束吧", "退出", "就这样了", "谢谢，再见"

如果用户的输入不属于以上四类，或者意图不明确，请将任务分类为 **重新输入 (rephrase)**，并提示用户更清晰地描述他们的需求。

**特别注意**：
- 如果用户使用代词（它们、them、这些、那些）且对话历史中提到过示教点，应路由到 teaching
- 涉及坐标、位置、点位查询的模糊表达，优先考虑 teaching 节点
- 只有在明确询问系统能力或进行无关闲聊时才路由到 ask_info

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
    
    **Teaching模式粘性**: 一旦进入teaching模式，除非明确表达退出意图，否则继续在teaching节点。
    """
    logger.info("Task Router: Entered node.")
    user_input_to_process = state.get("user_request_for_router")
    
    # Check if we're in teaching mode (has recent teaching node activity)
    messages = state.get("messages", [])
    is_in_teaching_mode = False
    recent_teaching_activity = False
    
    # Look for recent teaching node activity in the last few messages
    for i, msg in enumerate(reversed(messages[-10:])):  # Check last 10 messages
        if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs.get('node') == 'teaching':
            recent_teaching_activity = True
            is_in_teaching_mode = True
            logger.info(f"Task Router: Detected recent teaching activity at message index {len(messages) - 10 + i}")
            break
        # Stop checking if we encounter a non-teaching node activity
        elif hasattr(msg, 'additional_kwargs') and 'node' in msg.additional_kwargs:
            other_node = msg.additional_kwargs.get('node')
            if other_node not in ['teaching', 'task_router']:
                logger.info(f"Task Router: Found recent non-teaching activity: {other_node}")
                break
    
    effective_input_for_llm: str
    if user_input_to_process:
        logger.info(f"Task Router: Processing user_request_for_router: '{user_input_to_process[:100]}...'")
        effective_input_for_llm = user_input_to_process
        
        # Teaching mode stickiness: if in teaching mode and input doesn't suggest exit
        if is_in_teaching_mode:
            # Check for explicit exit intentions
            exit_keywords = ["退出", "结束", "exit", "quit", "done", "finish", "再见", "bye"]
            is_exit_intent = any(keyword in user_input_to_process.lower() for keyword in exit_keywords)
            
            # Check for other clear non-teaching intents
            planner_keywords = ["流程图", "节点", "连接", "workflow", "flow", "创建流程"]
            is_planner_intent = any(keyword in user_input_to_process.lower() for keyword in planner_keywords)
            
            info_keywords = ["你能做什么", "能力", "帮助", "how to", "what can you"]
            is_info_intent = any(keyword in user_input_to_process.lower() for keyword in info_keywords)
            
            if not is_exit_intent and not is_planner_intent and not is_info_intent:
                logger.info(f"Task Router: In teaching mode, input doesn't suggest exit. Staying in teaching.")
                return {
                    "task_route_decision": RouteDecision(
                        user_intent=f"继续示教点操作: {user_input_to_process[:50]}...",
                        next_node="teaching"
                    ),
                    "user_request_for_router": None
                }
            else:
                logger.info(f"Task Router: Exit intent detected or clear non-teaching intent, allowing normal routing.")
        
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
        
        # Post-process decision: if we detected teaching mode but LLM routed elsewhere,
        # consider overriding for certain ambiguous cases
        if is_in_teaching_mode and route_decision.next_node == "ask_info":
            # Check if the input seems to be about coordinates/points but was misrouted
            coordinate_keywords = ["coordinate", "coordinates", "坐标", "位置", "them", "它们", "these", "那些"]
            if any(keyword in effective_input_for_llm.lower() for keyword in coordinate_keywords):
                logger.info(f"Task Router: Overriding ask_info decision to teaching due to teaching mode + coordinate keywords")
                route_decision = RouteDecision(
                    user_intent=f"继续示教点坐标查询: {effective_input_for_llm[:50]}...",
                    next_node="teaching"
                )
        
        # 无论如何，清除 user_request_for_router，因为它已被处理或本次不需要。
        return {"task_route_decision": route_decision, "user_request_for_router": None}

    except Exception as e:
        logger.error(f"Task Router: Error invoking LLM or processing decision: {e}")
        # 出现错误时，安全回退到 "rephrase"
        return {
            "task_route_decision": RouteDecision(user_intent="LLM调用或决策处理失败", next_node="rephrase"),
            "user_request_for_router": None # 同样清除
        } 