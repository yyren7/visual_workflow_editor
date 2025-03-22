from typing import Dict, Any, List
import httpx
import json
import logging
import os
from openai import OpenAI
from backend.app.config import Config
from backend.app.services.prompt_service import BasePromptService

logger = logging.getLogger(__name__)

class PromptExpansionService(BasePromptService):
    """
    Prompt扩展和修正服务
    将用户简单输入扩展为详细的专业步骤
    """
    
    def __init__(self):
        super().__init__()
        self.llm_api_url = Config.LLM_API_URL
        self.llm_api_key = Config.LLM_API_KEY
        # 初始化DeepSeek客户端
        if Config.USE_DEEPSEEK:
            self.deepseek_client = OpenAI(
                api_key=Config.DEEPSEEK_API_KEY, 
                base_url=Config.DEEPSEEK_BASE_URL
            )
        else:
            self.deepseek_client = None
        
        # 扩展模板 - 将用户输入扩展为详细步骤
        self.expansion_template = """
你是一个专业的流程图设计助手。我需要你将用户的简单描述扩展为详细的、专业的步骤序列。

用户描述: {input_prompt}

请将上述描述扩展为一系列明确的、专业的步骤，遵循以下要求:
1. 使用流程图设计领域的专业术语和表达方式
2. 确保步骤之间有清晰的逻辑关系
3. 明确指出需要创建哪些节点、节点类型、节点属性和节点之间的连接关系
4. 如果用户描述不完整，标注出哪些信息不足，需要进一步询问
5. 以编号列表形式呈现每个步骤

请输出格式如下:
步骤1: [详细步骤描述]
步骤2: [详细步骤描述]
...
缺少信息: [列出缺少的信息，如有]
"""
    
    async def expand_prompt(self, input_prompt: str) -> str:
        """
        扩展并修正prompt为专业步骤序列
        
        Args:
            input_prompt: 用户输入的prompt
            
        Returns:
            扩展后的步骤序列
        """
        try:
            expansion_prompt = self.process_template(self.expansion_template, {"input_prompt": input_prompt})
            expanded_result = await self._call_llm_api(expansion_prompt)
            return expanded_result
        except Exception as e:
            logger.error(f"扩展prompt时出错: {str(e)}")
            return f"无法扩展输入。原因: {str(e)}"
    
    async def _call_llm_api(self, prompt: str) -> str:
        """调用LLM API"""
        # 判断是否使用DeepSeek API
        if Config.USE_DEEPSEEK:
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
            "max_tokens": 1000,
            "temperature": 0.2, # 低温度以获得更连贯的回复
            "top_p": 0.9 # 添加top_p参数
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
            logger.info(f"调用DeepSeek API，模型: {Config.DEEPSEEK_MODEL}, API基础URL: {Config.DEEPSEEK_BASE_URL}")
            
            if not self.deepseek_client:
                logger.error("DeepSeek客户端未初始化，尝试重新初始化")
                self.deepseek_client = OpenAI(
                    api_key=Config.DEEPSEEK_API_KEY, 
                    base_url=Config.DEEPSEEK_BASE_URL
                )
                logger.info("DeepSeek客户端初始化完成")
            
            messages = [
                {"role": "system", "content": "你是一个专业的流程图设计助手，负责扩展用户输入为详细的专业步骤。"},
                {"role": "user", "content": prompt}
            ]
            
            logger.info(f"准备向DeepSeek API发送请求，消息长度: {len(str(messages))}")
            logger.info(f"API密钥前4位: {Config.DEEPSEEK_API_KEY[:4] if Config.DEEPSEEK_API_KEY else '未设置'}")
            
            try:
                # 使用非流式响应进行测试，简化调试过程
                response = self.deepseek_client.chat.completions.create(
                    model=Config.DEEPSEEK_MODEL,
                    messages=messages,
                    max_tokens=1000,
                    temperature=0.2,
                    stream=False
                )
                
                logger.info("DeepSeek API响应成功")
                return response.choices[0].message.content
                
            except Exception as api_e:
                logger.error(f"DeepSeek API调用失败: {str(api_e)}")
                logger.error(f"错误类型: {type(api_e).__name__}")
                import traceback
                logger.error(f"API调用堆栈跟踪: {traceback.format_exc()}")
                
                # 尝试使用备用方式调用API
                logger.info("尝试使用httpx直接调用DeepSeek API")
                return await self._direct_call_deepseek(messages)
                
        except Exception as e:
            logger.error(f"调用DeepSeek API时出错: {str(e)}")
            if Config.DEBUG:
                logger.error(f"API URL: {Config.DEEPSEEK_BASE_URL}")
                import traceback
                logger.error(f"调用堆栈: {traceback.format_exc()}")
            raise
    
    async def _direct_call_deepseek(self, messages: list) -> str:
        """使用httpx直接调用DeepSeek API，作为备用方案"""
        try:
            logger.info("使用httpx直接调用DeepSeek API")
            
            # 构建正确的URL路径
            base_url = Config.DEEPSEEK_BASE_URL.rstrip('/')  # 移除尾部的斜杠(如果有)
            url = f"{base_url}/v1/chat/completions"
            
            logger.info(f"调用API URL: {url}")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}"
            }
            payload = {
                "model": Config.DEEPSEEK_MODEL,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.2
            }
            
            # 检查API密钥是否有效
            if not Config.DEEPSEEK_API_KEY or Config.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
                logger.error("无效的API密钥：未设置或使用了占位符值")
                return "DeepSeek API密钥未设置或无效。请设置有效的API密钥。"
                
            logger.info(f"Authorization头: Bearer {Config.DEEPSEEK_API_KEY[:4]}***")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                logger.info("直接调用DeepSeek API成功")
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"直接调用DeepSeek API失败: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text}")
                
            return f"无法连接到DeepSeek API，请检查网络和API配置。错误: {str(e)}" 