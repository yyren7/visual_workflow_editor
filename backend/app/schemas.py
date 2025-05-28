from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    
    class Config:
        from_attributes = True

class NodeData(BaseModel):
    """
    Represents data for a node in the flow.
    Used for LLM API responses.
    """
    type: str
    data: Dict[str, Any]
    position: Optional[Dict[str, float]] = None

class FlowNodeBase(BaseModel):
    id: str
    type: str
    position: Dict[str, float]
    data: Dict[str, Any]

class FlowEdgeBase(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None

# 调整Flow相关模型以匹配models.py中的定义
class FlowBase(BaseModel):
    name: str

class FlowCreate(FlowBase):
    flow_data: Dict[str, Any] = {}

class FlowUpdate(BaseModel):
    name: Optional[str] = None
    flow_data: Optional[Dict[str, Any]] = None

class Flow(FlowBase):
    id: str
    owner_id: str
    flow_data: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_interacted_chat_id: Optional[str] = None
    
    class Config:
        from_attributes = True

class NodeGenerationRequest(BaseModel):
    prompt: str
    existing_nodes: Optional[List[FlowNodeBase]] = None
    
class NodeGenerationResponse(BaseModel):
    node: FlowNodeBase
    
class NodeUpdateRequest(BaseModel):
    node_id: str
    prompt: str
    current_data: Dict[str, Any]
    
class NodeUpdateResponse(BaseModel):
    updated_data: Dict[str, Any]

class GlobalVariable(BaseModel):
    name: str
    value: Any
    
class GlobalVariablesFile(BaseModel):
    variables: Dict[str, Any]

# 聊天相关的模型
class ChatBase(BaseModel):
    """聊天基础模型"""
    name: str = "未命名聊天"
    chat_data: Dict[str, Any] = Field(default_factory=dict)

class ChatCreate(ChatBase):
    """创建聊天模型"""
    flow_id: str

class ChatUpdate(BaseModel):
    """更新聊天模型"""
    name: Optional[str] = None
    chat_data: Optional[Dict[str, Any]] = None

class ChatAddMessage(BaseModel):
    """向聊天添加消息模型"""
    role: str  # user, assistant, system
    content: str
    client_message_id: Optional[str] = None # 前端生成的临时消息ID

class ChatMessageEdit(BaseModel):
    """编辑聊天消息模型"""
    new_content: str

class Chat(ChatBase):
    """聊天响应模型"""
    id: str
    flow_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 聊天消息处理的响应模型
class ChatMessageResponse(BaseModel):
    ai_response: str
    nodes: Optional[List[Dict]] = None # 由 WorkflowChain 返回的节点更新
    connections: Optional[List[Dict]] = None # 由 WorkflowChain 返回的连接更新
    flow_update_status: Optional[Dict] = None # Flow 更新状态
    error: Optional[str] = None # 任何处理错误

    class Config:
        from_attributes = True # 如果需要从 ORM 对象创建

class LastChatResponse(BaseModel):
    chatId: Optional[str] = None