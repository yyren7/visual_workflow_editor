"""
DeepSeek API客户端模块
提供与DeepSeek API交互的功能 (已重构以适配 Langchain BaseChatModel)
"""

import logging
import time
import uuid
import json
import os
from typing import Dict, List, Any, Optional, Union, Tuple, AsyncGenerator, Iterator, AsyncIterator # Add Iterator, AsyncIterator
from datetime import datetime

# Use AsyncOpenAI for async operations
from openai import OpenAI, AsyncOpenAI, APIConnectionError, APITimeoutError, OpenAIError, RateLimitError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionChunk
from openai.types.chat.chat_completion import ChatCompletion

# Langchain Core Imports
from langchain_core.callbacks.manager import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    ChatMessage, # Added for potential role mapping
    FunctionMessage # Added for potential role mapping
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field, SecretStr, model_validator

from backend.config import AI_CONFIG, get_log_file_path

# 使用专门的deepseek日志记录器
logger = logging.getLogger("backend.deepseek")

# (保持日志文件设置)
DEEPSEEK_LOG_FILE = get_log_file_path("deepseek_api.log")
file_handler = logging.FileHandler(DEEPSEEK_LOG_FILE)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Helper function to convert BaseMessage to OpenAI compatible dict
def _convert_message_to_dict(message: BaseMessage) -> ChatCompletionMessageParam:
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    elif isinstance(message, AIMessage):
        content = message.content
        # Handle tool calls if present
        if message.tool_calls:
            # Assuming deepseek uses OpenAI format for tool_calls
            return {"role": "assistant", "content": content or None, "tool_calls": message.tool_calls} 
        else:
            return {"role": "assistant", "content": content}
    elif isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    elif isinstance(message, ToolMessage):
        return {"role": "tool", "content": message.content, "tool_call_id": message.tool_call_id}
    # Add mapping for FunctionMessage if needed (often mapped to 'assistant' with function_call or 'function' role)
    elif isinstance(message, FunctionMessage):
         # Deepseek might expect 'function' role or use tool_calls on AIMessage
         # Assuming 'tool' role mapping for now, similar to ToolMessage but without tool_call_id?
         # Check Deepseek documentation for correct mapping
         logger.warning(f"Mapping FunctionMessage to role 'tool'. Verify Deepseek API compatibility.")
         return {"role": "tool", "content": message.content, "name": message.name} # OpenAI function role uses name
    elif isinstance(message, ChatMessage):
        return {"role": message.role, "content": message.content}
    else:
        raise TypeError(f"Got unknown message type: {type(message)}")

# Helper function to convert list of BaseMessages
def _convert_messages_to_dicts(messages: List[BaseMessage]) -> List[ChatCompletionMessageParam]:
    return [_convert_message_to_dict(m) for m in messages]


