import logging
logger = logging.getLogger(__name__)

from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
from ..definitions import TextGenerationParams, ToolResult # Relative import

async def generate_text_func(
    params: TextGenerationParams,
    llm_client: DeepSeekLLM
) -> ToolResult:
    """文本生成工具实现"""
    try:
        prompt = params.prompt
        max_length = params.max_length
        
        logger.info(f"请求生成文本: prompt length={len(prompt)}, max_length={max_length}")

        if not prompt:
            return ToolResult(
                success=False,
                message="文本生成失败: 缺少提示"
            )
        
        response_text, success = await llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一个专业的文本生成助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_length
        )
        
        if not success:
            logger.error("LLM 调用失败 during text generation")
            return ToolResult(
                success=False,
                message="文本生成失败: AI 服务错误"
            )
        
        logger.info("成功生成文本")
        return ToolResult(
            success=True,
            message="成功生成文本",
            data={"text": response_text}
        )
    except Exception as e:
        logger.error(f"生成文本时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"生成文本失败: {str(e)}"
        ) 