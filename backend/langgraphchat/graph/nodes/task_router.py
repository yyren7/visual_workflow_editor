import logging
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
# from pydantic import BaseModel, Field # RouteDecision is now imported

from ..agent_state import AgentState
# from ..graph.conditions import RouteDecision # Import RouteDecision from conditions
from ..graph_types import RouteDecision # Corrected import path

logger = logging.getLogger(__name__)

# --- 节点描述定义 ---
ROUTER_INTRO = """你是一个任务路由助手。你需要分析用户的输入，并根据以下节点定义将其路由到最合适的节点。
请严格遵守每个节点的描述和主要职责，特别是 'teaching' 节点的首要规则。"""

PLANNER_DESCRIPTION = """用户想要创建、修改、删除流程图的节点、边，或者通过描述一系列动作或逻辑来构建一个机器人执行流程，或者询问与流程图结构相关的问题。
**只有当用户的核心意图是构建或修改一个序列化的机器人动作流程时，才选择此项。**"""
PLANNER_EXAMPLES = """
    一些例子包括：
    - "创建一个开始节点"
    - "将节点A连接到节点B"
    - "删除那个判断节点"
    - "流程图现在是什么样的？"
    - "首先让机器人移动到P1，然后夹取工件，接着移动到P2并放置工件。"
    - "如果传感器检测到物体，就执行操作A，否则执行操作B。"
    - "先依次运动到点1、点2、点3，然后重复抓取和放置的动作5次。"
    - "点2、3、1の順で運動させ、その後、点4、5、6の順で循環運動させてください。" (按点2、3、1的顺序运动，然后按点4、5、6的顺序循环运动)"""

TEACHING_PRIORITY_RULES = """**重要：会话模式持续性与 teaching 节点优先**
- **首要规则：当用户输入包含明确的"示教点相关名词"（如 "坐标/coordinate(s)", "点/point(s)", "位置/position", "示教点/teaching point"）与明确的"操作性动词"（如 "查询/query/get/tell me/what is/what are", "列出/list/show", "获取/fetch", "保存/save/record", "修改/update/change", "删除/delete/remove", "创建/create"）的组合时，无论表达方式如何，均必须将 `next_node` 判断为 `teaching`。此规则的优先级最高，除非用户明确表示要用这些点来构建一个序列化的机器人动作流程（此时应判断为 `planner`）。**
- 特别注意代词引用："它们(them)"、"这些点(these points)"、"那些(those)"等，如果上下文中刚讨论过示教点，则后续操作通常指向 `teaching`。
- 涉及坐标、位置、点位查询的模糊表达，优先考虑 teaching 节点。"""

TEACHING_DESCRIPTION = """用户主要目的是查询、保存、修改或删除单个或多个已命名的坐标点 (示教点) 的信息，包括坐标数据的查看和管理，而不是用它们来构建复杂流程。"""
TEACHING_EXAMPLES = """
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
    注意：如果用户在描述流程时提到了点位（例如"移动到P1"），但主要意图是构建流程，则应归类为 planner。"""

OTHER_ASSISTANT_DESCRIPTION = """**此节点严格用于处理与系统本身能力、使用方法、交互方式相关的咨询，或不涉及具体数据操作和流程构建的通用闲聊。**
如果用户的请求涉及对任何一种具体数据（如示教点、流程图元素）的查询、修改、创建或删除，则不应路由到 `other_assistant`。
只有在明确询问系统能力或进行无关闲聊时才路由到 `other_assistant`。"""
OTHER_ASSISTANT_EXAMPLES = """
    例如："你能做什么？", "我应该怎么告诉你创建流程图？", "你好", "今天天气怎么样？"
"""

END_SESSION_DESCRIPTION = """用户明确表示想要结束当前的对话或任务。"""
END_SESSION_EXAMPLES = """
    例如："结束吧", "退出", "就这样了", "谢谢，再见"
"""

REPHRASE_CONDITION = """如果用户的输入不属于以上定义的任何一种节点，或者意图不明确，无法根据节点描述清晰判断，请将任务分类为 **重新输入 (rephrase)**，并提示用户更清晰地描述他们的需求。"""

