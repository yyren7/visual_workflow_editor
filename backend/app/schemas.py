from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    
    class Config:
        orm_mode = True

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
    id: int
    owner_id: int
    flow_data: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

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