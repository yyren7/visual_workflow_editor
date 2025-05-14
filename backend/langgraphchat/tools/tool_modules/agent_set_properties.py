from backend.langgraphchat.utils.logging import logger
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
from ..definitions import PropertyParams, ToolResult # Relative import

async def set_properties_func(
    params: PropertyParams,
    llm_client: DeepSeekLLM
) -> ToolResult:
    """属性设置工具实现"""
    try:
        element_id = params.element_id
        properties = params.properties
        
        logger.info(f"请求设置属性 for element: {element_id}")

        if not element_id or properties is None:
            return ToolResult(
                success=False,
                message="设置属性失败: 缺少元素ID或属性"
            )
        
        result_data = {
            "element_id": element_id,
            "properties": properties
        }
        
        logger.info(f"成功准备属性设置数据 for: {element_id}")
        return ToolResult(
            success=True,
            message=f"成功准备设置属性: {element_id}",
            data=result_data
        )
    except Exception as e:
        logger.error(f"设置属性时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"设置属性失败: {str(e)}"
        ) 