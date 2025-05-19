from typing import List, TypedDict, Optional, Any, Annotated
from langchain_core.messages import BaseMessage
import operator

# from .conditions import RouteDecision # RouteDecision is now in conditions.py
from .types import RouteDecision # RouteDecision is now in types.py

# 为了与 LangGraph 兼容，并让我们可以添加任意数量的键，
# 我们将基础状态类定义为 TypedDict，然后使用它来注解 StateGraph。
# TypedDict 的一个好处是，我们可以为每个键定义一个类型，
# 并且 LangGraph 会在更新状态时验证这些类型。

# 此外，LangGraph 还允许我们为状态中的每个键定义一个更新策略。
# 这意味着我们可以定义当一个键被多次更新时会发生什么。
# 例如，我们可以让 chat_history 累积（append），或者让 input 被覆盖（replace）。
# 默认情况下，键会被覆盖（replace）。

# 我们将 chat_history 和 intermediate_steps 合并到 messages 字段中。
# LangGraph 的许多预构建组件（如 ToolExecutor 和基于 MessagesState 的 Agent）
# 都期望一个 messages 列表，其中包含 AIMessage（含 tool_calls）和 ToolMessage。
# operator.add 将确保新的消息被追加到现有消息列表中。

class AgentState(TypedDict):
    """
    表示 LangGraph Agent 的状态。

    属性:
        input: 用户的当前输入。
        messages: 包含 BaseMessage 对象的对话历史和中间步骤（工具调用和工具结果）的列表。
                  新的消息会被追加到这个列表。
        flow_context: 当前流程图的上下文信息，可以是任意结构。
        current_flow_id: 当前操作的流程图 ID。
        input_processed: 一个布尔标志，指示 state.input 是否已被处理并合并到 messages 中。默认为 False。
        # agent_outcome 字段可以移除，因为最终的 Agent 回复也会是 messages 列表中的一个 AIMessage。
        # 工具调用信息将直接存在于 AIMessage 的 tool_calls 属性中。

        # 新增字段，用于存储 task_router 节点的决策结果
        task_route_decision: Optional[RouteDecision]
        user_request_for_router: Optional[str] # 新增：专门用于task_router处理的用户请求内容
    """
    input: str
    messages: Annotated[List[BaseMessage], operator.add]
    flow_context: Any
    current_flow_id: str
    input_processed: bool
    task_route_decision: Optional[RouteDecision]
    user_request_for_router: Optional[str] # 新增 