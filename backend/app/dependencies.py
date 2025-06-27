import os # 导入 os 模块以使用 getenv
from dotenv import load_dotenv # 导入 load_dotenv
from backend.app.services.node_template_service import NodeTemplateService
from fastapi import Request, HTTPException
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # Or BaseCheckpointSaver if more general type is needed
import logging

load_dotenv() # 加载 .env 文件中的环境变量

# 单例模式存储NodeTemplateService实例
_node_template_service = None

def get_node_template_service() -> NodeTemplateService:
    """
    获取NodeTemplateService实例的依赖函数
    
    每次应用启动只创建一个实例，遵循单例模式
    
    返回:
        NodeTemplateService: 节点模板服务实例
    """
    global _node_template_service
    if _node_template_service is None:
        # 从环境变量获取模板目录，如果未设置，NodeTemplateService内部会处理默认值
        template_dir_from_env = os.getenv("NODE_TEMPLATE_DIR_PATH")
        _node_template_service = NodeTemplateService(template_dir=template_dir_from_env)
        _node_template_service.load_templates()
    return _node_template_service 

logger = logging.getLogger(__name__)

def get_checkpointer(request: Request) -> AsyncPostgresSaver:
    """
    Dependency provider for the LangGraph checkpointer.
    Retrieves the checkpointer instance from request.app.state.
    Raises an HTTPException if the checkpointer is not available.
    """
    if not hasattr(request.app.state, 'checkpointer_instance') or request.app.state.checkpointer_instance is None:
        logger.error("get_checkpointer called but checkpointer_instance is not found in app.state or is None. Initialization likely failed.")
        raise HTTPException(
            status_code=503, 
            detail="Persistence service (checkpointer) is not available or not initialized."
        )
    return request.app.state.checkpointer_instance

# You can add other shared dependencies here in the future, like get_node_template_service
# from backend.app.services.node_template_service import NodeTemplateService
# from database.connection import get_db
# from sqlalchemy.orm import Session

# def get_node_template_service(db: Session = Depends(get_db)) -> NodeTemplateService:
#     return NodeTemplateService(db=db) 