FEW_SHOT_EXAMPLES = """**输入示例与预期输出（用于学习）：**

*   用户输入: "请告诉我P2点的坐标。"
    预期分析：{{\\"user_intent\\": \\"查询P2点坐标\\", \\"next_node\\": \\"teaching\\"}}

*   用户输入: "保存当前位置为\'出口\'"
    预期分析：{{\\"user_intent\\": \\"保存当前位置为\'出口\'\\", \\"next_node\\": \\"teaching\\"}}

*   用户输入: "你能帮我创建流程图吗？"
    预期分析：{{\\"user_intent\\": \\"询问创建流程图的方法\\", \\"next_node\\": \\"other_assistant\\"}}

*   用户输入: "显示所有点的名称和位置"
    预期分析：{{\\"user_intent\\": \\"显示所有点的名称和位置\\", \\"next_node\\": \\"teaching\\"}}

*   用户输入: "那些点的坐标是什么"
    预期分析：{{\\"user_intent\\": \\"查询那些点的坐标\\", \\"next_node\\": \\"teaching\\"}} (假设上下文中\\"那些点\\"指代示教点)

*   User Input: "tell me the coordinates of point P10 and P12"
    Expected Analysis: {{\"user_intent\": \"Query coordinates of P10 and P12\", \"next_node\": \"teaching\"}}

*   User Input: "save current robot position as \'safe_exit\'"
    Expected Analysis: {{\"user_intent\": \"Save current position as \'safe_exit\'\", \"next_node\": \"teaching\"}}

*   User Input: "what can you do for me?"
    Expected Analysis: {{\"user_intent\": \"Inquire about system capabilities\", \"next_node\": \"other_assistant\"}}

*   User Input: "Show me all points that have a name."
    Expected Analysis: {{\"user_intent\": \"List all points with names\", \"next_node\": \"teaching\"}}

*   User Input: "delete the point named \'temp_spot\'"
    Expected Analysis: {{\"user_intent\": \"Delete point \'temp_spot\'\", \"next_node\": \"teaching\"}}

*   用户输入: "创建一个流程，让机器人先到P1，然后到P2，再回到P1"
    预期分析：{{\\"user_intent\\": \\"创建P1-P2-P1的往返流程\\", \\"next_node\\": \\"planner\\"}}

*   User Input: "add a new node to my current workflow"
    Expected Analysis: {{\"user_intent\": \"Add new node to workflow\", \"next_node\": \"planner\"}}

*   用户输入: "你好，你是谁？"
    预期分析：{{\\"user_intent\\": \\"询问AI身份\\", \\"next_node\\": \\"other_assistant\\"}}

*   User Input: "How do I use the teaching points in a flow?"
    Expected Analysis: {{\"user_intent\": \"Ask how to use teaching points in a flow\", \"next_node\": \"other_assistant\"}} (This is about usage/how-to, not direct data op)

*   用户输入: "机器人先移动到P5，然后执行夹取，再移动到P6。"
    预期分析：{{\\"user_intent\\": \\"创建P5-夹取-P6的流程\\", \\"next_node\\": \\"planner\\"}}
"""

# 定义输出模式，LLM 需要根据这个模式来决定路由
# class RouteDecision(BaseModel):
#     """用户的意图以及相应的路由目标。"""
#     user_intent: str = Field(description="对用户输入的简要总结或分类。")
#     next_node: Literal["planner", "teaching", "other_assistant", "rephrase", "end_session"] = Field(
#         description="根据用户意图，决定下一个要跳转到的节点。"
#     )

TASK_ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""{ROUTER_INTRO}

以下是各个可用节点的定义和主要职责：

1.  **流程图编辑 (planner)**:
{PLANNER_DESCRIPTION}{PLANNER_EXAMPLES}

2.  **示教点操作 (teaching)**:
{TEACHING_DESCRIPTION}
{TEACHING_PRIORITY_RULES}
{TEACHING_EXAMPLES}

3.  **其他助手 (other_assistant)**:
{OTHER_ASSISTANT_DESCRIPTION}{OTHER_ASSISTANT_EXAMPLES}

4.  **结束会话 (end_session)**:
{END_SESSION_DESCRIPTION}{END_SESSION_EXAMPLES}

{REPHRASE_CONDITION}

{FEW_SHOT_EXAMPLES}

根据你的判断，填充 'user_intent' 字段，总结用户的意图，并在 'next_node' 字段中指定下一个节点的名称。"""
        ),
        ("human", "用户输入：\\n{input}\\n\\n你的分析和路由决策："),
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
        logger.info(f"Task Router: Processing user_request_for_router: \'{user_input_to_process[:100]}...\'")
        effective_input_for_llm = user_input_to_process
        
    else:
        logger.info("Task Router: No 'user_request_for_router' found in state. Constructing input for LLM to decide based on context.")
        effective_input_for_llm = (
            "当前无新的用户直接输入。请回顾整个对话历史（如果对您可见），并根据对话的整体上下文和您的任务路由指令（将用户意图分类到"
            " 'planner', 'teaching', 'other_assistant', 'end_session' 或 'rephrase'），来决定最合适的下一步。"
            "如果对话历史不足或不明确，或者需要用户进一步澄清，请选择 'rephrase'。"
            "如果认为对话应结束，则选择 'end_session'。"
        )

    prompt_messages = TASK_ROUTER_PROMPT.format_messages(input=effective_input_for_llm)
    
    structured_llm = llm.with_structured_output(RouteDecision)
    
    try:
        history_messages = list(state.get("messages", []))
        messages_for_llm_invocation = history_messages + prompt_messages
        
        route_decision: RouteDecision = await structured_llm.ainvoke(messages_for_llm_invocation)
        logger.info(f"Task Router: LLM decision: Intent='{route_decision.user_intent}', Next Node='{route_decision.next_node}'")
        
        return {"task_route_decision": route_decision, "user_request_for_router": None}

    except Exception as e:
        logger.error(f"Task Router: Error invoking LLM or processing decision: {e}")
        return {
            "task_route_decision": RouteDecision(user_intent="LLM调用或决策处理失败", next_node="rephrase"),
            "user_request_for_router": None
        } 