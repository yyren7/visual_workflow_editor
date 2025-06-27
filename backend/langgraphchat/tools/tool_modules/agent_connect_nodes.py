import uuid
import logging
logger = logging.getLogger(__name__)
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM # For consistent interface
from ..definitions import ConnectionParams, ToolResult # Relative import

async def connect_nodes_func(
    params: ConnectionParams,
    llm_client: DeepSeekLLM 
) -> ToolResult:
    """连接创建工具实现"""
    try:
        source_id = params.source_id
        target_id = params.target_id
        label = params.label
        
        logger.info(f"请求连接节点: {source_id} -> {target_id}")

        if not source_id or not target_id:
            return ToolResult(
                success=False,
                message="创建连接失败: 必须提供源节点ID和目标节点ID"
            )
        
        connection_id = f"conn_{str(uuid.uuid4())[:8]}"
        
        result_data = {
            "id": connection_id,
            "source": source_id,
            "target": target_id,
            "label": label or ""
        }
        
        logger.info(f"成功准备连接创建数据: {source_id} -> {target_id}")
        return ToolResult(
            success=True,
            message=f"成功准备创建连接: {source_id} -> {target_id}",
            data=result_data
        )
    except Exception as e:
        logger.error(f"创建连接时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"创建连接失败: {str(e)}"
        ) 