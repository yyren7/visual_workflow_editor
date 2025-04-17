"""
DeepSeek API客户端模块
提供与DeepSeek API交互的功能
"""

import logging
import time
import uuid
import json
import os
from typing import Dict, List, Any, Optional, Union, Tuple, AsyncGenerator
from datetime import datetime
from openai import OpenAI, APIConnectionError, APITimeoutError, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
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

class DeepSeekLLM:
    """
    DeepSeek LLM 客户端
    负责与 DeepSeek API 的交互和错误处理
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
    
    async def chat_completion(self,
                       messages: List[ChatCompletionMessageParam],
                       model_name: str = None,
                       temperature: float = 0.3,
                       max_tokens: int = 1000,
                       json_mode: bool = False,
                       tools: List[Dict[str, Any]] = None) -> Tuple[str, bool]:
        """执行非流式的聊天完成请求，优先检查并返回工具调用信息。"""
        # Force stream to False for this method
        stream = False 
        
        logger.debug(f"Executing non-streaming chat completion...")
        
        try:
            # Sanitize messages (ensure content is string)
            request_messages = []
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content')
                if not isinstance(content, str):
                    # 尝试将非字符串内容转换为JSON字符串
                    try:
                        content = json.dumps(content, ensure_ascii=False)
                        logger.warning(f"非字符串消息内容已自动转换为JSON字符串: {content[:100]}...")
                    except Exception as e:
                        logger.error(f"无法将消息内容自动转换为JSON字符串: {e}. 原始内容: {content}")
                        # 可以选择跳过此消息或使用默认值
                        content = str(content) # 最后手段：转换为字符串
                request_messages.append({"role": role, "content": content})

            # 打印简化的请求信息到控制台（只打印用户消息或截断长消息）
            print("\n======== DEEPSEEK API 请求 (非流式) ========")
            print(f"消息数量: {len(request_messages)}")
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
            
            logger.info("===== DEEPSEEK API 请求详情 (非流式) =====")
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
            
            model = model_name or self.model
            retries = 0
            response_data = "" # Renamed from response_text to avoid confusion
            success = False
            last_error = None
            
            while retries <= self.max_retries:
                if retries > 0:
                    delay = self.retry_delay * (2 ** (retries - 1))
                    logger.info(f"重试DeepSeek API调用 (第{retries}次，延迟{delay:.2f}秒)")
                    time.sleep(delay)
                
                try:
                    params = {
                        "model": model,
                        "messages": request_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False # Explicitly False
                    }
                    if json_mode:
                        params["response_format"] = {"type": "json_object"}
                    if tools:
                        params["tools"] = tools
                    
                    logger.debug(f"调用DeepSeek API (非流式): 模型={model}, 温度={temperature}, JSON模式={json_mode}, 工具数={len(tools) if tools else 0}")
                    
                    if self.client is None:
                        logger.warning("DeepSeek客户端未初始化，尝试重新初始化")
                        self.__init__()
                    
                    # 非流式调用
                    logger.info("开始非流式API调用")
                    response = self.client.chat.completions.create(**params)
                    
                    # --- NEW: Parse response for tool calls or content ---
                    response_message = response.choices[0].message
                    if response_message.tool_calls:
                        # Tool calls detected! Return the message object as JSON string
                        logger.info(f"检测到工具调用请求: {len(response_message.tool_calls)} 个调用")
                        # Return the full ChatCompletionMessage as JSON
                        response_data = response_message.model_dump_json()
                        logger.info("响应数据 (工具调用JSON):", extra={'json_data': response_data[:500] + '...' if len(response_data) > 500 else response_data})
                    elif response_message.content is not None:
                        # No tool calls, return the text content
                        response_data = response_message.content
                        logger.info(f"非流式API调用完成，接收到文本内容，长度: {len(response_data)}")
                    else:
                        # No tool calls and no content
                        logger.warning("非流式API响应既没有内容也没有工具调用。")
                        response_data = "" # Return empty string
                    # --- End NEW parsing logic ---

                    # --- (Logging/Printing for response - uses response_data) ---
                    print("\n======== DEEPSEEK API 响应结果 (非流式) ========")
                    response_preview = response_data
                    # Handle potential JSON string in preview
                    if response_preview.strip().startswith('{') and 'tool_calls' in response_preview:
                         response_preview = "(工具调用信息，详见日志)"
                    elif len(response_preview) > 1000:
                        response_preview = response_preview[:1000] + "... (内容已截断)"
                    print(response_preview)
                    print("========================================\n")
                    
                    logger.info("===== DEEPSEEK API 响应详情 (非流式) =====")
                    logger.info("响应数据:")
                    response_lines = response_data.split('\n')
                    for line in response_lines:
                        logger.info(f"  {line}")
                    logger.info("==================================")
                    # --- End Logging/Printing ---

                    success = True
                    logger.info("DeepSeek API调用成功 (非流式)")
                    break # Success, exit retry loop
                    
                except (APIConnectionError, APITimeoutError) as e:
                    # ... (Retry logic - unchanged) ...
                    logger.warning(f"DeepSeek API 可重试错误 (第{retries+1}次): {type(e).__name__} - {str(e)}")
                    last_error = e
                    retries += 1
                except OpenAIError as e:
                    # ... (Non-retryable error logic - unchanged) ...
                    logger.error(f"DeepSeek API 不可重试错误: {type(e).__name__} - {str(e)}")
                    if hasattr(e, 'response'): logger.error(f"响应: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'} - {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
                    response_data = f"与AI服务通信时出错: {str(e)}"
                    last_error = e
                    break
                except Exception as e:
                    # ... (Unknown error logic - unchanged) ...
                    logger.error(f"调用DeepSeek API时发生未知错误: {str(e)}", exc_info=True)
                    response_data = f"未知错误: {str(e)}"
                    last_error = e
                    break

            # --- End retry loop ---
            
        except Exception as outer_e:
            # ... (Outer exception handling - unchanged) ...
            logger.error(f"执行聊天完成请求时发生外部异常: {str(outer_e)}", exc_info=True)
            return f"处理请求时出错: {str(outer_e)}", False
            
        if not success:
            # ... (Handle failure after retries - unchanged) ...
            error_msg = f"AI服务暂时不可用: {str(last_error)}" if last_error else "执行API调用失败。"
            logger.error(f"DeepSeek API调用最终失败: {error_msg}")
            return error_msg, False
        else:
             # Success, return the collected data (either text or tool call JSON)
             return response_data, True

    async def stream_chat_completion(self,
                                messages: List[ChatCompletionMessageParam],
                                model_name: str = None,
                                temperature: float = 0.3,
                                max_tokens: int = 1000,
                                # json_mode is not supported in stream
                                # tools are not supported in this simple stream method
                                ) -> AsyncGenerator[str, None]:
        """执行流式的聊天完成请求，并异步生成响应文本块。
           注意: 此版本不支持 JSON 模式或工具调用解析。
        """
        logger.debug(f"Executing streaming chat completion...")
        stream = True

        try:
            # --- (Sanitize messages - same as non-streaming) ---
            request_messages = []
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content')
                if not isinstance(content, str):
                    try: content = json.dumps(content, ensure_ascii=False)
                    except Exception: content = str(content)
                request_messages.append({"role": role, "content": content})
                
            # --- (Logging/Printing for stream request - simplified) ---
            print("\n======== DEEPSEEK API 请求 (流式) ========")
            print(f"消息数量: {len(request_messages)}")
            print(f"模型: {model_name or self.model}")
            print(f"温度: {temperature}")
            print(f"最大令牌数: {max_tokens}")
            print(f"流式响应: {stream}")
            print("======================================\n")
            logger.info("===== DEEPSEEK API 请求详情 (流式) =====")
            logger.info(f"模型: {model_name or self.model}")
            logger.info(f"温度: {temperature}")
            logger.info(f"最大令牌数: {max_tokens}")
            logger.info(f"流式响应: {stream}")
            logger.info("==================================")
            
            model = model_name or self.model
            retries = 0
            last_error = None

            while retries <= self.max_retries:
                if retries > 0:
                    delay = self.retry_delay * (2 ** (retries - 1))
                    logger.info(f"重试DeepSeek API流式调用 (第{retries}次，延迟{delay:.2f}秒)")
                    import asyncio 
                    await asyncio.sleep(delay)

                try:
                    params = {
                        "model": model,
                        "messages": request_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True # Explicitly True
                    }
                    # Ignore tools/json_mode for simple streaming

                    logger.debug(f"调用DeepSeek API (流式): 模型={model}, 温度={temperature}")
                    if self.client is None: self.__init__()

                    logger.info("开始流式API调用")
                    # Make the API call and get the async stream iterator
                    response_stream = self.client.chat.completions.create(**params)
                    
                    # Iterate SYNCHRONOUSLY through the stream object
                    # but yield asynchronously from the async generator function
                    for chunk in response_stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            # Check if delta and delta.content exist
                            if delta and delta.content:
                                content_piece = delta.content
                                # Print to console for debugging
                                print(content_piece, end='', flush=True) 
                                # Yield the content piece to the caller of this async generator
                                yield content_piece 
                    
                    # If the loop finishes without exceptions, the stream ended normally
                    print("\n") # Newline after stream ends in console
                    logger.info("流式API调用正常结束")
                    return # Successfully end the generator
                
                except (APIConnectionError, APITimeoutError) as e:
                    logger.warning(f"DeepSeek API 流式连接/超时错误(第{retries+1}次): {type(e).__name__} - {str(e)}")
                    last_error = e
                    retries += 1
                    if retries > self.max_retries:
                         logger.error(f"流式调用重试次数已达上限 ({self.max_retries})，放弃。")
                         # Re-raise the last error to signal failure to the caller
                         raise e 
                except OpenAIError as e:
                     logger.error(f"DeepSeek API 流式错误: {type(e).__name__} - {str(e)}", exc_info=True)
                     # Re-raise non-retryable errors immediately
                     raise e 
                except Exception as e:
                     logger.error(f"处理 DeepSeek 流时发生未知错误: {str(e)}", exc_info=True)
                     # Re-raise unknown errors immediately
                     raise e 

            # If the loop finished because max_retries was reached
            if last_error:
                 logger.error(f"流式调用最终失败，已重试 {self.max_retries} 次。最后错误: {last_error}")
                 # Re-raise the last known error
                 raise last_error

        except Exception as outer_e:
            # Catch any other exceptions during setup or outer logic
            logger.error(f"执行流式聊天完成请求时发生外部异常: {str(outer_e)}", exc_info=True)
            # Re-raise the exception to be handled by the caller
            raise outer_e

    async def structured_output(self,
                         prompt: str,
                         system_prompt: str = None,
                         schema: Dict = None) -> Tuple[Dict, bool]:
        """
        获取结构化JSON输出
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
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
            prompt_content = f"{prompt}\n\n请使用以下JSON模式:\n```json\n{schema_str}\n```"
        else:
             prompt_content = prompt

        messages.append({"role": "user", "content": prompt_content})
        
        # 使用JSON模式调用API
        response_text, success = await self.chat_completion(
            messages=messages,
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
                       ) -> Tuple[Dict, bool]:
        """
        执行函数调用
        
        Args:
            prompt: 用户提示
            tools: 工具定义列表
            system_prompt: 系统提示
            
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
            messages=messages,
            tools=tools
        )
        
        if not success:
            return {}, False
        
        # 提取工具调用信息
        try:
            # 这里通常需要解析响应以提取工具调用信息
            # 由于DeepSeek的函数调用可能会有特殊的返回格式，可能需要调整
            # 假设响应本身包含调用信息或纯文本
            # 尝试解析为JSON看是否是结构化响应
            try:
                response_json = json.loads(response_text)
                if "tool_calls" in response_json: # 检查 OpenAI 格式
                    return {"tool_calls": response_json["tool_calls"], "has_tool_calls": True}, True
                else: # 其他 JSON 结构
                     return {"content": response_json, "has_tool_calls": False}, True
            except json.JSONDecodeError:
                 # 不是 JSON，返回纯文本
                 return {"content": response_text, "has_tool_calls": False}, True

        except Exception as e:
            logger.error(f"处理工具调用响应时出错: {str(e)}")
            return {"error": f"处理工具调用响应时出错: {str(e)}", "raw_response": response_text}, False 