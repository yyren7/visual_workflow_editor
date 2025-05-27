from typing import Literal
from pydantic import BaseModel, Field

# 定义输出模式，LLM 需要根据这个模式来决定路由
class RouteDecision(BaseModel):
    """用户的意图以及相应的路由目标。"""
    user_intent: str = Field(description="对用户输入的简要总结或分类。")
    next_node: Literal["planner", "teaching", "other_assistant", "rephrase", "end_session"] = Field(
        description="根据用户意图，决定下一个要跳转到的节点。"
    ) 