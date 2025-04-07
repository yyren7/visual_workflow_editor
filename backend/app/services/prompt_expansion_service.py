from typing import Dict, Any, List, Optional
import httpx
import json
import logging
import os
from openai import OpenAI
from backend.config import AI_CONFIG
from backend.app.services.prompt_service import BasePromptService

logger = logging.getLogger(__name__)

class PromptExpansionService(BasePromptService):
    """
    Prompt扩展和修正服务
    将用户简单输入扩展为详细的专业步骤
    """
    
    def __init__(self):
        """初始化提示扩展服务"""
        super().__init__()
        
        # 获取DeepSeek API配置
        self.deepseek_api_key = AI_CONFIG['DEEPSEEK_API_KEY']
        self.deepseek_base_url = AI_CONFIG['DEEPSEEK_BASE_URL']
        self.deepseek_model = AI_CONFIG['DEEPSEEK_MODEL']
        
        # 提示扩展模板
        self.prompt_expansion_template = """
你是一个专业的流程图设计助手。请将用户的输入转换为明确的流程图设计步骤。

用户输入: {user_input}

请将用户输入扩展为详细的步骤列表，使用以下格式:
步骤1: [第一个步骤的详细描述]
步骤2: [第二个步骤的详细描述]
...

对于流程图设计，考虑以下节点类型:
1. 开始节点(start): 流程的起点
2. 结束节点(end): 流程的终点
3. 处理节点(process): 表示一个操作或行动
4. 决策节点(decision): 表示条件判断，通常有多个输出路径
5. 数据节点(data): 表示数据存储
6. 输入输出节点(io): 表示数据输入或输出

如果用户要求创建或修改特定节点，请包括:
- 节点类型
- 节点名称/标签
- 节点属性(如果有)

如果用户输入信息不足，请指出缺少的关键信息:
缺少信息: [描述缺少的信息]

注意: 请直接输出步骤列表，不要添加额外的解释或前置文字。仅输出步骤序列。
"""

        # 上下文扩展模板 - 处理简短响应和历史上下文
        self.context_expansion_template = """
你是一个专业的流程图设计助手。请根据对话历史和用户的简短回应，继续之前的流程图设计过程。

对话历史:
{context}

用户回应: {user_response}

请基于对话历史和用户的响应，生成下一步的流程图设计步骤。如果用户回应是确认或同意之前的建议，请继续之前未完成的步骤。如果用户回应是否定的，请调整之前的建议。

使用以下格式:
步骤1: [步骤的详细描述]
步骤2: [步骤的详细描述]
...

注意: 请直接输出步骤列表，不要添加额外的解释或前置文字。仅输出步骤序列。
"""
        
        self.llm_api_url = AI_CONFIG['LLM_API_URL']
        self.llm_api_key = AI_CONFIG['LLM_API_KEY']
        # 初始化DeepSeek客户端
        if AI_CONFIG['USE_DEEPSEEK']:
            self.deepseek_client = OpenAI(
                api_key=AI_CONFIG['DEEPSEEK_API_KEY'], 
                base_url=AI_CONFIG['DEEPSEEK_BASE_URL']
            )
        else:
            self.deepseek_client = None
        
        # 扩展模板 - 将用户输入扩展为详细步骤
        self.expansion_template = """
你是一个专业的流程图设计助手。我需要你将用户的简单描述扩展为详细的、专业的步骤序列。

用户描述: {input_prompt}

请先分析用户描述的复杂性:
1. 如果用户请求简单明确（如"创建一个开始节点"、"生成一个process节点"等），请直接提供简洁的1-2个步骤，不要过度复杂化。
2. 如果用户请求具有一定复杂性，再展开为更详细的步骤。

对于明确的简单请求，不要生成"缺少信息"部分，除非真的无法执行请求。

请将用户描述扩展为明确的、专业的步骤，遵循以下要求:
1. 使用流程图设计领域的专业术语和表达方式
2. 确保步骤之间有清晰的逻辑关系
3. 明确指出需要创建哪些节点、节点类型、节点属性和节点之间的连接关系
4. 只在必要时标注出真正不足的关键信息
5. 以编号列表形式呈现每个步骤

请输出格式如下:
步骤1: [详细步骤描述]
步骤2: [详细步骤描述]
...
缺少信息: [仅在真正缺少关键信息时列出]
"""
    
    async def expand_prompt(self, user_input: str, context: str = "") -> str:
        """
        扩展和修正用户输入为专业的工作流步骤
        
        Args:
            user_input: 用户输入的字符串
            context: 对话历史上下文，默认为空字符串
            
        Returns:
            扩展和修正后的工作流步骤
        """
        try:
            # 检查输入是否包含对话历史上下文
            current_input = user_input
            
            # 如果没有提供context参数但用户输入中包含对话历史
            if not context and "对话历史:" in user_input and "当前输入:" in user_input:
                # 提取对话历史和当前输入
                parts = user_input.split("当前输入:", 1)
                if len(parts) > 1:
                    context = parts[0].replace("对话历史:", "").strip()
                    current_input = parts[1].strip()
                    logger.info("从用户输入中检测到对话历史上下文")

            # 解析简短的响应，例如"是的"，"好的"，"确认"等
            is_simple_response = False
            simple_responses = ["是的", "好的", "确认", "好", "是", "确定", "对", "同意", "可以", 
                               "不", "不是", "否", "不要", "不行", "不可以", "不同意"]
            
            if any(current_input.strip().startswith(resp) for resp in simple_responses) or len(current_input.strip()) < 10:
                is_simple_response = True
                logger.info(f"检测到简短响应: {current_input}")
            
            # 准备提示模板
            if is_simple_response and context:
                # 如果是简短响应且有上下文，使用上下文增强理解
                template = self.context_expansion_template
                prompt_data = {
                    "context": context,
                    "user_response": current_input
                }
            else:
                # 常规提示扩展
                template = self.prompt_expansion_template
                prompt_data = {"user_input": current_input}
            
            # 使用模板构建提示
            prompt = self.process_template(template, prompt_data)
            
            logger.info(f"调用DeepSeek API，模型: {self.deepseek_model}, API基础URL: {self.deepseek_base_url}")
            logger.info(f"准备向DeepSeek API发送请求，消息长度: {len(prompt)}")
            logger.info(f"API密钥前4位: {self.deepseek_api_key[:4] if self.deepseek_api_key else 'None'}")
            
            # 构建请求
            headers = {
                "Authorization": f"Bearer {self.deepseek_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.deepseek_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的流程图设计助手，擅长将用户需求转换为明确的步骤和操作。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1500
            }
            
            # 发送请求
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.deepseek_base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                logger.info("DeepSeek API响应成功")
                result = response.json()
                expanded_prompt = result["choices"][0]["message"]["content"]
                return expanded_prompt
            else:
                logger.error(f"DeepSeek API调用失败: {response.status_code}, {response.text}")
                # 如果API调用失败，使用一个基本的格式化
                if is_simple_response and context:
                    # 尝试从上下文中提取最后一个步骤并继续
                    return f"继续执行先前讨论的步骤，并确认用户的响应: {current_input}"
                return f"步骤1: {current_input}"
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"扩展提示时出错: {str(e)}")
            logger.error(f"错误详细信息: {error_trace}")
            
            # 构造更明确的错误信息而不是直接返回原始输入
            if "DeepSeek API" in error_trace or "429" in error_trace:
                error_message = f"步骤1: API服务暂时不可用，请稍后重试。原始请求: {user_input}"
            elif "timeout" in error_trace.lower():
                error_message = f"步骤1: 请求超时，请稍后重试。原始请求: {user_input}"
            else:
                error_message = f"步骤1: 处理请求时发生错误，系统将直接执行您的原始请求: {user_input}"
            
            # 记录返回的错误信息
            logger.info(f"由于错误，返回的扩展提示: {error_message}")
            return error_message
    
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
            if AI_CONFIG['DEBUG']:
                logger.error(f"API URL: {self.llm_api_url}, Payload: {payload}")
            raise
            
    async def _call_deepseek_api(self, prompt: str) -> str:
        """调用DeepSeek API"""
        try:
            logger.info(f"调用DeepSeek API，模型: {AI_CONFIG['DEEPSEEK_MODEL']}, API基础URL: {AI_CONFIG['DEEPSEEK_BASE_URL']}")
            
            if not self.deepseek_client:
                logger.error("DeepSeek客户端未初始化，尝试重新初始化")
                self.deepseek_client = OpenAI(
                    api_key=AI_CONFIG['DEEPSEEK_API_KEY'], 
                    base_url=AI_CONFIG['DEEPSEEK_BASE_URL']
                )
                logger.info("DeepSeek客户端初始化完成")
            
            messages = [
                {"role": "system", "content": "你是一个专业的流程图设计助手，负责扩展用户输入为详细的专业步骤。"},
                {"role": "user", "content": prompt}
            ]
            
            logger.info(f"准备向DeepSeek API发送请求，消息长度: {len(str(messages))}")
            logger.info(f"API密钥前4位: {AI_CONFIG['DEEPSEEK_API_KEY'][:4] if AI_CONFIG['DEEPSEEK_API_KEY'] else '未设置'}")
            
            try:
                # 使用非流式响应进行测试，简化调试过程
                response = self.deepseek_client.chat.completions.create(
                    model=AI_CONFIG['DEEPSEEK_MODEL'],
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
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"调用DeepSeek API时出错: {str(e)}")
            logger.error(f"错误详细信息: {error_trace}")
            
            if AI_CONFIG['DEBUG']:
                logger.error(f"API URL: {AI_CONFIG['DEEPSEEK_BASE_URL']}")
                logger.error(f"调用堆栈: {error_trace}")
            
            # 返回明确的错误信息，而不是抛出异常
            if "timeout" in str(e).lower() or "timeout" in error_trace.lower():
                return "DeepSeek API请求超时，请稍后再试。"
            elif "429" in str(e) or "rate limit" in str(e).lower():
                return "DeepSeek API请求频率过高，请稍后再试。"
            elif "401" in str(e) or "unauthorized" in str(e).lower():
                return "DeepSeek API验证失败，请检查API密钥。"
            else:
                return f"调用DeepSeek API时发生错误: {str(e)[:100]}..."
    
    async def _direct_call_deepseek(self, messages: list) -> str:
        """使用httpx直接调用DeepSeek API，作为备用方案"""
        try:
            logger.info("使用httpx直接调用DeepSeek API")
            
            # 构建正确的URL路径
            base_url = AI_CONFIG['DEEPSEEK_BASE_URL'].rstrip('/')  # 移除尾部的斜杠(如果有)
            url = f"{base_url}/v1/chat/completions"
            
            logger.info(f"调用API URL: {url}")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AI_CONFIG['DEEPSEEK_API_KEY']}"
            }
            payload = {
                "model": AI_CONFIG['DEEPSEEK_MODEL'],
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.2
            }
            
            # 检查API密钥是否有效
            if not AI_CONFIG['DEEPSEEK_API_KEY'] or AI_CONFIG['DEEPSEEK_API_KEY'] == "your_deepseek_api_key_here":
                logger.error("无效的API密钥：未设置或使用了占位符值")
                return "DeepSeek API密钥未设置或无效。请设置有效的API密钥。"
                
            logger.info(f"Authorization头: Bearer {AI_CONFIG['DEEPSEEK_API_KEY'][:4]}***")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                logger.info("直接调用DeepSeek API成功")
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"直接调用DeepSeek API失败: {str(e)}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详细信息: {error_trace}")
            
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text}")
            
            # 返回格式化的错误信息，符合步骤格式
            error_reason = str(e)[:150]  # 限制错误信息长度
            return f"步骤1: 由于技术原因无法完成请求，请尝试使用更明确的指令。错误详情: {error_reason}" 