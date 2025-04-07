"""
DeepSeek API客户端服务模块
提供与DeepSeek API交互的功能
"""

import logging
import time
import uuid
import json
import os
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageParam, ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam, ChatCompletionAssistantMessageParam
from openai._exceptions import OpenAIError, APIConnectionError, APITimeoutError
from backend.config import AI_CONFIG, get_log_file_path

# 使用专门的deepseek日志记录器
logger = logging.getLogger("backend.deepseek")

# 日志文件路径
DEEPSEEK_LOG_FILE = get_log_file_path("deepseek_api.log")

# 设置文件日志处理器
file_handler = logging.FileHandler(DEEPSEEK_LOG_FILE)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 单例管理器
_deepseek_client_instance = None
# 会话管理，存储不同会话的对话历史
_conversation_histories = {}

class DeepSeekClientService:
    """
    DeepSeek客户端管理服务
    负责DeepSeek API的客户端管理、多轮对话历史和错误处理
    """
    
    def __init__(self):
        """初始化DeepSeek客户端"""
        self.api_key = AI_CONFIG['DEEPSEEK_API_KEY']
        self.base_url = AI_CONFIG['DEEPSEEK_BASE_URL']
        self.model = AI_CONFIG['DEEPSEEK_MODEL']
        
        # 验证配置
        if not self.api_key:
            logger.warning("DeepSeek API密钥未设置")
            
        logger.info(f"初始化DeepSeek客户端，使用模型: {self.model}")
        
        # 创建客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.max_retries = 3
        self.retry_delay = 1.0  # 初始重试延迟(秒)
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        global _deepseek_client_instance
        if _deepseek_client_instance is None:
            _deepseek_client_instance = cls()
        return _deepseek_client_instance
    
    def create_conversation(self, conversation_id: str = None, system_message: str = None) -> str:
        """
        创建一个新的对话
        
        Args:
            conversation_id: 对话ID，如果不提供则自动生成
            system_message: 系统消息，用于初始化对话
            
        Returns:
            对话ID
        """
        if conversation_id is None:
            conversation_id = f"conv_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
        # 如果对话已存在，返回已有ID
        if conversation_id in _conversation_histories:
            return conversation_id
        
        # 初始化对话历史
        _conversation_histories[conversation_id] = []
        
        # 添加系统消息(如果提供)
        if system_message:
            self.add_message(conversation_id, "system", system_message)
        
        logger.debug(f"创建新对话: {conversation_id}")
        return conversation_id
    
    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """
        向对话添加消息
        
        Args:
            conversation_id: 对话ID
            role: 消息角色 (system, user, assistant)
            content: 消息内容
        """
        if conversation_id not in _conversation_histories:
            self.create_conversation(conversation_id)
        
        message: ChatCompletionMessageParam = {"role": role, "content": content}
        _conversation_histories[conversation_id].append(message)
        logger.debug(f"添加消息到对话 {conversation_id}: role={role}, content_length={len(content)}")
    
    def get_conversation_history(self, conversation_id: str) -> List[ChatCompletionMessageParam]:
        """
        获取对话历史
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            对话历史消息列表
        """
        if conversation_id not in _conversation_histories:
            logger.warning(f"尝试获取不存在的对话历史: {conversation_id}")
            return []
        
        return _conversation_histories[conversation_id]
    
    def clear_conversation(self, conversation_id: str) -> None:
        """
        清除对话历史
        
        Args:
            conversation_id: 对话ID
        """
        if conversation_id in _conversation_histories:
            del _conversation_histories[conversation_id]
            logger.debug(f"清除对话历史: {conversation_id}")
    
    async def chat_completion(self, 
                       messages: List[ChatCompletionMessageParam] = None,
                       conversation_id: str = None, 
                       user_message: str = None,
                       model_name: str = None,
                       temperature: float = 0.3,
                       max_tokens: int = 1000,
                       stream: bool = False,
                       json_mode: bool = False,
                       tools: List[Dict[str, Any]] = None) -> Tuple[str, bool]:
        """
        执行聊天完成请求，支持新消息或已有对话ID
        
        Args:
            messages: 消息列表(直接提供时会忽略conversation_id)
            conversation_id: 对话ID
            user_message: 用户消息(当使用conversation_id时)
            model_name: 使用的模型，默认使用初始化时的模型
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成令牌数
            stream: 是否使用流式响应
            json_mode: 是否使用JSON结构化输出
            tools: 功能调用定义列表
            
        Returns:
            (响应内容, 是否成功)
        """
        # 确定使用哪些消息
        request_messages = None
        use_conversation = False
        
        try:
            if messages is not None:
                # 直接使用提供的消息列表
                request_messages = messages
            elif conversation_id is not None:
                # 使用对话历史
                use_conversation = True
                if conversation_id not in _conversation_histories:
                    self.create_conversation(conversation_id)
                
                # 添加新的用户消息(如果有)
                if user_message:
                    self.add_message(conversation_id, "user", user_message)
                
                request_messages = _conversation_histories[conversation_id]
            else:
                # 错误：没有指定消息或对话ID
                logger.error("执行聊天完成请求时未提供消息或对话ID")
                return "错误：未提供消息或对话ID", False
            
            # 确保消息不为空且格式正确
            if not request_messages:
                logger.error("消息列表为空")
                return "错误：消息列表为空", False
            
            # 记录请求详情
            msg_count = len(request_messages)
            logger.info(f"准备DeepSeek API调用: {msg_count}条消息")
            
            # 记录完整的输入消息内容（开发调试用）
            print("\n======== DEEPSEEK API 请求开始 ========")
            print(f"消息数量: {msg_count}")
            for i, msg in enumerate(request_messages):
                print(f"消息 {i+1} ({msg['role']}):")
                # 限制内容长度以保持日志可读性
                content_preview = msg['content']
                if len(content_preview) > 500:
                    content_preview = content_preview[:500] + "... (内容已截断)"
                print(f"{content_preview}")
            
            # 记录工具定义（如果有）
            if tools:
                print(f"\n工具定义: {json.dumps(tools, ensure_ascii=False, indent=2)}")
            
            # 记录其他参数
            print(f"\n模型: {model_name or self.model}")
            print(f"温度: {temperature}")
            print(f"最大令牌数: {max_tokens}")
            print(f"JSON模式: {json_mode}")
            print(f"流式响应: {stream}")
            print("======================================\n")
            
            # 详细记录到日志文件
            logger.info("===== DEEPSEEK API 请求详情 =====")
            # 记录完整的请求消息内容到日志文件
            for i, msg in enumerate(request_messages):
                role = msg['role']
                content = msg['content']
                # 对日志文件不截断内容，确保完整记录
                logger.info(f"消息 {i+1} ({role}) 完整内容:")
                # 分行记录长内容以提高可读性
                content_lines = content.split('\n')
                for line in content_lines:
                    logger.info(f"  {line}")
            
            if tools:
                logger.info(f"工具定义: {json.dumps(tools, ensure_ascii=False)}")
            
            logger.info(f"模型: {model_name or self.model}")
            logger.info(f"温度: {temperature}")
            logger.info(f"最大令牌数: {max_tokens}")
            logger.info(f"JSON模式: {json_mode}")
            logger.info(f"流式响应: {stream}")
            logger.info("==================================")
            
            # 使用指定的模型或默认模型
            model = model_name or self.model
            
            # 执行API调用，带有重试机制
            retries = 0
            response_text = ""
            success = False
            last_error = None
            
            while retries <= self.max_retries:
                if retries > 0:
                    # 计算退避延迟时间: 基础延迟 * (2^重试次数)
                    delay = self.retry_delay * (2 ** (retries - 1))
                    logger.info(f"重试DeepSeek API调用 (第{retries}次，延迟{delay:.2f}秒)")
                    time.sleep(delay)
                
                try:
                    # 准备请求参数
                    params = {
                        "model": model,
                        "messages": request_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": stream
                    }
                    
                    # JSON模式设置
                    if json_mode:
                        params["response_format"] = {"type": "json_object"}
                    
                    # 添加工具调用参数(如果提供)
                    if tools:
                        params["tools"] = tools
                    
                    logger.debug(f"调用DeepSeek API: 模型={model}, 温度={temperature}, JSON模式={json_mode}")
                    
                    # 检查客户端是否初始化
                    if self.client is None:
                        logger.warning("DeepSeek客户端未初始化，尝试重新初始化")
                        self.__init__()
                    
                    # 调用API
                    if stream:
                        # 流式响应处理
                        full_text = ""
                        logger.info("开始流式API调用")
                        response = self.client.chat.completions.create(**params)
                        for chunk in response:
                            if chunk.choices and len(chunk.choices) > 0:
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    content = delta.content
                                    full_text += content
                                    # 在控制台打印流式返回的内容
                                    print(content, end='', flush=True)
                        response_text = full_text
                        print("\n")
                        logger.info(f"流式API调用完成，接收到{len(response_text)}字符")
                    else:
                        # 非流式响应
                        logger.info("开始非流式API调用")
                        response = self.client.chat.completions.create(**params)
                        response_text = response.choices[0].message.content
                        logger.info(f"非流式API调用完成，接收到{len(response_text)}字符")
                    
                    # 打印并记录API返回的完整响应
                    print("\n======== DEEPSEEK API 响应结果 ========")
                    # 显示响应内容（限制长度以保持可读性）
                    response_preview = response_text
                    if len(response_preview) > 1000:
                        response_preview = response_preview[:1000] + "... (内容已截断)"
                    print(response_preview)
                    print("========================================\n")
                    
                    # 完整记录到日志文件
                    logger.info("===== DEEPSEEK API 响应详情 =====")
                    # 记录完整的响应内容，不截断
                    logger.info("响应完整内容:")
                    # 分行记录长回复以提高可读性
                    response_lines = response_text.split('\n')
                    for line in response_lines:
                        logger.info(f"  {line}")
                    logger.info("==================================")
                    
                    # 如果使用对话，将助手响应添加到历史
                    if use_conversation and conversation_id and response_text:
                        self.add_message(conversation_id, "assistant", response_text)
                    
                    success = True
                    logger.info("DeepSeek API调用成功")
                    break
                    
                except APIConnectionError as e:
                    # 网络连接错误，可以重试
                    logger.warning(f"DeepSeek API连接错误(第{retries+1}次): {str(e)}")
                    
                    # 记录更多网络错误细节
                    import traceback
                    logger.error(f"连接错误详情:\n{traceback.format_exc()}")
                    
                    # 尝试检查网络连接
                    try:
                        import socket
                        from urllib.parse import urlparse
                        parsed_url = urlparse(self.base_url)
                        hostname = parsed_url.hostname
                        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
                        
                        logger.info(f"测试到 {hostname}:{port} 的连接")
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        result = sock.connect_ex((hostname, port))
                        sock.close()
                        
                        if result == 0:
                            logger.info(f"可以连接到 {hostname}:{port}")
                        else:
                            logger.error(f"无法连接到 {hostname}:{port}，错误码: {result}")
                    except Exception as net_e:
                        logger.error(f"测试网络连接时出错: {str(net_e)}")
                    
                    last_error = e
                    retries += 1
                except APITimeoutError as e:
                    # 超时错误，可以重试
                    logger.warning(f"DeepSeek API超时(第{retries+1}次): {str(e)}")
                    last_error = e
                    retries += 1
                except OpenAIError as e:
                    # 其他OpenAI错误，可能不适合重试
                    logger.error(f"DeepSeek API错误: {str(e)}")
                    
                    # 检查错误详情
                    if hasattr(e, 'response') and e.response:
                        logger.error(f"响应状态码: {e.response.status}")
                        logger.error(f"响应内容: {e.response.text}")
                    
                    response_text = f"与AI服务通信时出错: {str(e)}"
                    last_error = e
                    # 针对某些错误码决定是否重试
                    if hasattr(e, 'status_code') and e.status_code in [429, 500, 502, 503, 504]:
                        retries += 1
                    else:
                        break  # 不可重试的错误，直接跳出
                except Exception as e:
                    # 未知错误
                    logger.error(f"调用DeepSeek API时发生未知错误: {str(e)}")
                    logger.error(f"错误类型: {type(e).__name__}")
                    import traceback
                    logger.error(f"调用堆栈:\n{traceback.format_exc()}")
                    response_text = f"未知错误: {str(e)}"
                    last_error = e
                    break  # 未知错误不重试
        except Exception as outer_e:
            # 捕获外部异常
            logger.error(f"执行聊天完成请求时发生外部异常: {str(outer_e)}")
            import traceback
            logger.error(f"外部异常堆栈:\n{traceback.format_exc()}")
            return f"处理请求时出错: {str(outer_e)}", False
            
        if not success:
            # 所有重试都失败了
            if last_error:
                logger.error(f"DeepSeek API调用失败，已重试{retries}次: {str(last_error)}")
                return f"AI服务暂时不可用，请稍后再试。错误: {str(last_error)}", False
            else:
                return "AI服务暂时不可用，请稍后再试", False
        
        return response_text, True
    
    async def structured_output(self, 
                         prompt: str, 
                         system_prompt: str = None, 
                         conversation_id: str = None, 
                         schema: Dict = None) -> Tuple[Dict, bool]:
        """
        获取结构化JSON输出
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            conversation_id: 对话ID
            schema: JSON结构定义
            
        Returns:
            (解析后的JSON对象, 是否成功)
        """
        # 准备消息
        messages = []
        if system_prompt:
            system_message = f"{system_prompt}\n\n请以JSON格式返回响应，确保输出是有效的JSON。"
            messages.append({"role": "system", "content": system_message})
        
        # 如果提供了schema，添加到提示中
        if schema:
            schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
            prompt = f"{prompt}\n\n请使用以下JSON模式:\n```json\n{schema_str}\n```"
        
        messages.append({"role": "user", "content": prompt})
        
        # 使用JSON模式调用API
        response_text, success = await self.chat_completion(
            messages=messages if conversation_id is None else None,
            conversation_id=conversation_id,
            user_message=prompt if conversation_id is not None else None,
            json_mode=True
        )
        
        if not success:
            return {}, False
        
        # 尝试解析JSON
        try:
            result = json.loads(response_text)
            return result, True
        except json.JSONDecodeError as e:
            logger.error(f"解析DeepSeek响应的JSON时出错: {str(e)}")
            
            # 尝试提取JSON部分
            try:
                import re
                json_pattern = r'```json\s*([\s\S]*?)\s*```|(\{[\s\S]*\})'
                match = re.search(json_pattern, response_text)
                if match:
                    json_str = match.group(1) or match.group(2)
                    result = json.loads(json_str)
                    return result, True
            except Exception:
                pass
            
            return {"error": "无法解析响应为有效的JSON", "raw_response": response_text}, False
    
    async def function_calling(self, 
                       prompt: str, 
                       tools: List[Dict[str, Any]], 
                       system_prompt: str = None,
                       conversation_id: str = None) -> Tuple[Dict, bool]:
        """
        执行函数调用
        
        Args:
            prompt: 用户提示
            tools: 工具定义列表
            system_prompt: 系统提示
            conversation_id: 对话ID
            
        Returns:
            (工具调用结果, 是否成功)
        """
        # 准备消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        # 调用API
        response_text, success = await self.chat_completion(
            messages=messages if conversation_id is None else None,
            conversation_id=conversation_id,
            user_message=prompt if conversation_id is not None else None,
            tools=tools
        )
        
        if not success:
            return {}, False
        
        # 提取工具调用信息
        try:
            # 这里通常需要解析响应以提取工具调用信息
            # 由于DeepSeek的函数调用可能会有特殊的返回格式，可能需要调整
            if "tool_calls" in response_text:
                # 假设工具调用以某种方式包含在响应中
                return {"tool_calls": response_text}, True
            else:
                # 如果没有工具调用，返回文本响应
                return {"content": response_text, "has_tool_calls": False}, True
        except Exception as e:
            logger.error(f"处理工具调用响应时出错: {str(e)}")
            return {"error": f"处理工具调用响应时出错: {str(e)}", "raw_response": response_text}, False 