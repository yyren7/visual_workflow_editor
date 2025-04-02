from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class ChatResponse(BaseModel):
    """聊天响应模型

    用于表示聊天API的标准响应格式
    """
    conversation_id: Optional[str] = None
    message: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        """配置类"""
        json_schema_extra = {
            "example": {
                "conversation_id": "7a0720fe-d63b-4253-b587-5e3f8f1bffd2",
                "message": "你好，我是流程图设计助手。我可以帮你设计和创建工作流流程图。",
                "created_at": "2025-03-27T05:51:18.123456",
                "metadata": {"refresh_flow": True, "node_id": "moveL-1743054678193"}
            }
        } 