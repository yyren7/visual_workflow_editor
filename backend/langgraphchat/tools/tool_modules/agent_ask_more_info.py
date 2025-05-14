import asyncio
from typing import List, Dict, Any, Optional
from backend.langgraphchat.utils.logging import logger
from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
from ..definitions import QuestionsParams, ToolResult # Relative import

async def ask_more_info_func(
    params: QuestionsParams,
    llm_client: DeepSeekLLM
) -> ToolResult:
    """询问更多信息工具实现"""
    try:
        questions = params.questions
        context = params.context
        
        questions = [q for q in questions if q and q.strip()]
        
        if not questions:
            logger.info("未提供问题，尝试基于上下文生成")
            
            if context and len(context) > 10:
                try:
                    prompt = f"""根据以下流程图设计对话的上下文，生成最多3个相关问题，以帮助获取更多设计流程图所需的信息：
                    
上下文: {context}

请生成一个包含问题的 JSON 数组，例如：{{"questions": ["问题1", "问题2"]}}。确保只返回 JSON。
"""
                    
                    questions_schema = {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "需要向用户询问的问题列表"
                            }
                        },
                        "required": ["questions"]
                    }
                    
                    result, success = await llm_client.structured_output(
                        prompt=prompt,
                        system_prompt="你是一个帮助生成有用问题的助手。请输出 JSON 数组格式的问题列表。",
                        schema=questions_schema
                    )
                    
                    if success and isinstance(result, dict) and "questions" in result and result["questions"]:
                        questions = result["questions"]
                        logger.info(f"基于上下文生成了 {len(questions)} 个问题")
                    else:
                        logger.warning("无法基于上下文生成问题，将使用默认问题")
                        questions = []
                except Exception as e:
                    logger.error(f"基于上下文生成问题时出错: {str(e)}，将使用默认问题")
                    questions = []
            
            if not questions:
                questions = [
                    "请详细描述一下您想要创建的流程图的主要目标或功能是什么？",
                    "这个流程图大概包含哪些关键的步骤或处理节点？", 
                    "流程中是否存在需要判断条件或做出选择的地方（决策点）？"
                ]
                logger.info("使用默认问题列表")
        
        formatted_questions = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        formatted_text = f"为了更好地帮助您，我需要了解更多信息：\n{formatted_questions}"
        if context:
             formatted_text = f"基于之前的讨论:\n{context}\n\n为了继续，我需要了解更多信息：\n{formatted_questions}"
        
        result_data = {
            "questions": questions,
            "context": context,
            "formatted_text": formatted_text
        }
        
        return ToolResult(
            success=True,
            message="已准备好需要询问的问题。",
            data=result_data
        )
    except Exception as e:
        logger.error(f"生成问题时出错: {str(e)}")
        return ToolResult(
            success=False,
            message=f"生成问题失败: {str(e)}"
        ) 