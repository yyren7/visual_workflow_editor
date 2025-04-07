from typing import Dict, Any, Type, TypeVar, Optional, get_type_hints, get_origin, get_args, List, Tuple
import json
import logging
import httpx
import os
from openai import OpenAI
from pydantic import BaseModel
from backend.config import AI_CONFIG
from backend.app.services.prompt_service import BasePromptService
from backend.app.services.deepseek_client_service import DeepSeekClientService

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# 单例管理
_structured_output_service_instance = None

class StructuredOutputRequest(BaseModel):
    """结构化输出请求"""
    prompt: str
    schema: Dict[str, Any] = None
    conversation_id: Optional[str] = None
    

class StructuredOutputService(BasePromptService):
    """
    结构化输出服务
    将用户输入转换为符合指定结构的JSON输出
    """
    
    def __init__(self):
        """初始化结构化输出服务"""
        super().__init__()
        
        # 使用DeepSeekClientService
        self.deepseek_service = DeepSeekClientService.get_instance()
        
        # 对话映射：用于维护不同用户/会话的对话历史
        self.conversation_mapping = {}
        
        # 结构化输出提示模板
        self.structured_output_template = """
你是一个专业的结构化信息提取助手。请从以下文本中提取关键信息，并以JSON格式输出：

{prompt}

请严格按照以下JSON结构输出：
{schema}

请确保输出的JSON格式有效且符合指定结构。只返回JSON，不要包含任何额外的解释或前缀。
"""
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        global _structured_output_service_instance
        if _structured_output_service_instance is None:
            logger.info("创建StructuredOutputService单例")
            _structured_output_service_instance = cls()
        return _structured_output_service_instance
    
    async def extract_structured_data(self, request: StructuredOutputRequest) -> Tuple[Dict[str, Any], bool]:
        """
        从文本中提取结构化数据
        
        Args:
            request: 结构化输出请求，包含原始提示文本和目标JSON结构
            
        Returns:
            (提取的结构化数据, 是否成功)
        """
        try:
            logger.info("开始提取结构化数据")
            
            # 使用会话ID(如果提供)
            conversation_id = request.conversation_id
            
            # 准备系统提示
            system_prompt = "你是一个专业的结构化数据提取助手，擅长将非结构化文本转换为结构化JSON数据。"
            
            # 准备用户提示
            prompt = request.prompt
            schema = request.schema
            
            # 使用DeepSeek客户端服务进行结构化输出
            result, success = await self.deepseek_service.structured_output(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation_id=conversation_id,
                schema=schema
            )
            
            if not success:
                logger.error("结构化数据提取失败")
                return {"error": "结构化数据提取失败，AI服务暂时不可用"}, False
            
            return result, True
            
        except Exception as e:
            logger.error(f"提取结构化数据时出错: {str(e)}")
            return {"error": f"处理失败: {str(e)}"}, False
    
    def create_new_conversation(self, system_message: str = None) -> str:
        """
        创建新的结构化输出对话
        
        Args:
            system_message: 可选的系统消息
            
        Returns:
            对话ID
        """
        # 使用DeepSeek客户端服务创建对话
        default_system_message = "你是一个专业的结构化数据提取助手，擅长将非结构化文本转换为结构化JSON数据。"
        conversation_id = self.deepseek_service.create_conversation(
            system_message=system_message or default_system_message
        )
        
        logger.info(f"创建新的结构化输出对话: {conversation_id}")
        return conversation_id
    
    def clear_conversation(self, conversation_id: str) -> None:
        """
        清除对话历史
        
        Args:
            conversation_id: 对话ID
        """
        # 使用DeepSeek客户端服务清除对话
        self.deepseek_service.clear_conversation(conversation_id)
        logger.info(f"清除结构化输出对话: {conversation_id}")
    
    async def generate_structured_output(self, 
                                  prompt: str, 
                                  system_prompt: str = None,
                                  conversation_id: str = None) -> Tuple[Dict[str, Any], bool]:
        """
        生成结构化输出(自动推断结构)
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            conversation_id: 对话ID
            
        Returns:
            (解析后的结构化数据, 是否成功)
        """
        try:
            # 生成简单系统提示,鼓励模型自动推断合适的结构
            if system_prompt is None:
                system_prompt = """你是一个专业的结构化数据提取助手。
请从用户输入中提取关键信息，并以JSON格式输出。
请自行推断适合的JSON结构，确保结构清晰、完整地表达提取的信息。
只返回JSON，不要包含任何额外解释。"""
                
            # 使用DeepSeek客户端服务进行结构化输出(不指定schema)
            result, success = await self.deepseek_service.structured_output(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation_id=conversation_id
            )
            
            if not success:
                logger.error("结构化输出生成失败")
                return {"error": "生成结构化输出失败，AI服务暂时不可用"}, False
                
            return result, True
            
        except Exception as e:
            logger.error(f"生成结构化输出时出错: {str(e)}")
            return {"error": f"处理失败: {str(e)}"}, False
    
    def _get_format_instructions(self, model: Type[BaseModel]) -> str:
        """获取模型的格式指令"""
        # 获取模型字段
        model_schema = model.schema()
        
        # 格式化指令
        instructions = []
        instructions.append(f"```json")
        instructions.append(json.dumps(model_schema, indent=2, ensure_ascii=False))
        instructions.append(f"```")
        
        # 添加示例
        instructions.append(f"\n示例:")
        example = {}
        for field_name, field_info in model_schema.get('properties', {}).items():
            if 'type' in field_info:
                field_type = field_info['type']
                if field_type == 'string':
                    example[field_name] = "示例文本"
                elif field_type == 'integer':
                    example[field_name] = 0
                elif field_type == 'number':
                    example[field_name] = 0.0
                elif field_type == 'boolean':
                    example[field_name] = False
                elif field_type == 'array':
                    example[field_name] = []
                elif field_type == 'object':
                    example[field_name] = {}
        
        instructions.append(f"```json")
        instructions.append(json.dumps(example, indent=2, ensure_ascii=False))
        instructions.append(f"```")
        
        return "\n".join(instructions)
    
    def _parse_structured_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析结构化响应"""
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试从文本中提取JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
            except:
                pass
            
            return None
            
    async def _call_llm_api(self, prompt: str) -> str:
        """调用LLM API"""
        # 判断是否使用DeepSeek API
        if AI_CONFIG['USE_DEEPSEEK']:
            return await self._call_deepseek_api(prompt)
        # 原有的本地LLM逻辑保留作为备选
        else:
            return await self._call_local_llm_api(prompt)
    
    async def _call_local_llm_api(self, prompt: str) -> str:
        """调用本地LLM API"""
        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        
        payload = {
            "prompt": prompt,
            "max_tokens": 2000, # 结构化输出可能需要更多token
            "temperature": 0.1  # 结构化输出需要更低的温度
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llm_api_url}/complete",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                return result.get("text", "")
        except Exception as e:
            logger.error(f"调用本地LLM API时出错: {str(e)}")
            if Config.DEBUG:
                logger.error(f"API URL: {self.llm_api_url}, Payload: {payload}")
            raise
            
    async def _call_deepseek_api(self, prompt: str) -> str:
        """调用DeepSeek API"""
        try:
            logger.info(f"调用DeepSeek API，模型: {Config.DEEPSEEK_MODEL}")
            
            messages = [
                {"role": "system", "content": "你是一个专业的流程图设计助手，能根据用户需求生成符合特定结构的输出，严格按照JSON格式要求。"},
                {"role": "user", "content": prompt}
            ]
            
            full_text = ""
            
            # 调用DeepSeek API
            response = self.deepseek_client.chat.completions.create(
                model=Config.DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=2000,
                temperature=0.0,  # 最低温度以确保结构化输出
                stream=True
            )
            
            # 处理流式响应
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_text += content
            
            return full_text
            
        except Exception as e:
            logger.error(f"调用DeepSeek API时出错: {str(e)}")
            if Config.DEBUG:
                logger.error(f"API URL: {Config.DEEPSEEK_BASE_URL}")
            raise 