class DeepSeekLLM(BaseChatModel):
    """
    Langchain BaseChatModel兼容的 DeepSeek LLM 客户端。
    """
    client: Any = Field(default=None, exclude=True)  # OpenAI sync client
    async_client: Any = Field(default=None, exclude=True) # OpenAI async client
    
    model_name: str = Field(default=AI_CONFIG.get('DEEPSEEK_MODEL', 'deepseek-chat'), alias='model')
    temperature: float = 0.3
    max_tokens: Optional[int] = 1000
    # Use SecretStr for the API key for better security practices with Pydantic
    deepseek_api_key: Optional[SecretStr] = Field(default=AI_CONFIG.get('DEEPSEEK_API_KEY'), alias='api_key')
    deepseek_base_url: str = Field(default=AI_CONFIG.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'), alias='base_url')
    max_retries: int = 3
    retry_delay: float = 1.0

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_environment(cls, data: Any) -> Any:
        if not isinstance(data, dict):
             return data

        # Ensure API key is loaded, prioritizing constructor/Pydantic settings over direct config access
        api_key_value = data.get('deepseek_api_key') or data.get('api_key') or AI_CONFIG.get('DEEPSEEK_API_KEY')
        if not api_key_value:
            logger.warning("DeepSeek API key not found in Pydantic fields or AI_CONFIG.")
            data['deepseek_api_key'] = None
        elif isinstance(api_key_value, str):
             data['deepseek_api_key'] = SecretStr(api_key_value)

        # Set other values from config if not provided explicitly
        if data.get('model_name') is None and data.get('model') is None:
            data['model_name'] = AI_CONFIG.get('DEEPSEEK_MODEL', 'deepseek-chat')
        if data.get('deepseek_base_url') is None and data.get('base_url') is None:
            data['deepseek_base_url'] = AI_CONFIG.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')

        return data

    @model_validator(mode='after')
    def initialize_clients(self) -> 'DeepSeekLLM':
        api_key_str = self.deepseek_api_key.get_secret_value() if self.deepseek_api_key else None
        base_url = self.deepseek_base_url
        model_name = self.model_name

        if not api_key_str:
             logger.error("Cannot initialize DeepSeek clients: API key is missing.")
        else:
             logger.info(f"Initializing DeepSeek clients for model: {model_name}")
             self.client = OpenAI(
                 api_key=api_key_str,
                 base_url=base_url,
                 max_retries=0
             )
             self.async_client = AsyncOpenAI(
                 api_key=api_key_str,
                 base_url=base_url,
                 max_retries=0
             )
        return self

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "deepseek"

    def _prepare_request_params(self, messages: List[BaseMessage], stop: Optional[List[str]], **kwargs: Any) -> Dict[str, Any]:
        """Helper to prepare the parameters for the OpenAI API call."""
        req_messages = _convert_messages_to_dicts(messages)
        params = {
            "model": self.model_name,
            "messages": req_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # Handle potential 'tools' and 'tool_choice' from kwargs
            "tools": kwargs.get("tools"),
            "tool_choice": kwargs.get("tool_choice"),
            # Handle potential 'response_format' (for JSON mode)
            "response_format": kwargs.get("response_format"),
            "stream": False # Default for non-streaming methods
        }
        if stop:
            params["stop"] = stop
        # Filter out None values for cleaner API calls
        return {k: v for k, v in params.items() if v is not None}

    # --- Core Generation Logic --- 

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Sync, non-streaming generation."""
        if self.client is None:
            raise ValueError("DeepSeek sync client not initialized. Check API key.")

        request_params = self._prepare_request_params(messages, stop, **kwargs)
        request_params["stream"] = False 
        response_message_content = ""
        response_tool_calls = None
        llm_output = {}
        retries = 0
        last_error = None
        
        logger.info(f"Calling DeepSeek _generate for model {self.model_name}")
        logger.debug(f"_generate request params: {json.dumps(request_params, indent=2, default=str)}")

        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"Retrying DeepSeek sync call (Attempt {retries+1}/{self.max_retries+1}, Delay: {delay:.2f}s)")
                time.sleep(delay)
            try:
                start_time = time.monotonic()
                response: ChatCompletion = self.client.chat.completions.create(**request_params)
                duration = time.monotonic() - start_time
                logger.info(f"DeepSeek sync call successful (Duration: {duration:.2f}s)")
                
                choice = response.choices[0]
                message = choice.message
                response_message_content = message.content or ""
                response_tool_calls = message.tool_calls
                llm_output = response.model_dump() # Get usage and other info
                
                # Log response details
                log_msg_preview = response_message_content[:200] + ('...' if len(response_message_content)>200 else '')
                log_tool_call_info = f", Tool Calls: {len(response_tool_calls)}" if response_tool_calls else ""
                logger.debug(f"_generate response received: FinishReason='{choice.finish_reason}', Content='{log_msg_preview}'{log_tool_call_info}")
                logger.debug(f"_generate full LLM output: {llm_output}")
                
                # Create AIMessage
                ai_message = AIMessage(
                     content=response_message_content,
                     tool_calls=response_tool_calls
                )
                generation = ChatGeneration(message=ai_message)
                return ChatResult(generations=[generation], llm_output=llm_output)
            
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                logger.warning(f"DeepSeek API retryable error (Attempt {retries+1}): {type(e).__name__} - {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"DeepSeek API non-retryable error: {type(e).__name__} - {str(e)}")
                last_error = e
                break # Don't retry for these errors
            except Exception as e:
                logger.error(f"Unknown error during DeepSeek sync call: {str(e)}", exc_info=True)
                last_error = e
                break

        # If loop finishes without success
        raise last_error or RuntimeError(f"Failed to get response from DeepSeek after {self.max_retries+1} attempts.")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async, non-streaming generation."""
        if self.async_client is None:
            raise ValueError("DeepSeek async client not initialized. Check API key.")

        request_params = self._prepare_request_params(messages, stop, **kwargs)
        request_params["stream"] = False
        response_message_content = ""
        response_tool_calls = None
        llm_output = {}
        retries = 0
        last_error = None

        logger.info(f"Calling DeepSeek _agenerate for model {self.model_name}")
        logger.debug(f"_agenerate request params: {json.dumps(request_params, indent=2, default=str)}")

        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"Retrying DeepSeek async call (Attempt {retries+1}/{self.max_retries+1}, Delay: {delay:.2f}s)")
                await asyncio.sleep(delay)
            try:
                start_time = time.monotonic()
                response: ChatCompletion = await self.async_client.chat.completions.create(**request_params)
                duration = time.monotonic() - start_time
                logger.info(f"DeepSeek async call successful (Duration: {duration:.2f}s)")
                
                choice = response.choices[0]
                message = choice.message
                response_message_content = message.content or ""
                response_tool_calls = message.tool_calls 
                llm_output = response.model_dump()

                log_msg_preview = response_message_content[:200] + ('...' if len(response_message_content)>200 else '')
                log_tool_call_info = f", Tool Calls: {len(response_tool_calls)}" if response_tool_calls else ""
                logger.debug(f"_agenerate response received: FinishReason='{choice.finish_reason}', Content='{log_msg_preview}'{log_tool_call_info}")
                logger.debug(f"_agenerate full LLM output: {llm_output}")

                ai_message = AIMessage(
                    content=response_message_content,
                    tool_calls=response_tool_calls
                )
                generation = ChatGeneration(message=ai_message)
                return ChatResult(generations=[generation], llm_output=llm_output)

            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                logger.warning(f"DeepSeek API async retryable error (Attempt {retries+1}): {type(e).__name__} - {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"DeepSeek API async non-retryable error: {type(e).__name__} - {str(e)}")
                last_error = e
                break
            except Exception as e:
                logger.error(f"Unknown error during DeepSeek async call: {str(e)}", exc_info=True)
                last_error = e
                break

        raise last_error or RuntimeError(f"Failed to get async response from DeepSeek after {self.max_retries+1} attempts.")

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Sync, streaming generation."""
        if self.client is None:
            raise ValueError("DeepSeek sync client not initialized. Check API key.")

        request_params = self._prepare_request_params(messages, stop, **kwargs)
        request_params["stream"] = True
        default_chunk_class = AIMessageChunk
        retries = 0
        last_error = None

        logger.info(f"Calling DeepSeek _stream for model {self.model_name}")
        logger.debug(f"_stream request params: {json.dumps(request_params, indent=2, default=str)}")
        
        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"Retrying DeepSeek sync stream (Attempt {retries+1}/{self.max_retries+1}, Delay: {delay:.2f}s)")
                time.sleep(delay)
            try:
                stream_iterator = self.client.chat.completions.create(**request_params)
                logger.info(f"DeepSeek sync stream initiated.")
                for chunk in stream_iterator:
                    if not isinstance(chunk, ChatCompletionChunk):
                        continue
                    delta = chunk.choices[0].delta
                    chunk_content = delta.content or ""
                    chunk_tool_calls = delta.tool_calls # This will be List[ToolCallChunk] or None
                    
                    # Conditionally add tool_call_chunks to avoid validation error when it's None
                    chunk_kwargs = {"content": chunk_content}
                    if chunk_tool_calls is not None:
                        chunk_kwargs["tool_call_chunks"] = chunk_tool_calls
                    # Replace the original message_chunk line with this one using kwargs
                    message_chunk = default_chunk_class(**chunk_kwargs)

                    gen_chunk = ChatGenerationChunk(message=message_chunk)
                    if run_manager: # Pass chunk to callbacks
                         run_manager.on_llm_new_token(chunk_content, chunk=gen_chunk)
                    yield gen_chunk
                # Stream finished successfully
                logger.info("DeepSeek sync stream finished.")
                return

            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                logger.warning(f"DeepSeek API sync stream retryable error (Attempt {retries+1}): {type(e).__name__} - {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"DeepSeek API sync stream non-retryable error: {type(e).__name__} - {str(e)}")
                last_error = e
                break
            except Exception as e:
                logger.error(f"Unknown error during DeepSeek sync stream: {str(e)}", exc_info=True)
                last_error = e
                break

        raise last_error or RuntimeError(f"Failed to get sync stream from DeepSeek after {self.max_retries+1} attempts.")

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Async, streaming generation."""
        if self.async_client is None:
            raise ValueError("DeepSeek async client not initialized. Check API key.")

        request_params = self._prepare_request_params(messages, stop, **kwargs)
        request_params["stream"] = True
        default_chunk_class = AIMessageChunk
        retries = 0
        last_error = None

        logger.info(f"Calling DeepSeek _astream for model {self.model_name}")
        logger.debug(f"_astream request params: {json.dumps(request_params, indent=2, default=str)}")

        while retries <= self.max_retries:
            if retries > 0:
                delay = self.retry_delay * (2 ** (retries - 1))
                logger.info(f"Retrying DeepSeek async stream (Attempt {retries+1}/{self.max_retries+1}, Delay: {delay:.2f}s)")
                await asyncio.sleep(delay)
            try:
                stream_iterator = await self.async_client.chat.completions.create(**request_params)
                logger.info(f"DeepSeek async stream initiated.")
                async for chunk in stream_iterator:
                    if not isinstance(chunk, ChatCompletionChunk):
                        continue
                    delta = chunk.choices[0].delta
                    chunk_content = delta.content or ""
                    chunk_tool_calls = delta.tool_calls # List[ToolCallChunk] or None
                    
                    # Conditionally add tool_call_chunks to avoid validation error when it's None
                    chunk_kwargs = {"content": chunk_content}
                    if chunk_tool_calls is not None:
                        chunk_kwargs["tool_call_chunks"] = chunk_tool_calls
                    # Replace the original message_chunk line with this one using kwargs
                    message_chunk = default_chunk_class(**chunk_kwargs)

                    gen_chunk = ChatGenerationChunk(message=message_chunk)
                    if run_manager:
                         await run_manager.on_llm_new_token(chunk_content, chunk=gen_chunk)
                    yield gen_chunk
                logger.info("DeepSeek async stream finished.")
                return

            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                logger.warning(f"DeepSeek API async stream retryable error (Attempt {retries+1}): {type(e).__name__} - {str(e)}")
                last_error = e
                retries += 1
            except OpenAIError as e:
                logger.error(f"DeepSeek API async stream non-retryable error: {type(e).__name__} - {str(e)}")
                last_error = e
                break
            except Exception as e:
                logger.error(f"Unknown error during DeepSeek async stream: {str(e)}", exc_info=True)
                last_error = e
                break

        raise last_error or RuntimeError(f"Failed to get async stream from DeepSeek after {self.max_retries+1} attempts.")

    # --- Remove old custom methods --- 
    # async def chat_completion(...) -> REMOVED
    # async def stream_chat_completion(...) -> REMOVED
    # async def structured_output(...) -> REMOVED
    # async def function_calling(...) -> REMOVED