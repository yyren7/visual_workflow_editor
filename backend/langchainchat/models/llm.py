from typing import Dict, Any, Optional, List, Union, Callable, Type
from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import ChatGenerationChunk, ChatResult, LLMResult, ChatGeneration
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    FunctionMessage,
)
from pydantic import Field, root_validator
import json
import logging
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessage, 
    ChatCompletionChunk, 
    ChatCompletion, 
    ChatCompletionMessageParam
)
from openai._exceptions import OpenAIError, APIConnectionError, APITimeoutError
import asyncio
import time
from contextlib import contextmanager
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.langchainchat.config import settings
from backend.langchainchat.utils.logging import logger
import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_community.chat_models import ChatZhipuAI

class DeepSeekChatModel(BaseChatModel):
    """
    LangChain封装的DeepSeek聊天模型
    
    基于OpenAI客户端实现，支持同步和异步操作
    """
    
    client: Any = None
    async_client: Any = None
    
    model_name: str = settings.DEEPSEEK_MODEL
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = settings.DEFAULT_TEMPERATURE
    max_tokens: Optional[int] = settings.DEFAULT_MAX_TOKENS
    top_p: float = 0.95
    
    streaming: bool = False
    n: int = 1
    
    openai_api_key: str = settings.DEEPSEEK_API_KEY
    openai_api_base: str = settings.DEEPSEEK_BASE_URL
    openai_proxy: Optional[str] = None
    request_timeout: Optional[float] = 60.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    def __init__(
        self,
        model_name: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        top_p: float = 0.95,
        openai_api_key: Optional[str] = None,
        openai_api_base: Optional[str] = None,
        **kwargs
    ):
        """初始化DeepSeek模型"""
        super().__init__(**kwargs)
        from dotenv import load_dotenv
        # 重新加载环境变量，确保能获取到最新值 - 显式指定.env文件路径
        workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env')
        load_dotenv(dotenv_path=workspace_env_path, override=True)
        
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        
        # 首先直接从环境变量获取API密钥，优先级最高
        env_api_key = os.environ.get("DEEPSEEK_API_KEY")
        if env_api_key:
            logger.info("从环境变量读取DEEPSEEK_API_KEY")
            self.openai_api_key = env_api_key
        else:
            # 其次使用传入的参数
            if openai_api_key:
                self.openai_api_key = openai_api_key
            # 最后使用settings中的值
            else:
                self.openai_api_key = settings.DEEPSEEK_API_KEY
                logger.info("使用settings中的DEEPSEEK_API_KEY")
        
        # 同样处理API基础URL
        env_api_base = os.environ.get("DEEPSEEK_BASE_URL")
        if env_api_base:
            logger.info("从环境变量读取DEEPSEEK_BASE_URL")
            self.openai_api_base = env_api_base
        else:
            self.openai_api_base = openai_api_base or settings.DEEPSEEK_BASE_URL
        
        # 添加更详细的日志，显示API密钥的一部分（但不是完整密钥）
        key_prefix = self.openai_api_key[:8] if self.openai_api_key and len(self.openai_api_key) > 10 else ""
        key_suffix = self.openai_api_key[-4:] if self.openai_api_key and len(self.openai_api_key) > 10 else ""
        key_length = len(self.openai_api_key) if self.openai_api_key else 0
        
        logger.info(f"API配置验证通过: ")
        logger.info(f"- 基础URL: {self.openai_api_base}")
        logger.info(f"- API密钥: {key_prefix}...{key_suffix} (长度: {key_length}字符)")
        
        # 验证密钥格式
        if self.openai_api_key and not self.openai_api_key.startswith("sk-"):
            logger.warning(f"警告: API密钥格式可能不正确 - 应该以'sk-'开头")
        
        # 列出环境变量（仅用于调试）
        logger.debug(f"可用环境变量: {list(os.environ.keys())}")
        
        self.validate_environment()
        self.client = self._create_client()
        
    def validate_environment(self) -> None:
        """验证环境变量，确保必要的配置存在"""
        if not self.openai_api_key:
            # 再次尝试直接从环境变量读取
            env_api_key = os.environ.get("DEEPSEEK_API_KEY")
            if env_api_key:
                logger.info("验证环境时从环境变量获取到DEEPSEEK_API_KEY")
                self.openai_api_key = env_api_key
            else:
                raise ValueError(
                    "DeepSeek API密钥未设置。请设置 DEEPSEEK_API_KEY 环境变量或在初始化时提供 openai_api_key 参数。"
                )
        
        if not self.openai_api_base:
            # 再次尝试直接从环境变量读取
            env_api_base = os.environ.get("DEEPSEEK_BASE_URL")
            if env_api_base:
                logger.info("验证环境时从环境变量获取到DEEPSEEK_BASE_URL")
                self.openai_api_base = env_api_base
            else:
                # 使用默认值
                self.openai_api_base = "https://api.deepseek.com"
                logger.info(f"未设置DEEPSEEK_BASE_URL，使用默认值: {self.openai_api_base}")
        
        # 添加更详细的日志，显示API密钥的一部分（但不是完整密钥）
        key_prefix = self.openai_api_key[:8] if self.openai_api_key and len(self.openai_api_key) > 10 else ""
        key_suffix = self.openai_api_key[-4:] if self.openai_api_key and len(self.openai_api_key) > 10 else ""
        key_length = len(self.openai_api_key) if self.openai_api_key else 0
        
        logger.info(f"API配置验证通过: ")
        logger.info(f"- 基础URL: {self.openai_api_base}")
        logger.info(f"- API密钥: {key_prefix}...{key_suffix} (长度: {key_length}字符)")
        
        # 验证密钥格式
        if self.openai_api_key and not self.openai_api_key.startswith("sk-"):
            logger.warning(f"警告: API密钥格式可能不正确 - 应该以'sk-'开头")
        
        # 列出环境变量（仅用于调试）
        logger.debug(f"可用环境变量: {list(os.environ.keys())}")
    
    def _create_client(self) -> Any:
        """创建OpenAI兼容客户端"""
        api_key = self.openai_api_key
        
        # 检查API密钥格式，并根据设置添加前缀
        if api_key:
            if not api_key.startswith("sk-") and settings.API_KEY_ADD_PREFIX:
                logger.info("根据配置添加'sk-'前缀到API密钥")
                api_key = f"sk-{api_key}"
            elif not api_key.startswith("sk-"):
                logger.warning(f"警告: API密钥格式可能不正确 - 应该以'sk-'开头，而当前密钥以'{api_key[:3]}...'开头")
        
        # 选择API端点
        api_base = self.openai_api_base
        if settings.ALTERNATIVE_BASE_URL:
            logger.info(f"使用替代API端点: {settings.ALTERNATIVE_BASE_URL}")
            api_base = settings.ALTERNATIVE_BASE_URL
        
        # 创建客户端并记录详细信息
        client = OpenAI(
            api_key=api_key,
            base_url=api_base or "https://api.deepseek.com"
        )
        
        logger.info(f"已创建API客户端: 基础URL={api_base}")
        
        return client
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return "deepseek-chat"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """返回标识参数"""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p
        }
    
    def _convert_message_to_dict(self, message: BaseMessage) -> Dict:
        """将LangChain消息转换为API请求的字典格式"""
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        elif isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            response = {"role": "assistant", "content": message.content}
            if hasattr(message, "function_call"):
                response["function_call"] = message.function_call
            return response
        elif isinstance(message, FunctionMessage):
            return {
                "role": "function",
                "content": message.content,
                "name": message.name
            }
        elif isinstance(message, ChatMessage):
            return {"role": message.role, "content": message.content}
        else:
            raise ValueError(f"不支持的消息类型: {type(message)}")
    
    def _create_chat_result(self, response: Union[ChatCompletion, ChatCompletionChunk]) -> ChatResult:
        """从API响应创建ChatResult对象"""
        generations = []
        
        if hasattr(response, "choices"):
            for choice in response.choices:
                message = choice.message if hasattr(choice, "message") else None
                
                if message:
                    text = message.content
                    generation_info = {}
                    
                    if hasattr(message, "function_call") and message.function_call:
                        generation_info["function_call"] = message.function_call
                        
                    ai_msg = AIMessage(content=text)
                    if generation_info:
                        ai_msg.additional_kwargs.update(generation_info)
                    
                    generations.append(ChatGeneration(message=ai_msg, generation_info=generation_info))
        
        return ChatResult(generations=generations)
    
    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """执行同步生成请求"""
        message_dicts = [self._convert_message_to_dict(m) for m in messages]
        params = {
            "model": self.model_name,
            "messages": message_dicts,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            **self.model_kwargs
        }
        
        # 添加停止序列（如果提供）
        if stop:
            params["stop"] = stop
            
        # 合并传入的关键字参数
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        # 记录请求详情
        logger.info(f"DeepSeek API请求: 模型={self.model_name}, 消息数量={len(message_dicts)}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"完整请求内容: {json.dumps(params, ensure_ascii=False)}")
        
        # 执行请求，带有重试机制
        response = None
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"重试DeepSeek API请求 (第{retries}次, 延迟{delay:.2f}秒)")
                time.sleep(delay)
                
            try:
                # 使用适配方式处理回调
                if run_manager:
                    try:
                        # 尝试使用新版API (如果有on_llm_start方法)
                        if hasattr(run_manager, "on_llm_start"):
                            run_manager.on_llm_start(
                                {"name": self._llm_type},
                                message_dicts,
                            )
                        # 兼容可能的新命名方式
                        elif hasattr(run_manager, "on_llm_run_start"):
                            run_manager.on_llm_run_start(
                                {"name": self._llm_type},
                                message_dicts,
                            )
                        # 如果都没有，记录一条警告但继续执行
                        else:
                            logger.warning("无法找到适当的回调方法，跳过启动回调")
                    except Exception as callback_error:
                        logger.warning(f"执行启动回调时出错: {str(callback_error)}")
                    
                response = self.client.chat.completions.create(**params)
                break
                
            except (APIConnectionError, APITimeoutError) as e:
                logger.warning(f"DeepSeek API连接错误(第{retries+1}次): {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"DeepSeek API错误: {str(e)}")
                raise
                
        if response is None:
            raise last_error or ValueError("DeepSeek API请求失败")
            
        chat_result = self._create_chat_result(response)
        
        # 使用适配方式处理回调
        if run_manager:
            try:
                # 尝试使用新版API (如果有on_llm_end方法)
                if hasattr(run_manager, "on_llm_end"):
                    run_manager.on_llm_end(chat_result)
                # 兼容可能的新命名方式
                elif hasattr(run_manager, "on_llm_run_end"):
                    run_manager.on_llm_run_end(chat_result)
                # 如果都没有，记录一条警告但继续执行
                else:
                    logger.warning("无法找到适当的回调方法，跳过结束回调")
            except Exception as callback_error:
                logger.warning(f"执行结束回调时出错: {str(callback_error)}")
            
        # 记录响应
        try:
            content = chat_result.generations[0].message.content
            logger.info(f"DeepSeek API响应: 长度={len(content)} 字符")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"完整响应内容: {content}")
        except (IndexError, AttributeError):
            logger.warning("无法记录API响应内容")
            
        return chat_result
    
    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """执行异步生成请求"""
        message_dicts = [self._convert_message_to_dict(m) for m in messages]
        params = {
            "model": self.model_name,
            "messages": message_dicts,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            **self.model_kwargs
        }
        
        # 添加停止序列（如果提供）
        if stop:
            params["stop"] = stop
            
        # 合并传入的关键字参数
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        # 记录请求详情
        logger.info(f"异步DeepSeek API请求: 模型={self.model_name}, 消息数量={len(message_dicts)}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"完整请求内容: {json.dumps(params, ensure_ascii=False)}")
        
        # 执行请求，带有重试机制
        response = None
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"重试异步DeepSeek API请求 (第{retries}次, 延迟{delay:.2f}秒)")
                await asyncio.sleep(delay)
                
            try:
                # 更改异步回调方式，兼容新版LangChain
                if run_manager:
                    # 使用适配方式处理回调
                    try:
                        # 尝试使用新版API (如果有on_llm_start方法)
                        if hasattr(run_manager, "on_llm_start"):
                            await run_manager.on_llm_start(
                                {"name": self._llm_type},
                                message_dicts,
                            )
                        # 兼容可能的新命名方式
                        elif hasattr(run_manager, "on_llm_run_start"):
                            await run_manager.on_llm_run_start(
                                {"name": self._llm_type},
                                message_dicts,
                            )
                        # 如果都没有，记录一条警告但继续执行
                        else:
                            logger.warning("无法找到适当的异步回调方法，跳过启动回调")
                    except Exception as callback_error:
                        logger.warning(f"执行启动回调时出错: {str(callback_error)}")
                    
                # 创建异步客户端（如果需要）
                if not hasattr(self, "async_client") or self.async_client is None:
                    # 再次检查环境变量中的API密钥
                    api_key = self.openai_api_key
                    env_api_key = os.environ.get("DEEPSEEK_API_KEY")
                    if env_api_key:
                        logger.info("创建异步客户端时从环境变量读取DEEPSEEK_API_KEY")
                        api_key = env_api_key
                        
                    # 检查环境变量中的API基础URL
                    api_base = self.openai_api_base
                    env_api_base = os.environ.get("DEEPSEEK_BASE_URL")
                    if env_api_base:
                        logger.info("创建异步客户端时从环境变量读取DEEPSEEK_BASE_URL")
                        api_base = env_api_base
                    
                    # 使用替代API端点（如果配置）
                    if settings.ALTERNATIVE_BASE_URL:
                        logger.info(f"异步客户端使用替代API端点: {settings.ALTERNATIVE_BASE_URL}")
                        api_base = settings.ALTERNATIVE_BASE_URL
                    
                    # 检查API密钥格式，并根据设置添加前缀
                    if api_key:
                        if not api_key.startswith("sk-") and settings.API_KEY_ADD_PREFIX:
                            logger.info("为异步客户端根据配置添加'sk-'前缀到API密钥")
                            api_key = f"sk-{api_key}"
                        elif not api_key.startswith("sk-"):
                            logger.warning(f"警告: 异步客户端API密钥格式可能不正确 - 应该以'sk-'开头")
                        
                    self.async_client = AsyncOpenAI(
                        api_key=api_key,
                        base_url=api_base or "https://api.deepseek.com"
                    )
                    
                    logger.info(f"已创建异步API客户端: 基础URL={api_base}")
                    
                # 使用异步客户端发送请求    
                response = await self.async_client.chat.completions.create(**params)
                break
                
            except (APIConnectionError, APITimeoutError) as e:
                logger.warning(f"异步DeepSeek API连接错误(第{retries+1}次): {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"异步DeepSeek API错误: {str(e)}")
                raise
                
        if response is None:
            raise last_error or ValueError("异步DeepSeek API请求失败")
            
        chat_result = self._create_chat_result(response)
        
        # 更改异步回调方式，兼容新版LangChain
        if run_manager:
            try:
                # 尝试使用新版API (如果有on_llm_end方法)
                if hasattr(run_manager, "on_llm_end"):
                    await run_manager.on_llm_end(chat_result)
                # 兼容可能的新命名方式
                elif hasattr(run_manager, "on_llm_run_end"):
                    await run_manager.on_llm_run_end(chat_result)
                # 如果都没有，记录一条警告但继续执行
                else:
                    logger.warning("无法找到适当的异步回调方法，跳过结束回调")
            except Exception as callback_error:
                logger.warning(f"执行结束回调时出错: {str(callback_error)}")
            
        # 记录响应
        try:
            content = chat_result.generations[0].message.content
            logger.info(f"异步DeepSeek API响应: 长度={len(content)} 字符")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"完整响应内容: {content}")
        except (IndexError, AttributeError):
            logger.warning("无法记录异步API响应内容")
            
        return chat_result

def get_chat_model() -> BaseChatModel:
    """
    获取聊天模型实例
    
    Returns:
        配置好的聊天模型实例
    """
    logger.info(f"初始化聊天模型: {settings.CHAT_MODEL_NAME}")
    
    # 使用DeepSeek模型
    if settings.USE_DEEPSEEK:
        logger.info("使用DeepSeek模型")
        return DeepSeekChatModel(
            model_name=settings.CHAT_MODEL_NAME,
            temperature=settings.DEFAULT_TEMPERATURE,
            max_tokens=settings.DEFAULT_MAX_TOKENS,
            openai_api_key=settings.DEEPSEEK_API_KEY,
            openai_api_base=settings.DEEPSEEK_BASE_URL
        )
    
    # 默认使用OpenAI模型
    logger.info("使用OpenAI兼容模型")
    from langchain_openai import ChatOpenAI
    
    return ChatOpenAI(
        model_name=settings.CHAT_MODEL_NAME,
        temperature=settings.DEFAULT_TEMPERATURE,
        max_tokens=settings.DEFAULT_MAX_TOKENS,
        openai_api_key=settings.OPENAI_API_KEY
    ) 