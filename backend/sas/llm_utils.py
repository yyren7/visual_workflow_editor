import logging
import json
import asyncio
from typing import List, Optional, Dict, Any, Type, AsyncGenerator, AsyncIterable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage, AIMessageChunk
from langchain_core.runnables import RunnableGenerator
from pydantic import BaseModel # For Type[BaseModel] for json_schema

from .prompt_loader import get_filled_prompt

logger = logging.getLogger(__name__)

async def streaming_text_parser(chunks: AsyncIterable[AIMessageChunk]) -> AsyncGenerator[str, None]:
    """
    A custom parser that processes a stream of AIMessageChunk objects
    and yields the string content of each chunk.
    """
    async for chunk in chunks:
        if hasattr(chunk, 'content') and chunk.content is not None:
            yield str(chunk.content)

async def invoke_llm_for_text_output(
    llm: BaseChatModel,
    system_prompt_content: str,
    user_message_content: str,
    message_history: Optional[List[BaseMessage]] = None,
) -> AsyncGenerator[str, None]:
    # To address the Gemini deprecation warning for SystemMessage,
    # we use a HumanMessage to convey system-level instructions.
    messages: List[BaseMessage] = [HumanMessage(content=system_prompt_content)]
    if message_history:
        messages.extend(message_history)
    messages.append(HumanMessage(content=user_message_content))

    logger.info("Invoking LLM for raw text output.")

    stream_for_gemini = "gemini" in getattr(llm, 'model', '').lower()
    streaming_attr = getattr(llm, 'streaming', False)
    stream_for_deepseek = streaming_attr and "deepseek" in getattr(llm, 'model', '').lower()
    should_stream_llm = stream_for_gemini or stream_for_deepseek

    if should_stream_llm:
        logger.info(f"LLM UTILS: Using streaming for LLM text output (Gemini: {stream_for_gemini}, DeepSeek: {stream_for_deepseek}).")
        try:
            # Directly iterate over the stream and yield the content of each chunk.
            # This is the most direct way and avoids type-checking issues with parsers.
            async for chunk in llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content is not None:
                    yield str(chunk.content)
        except Exception as e:
            logger.error(f"LLM streaming call for string output failed. Error: {e}", exc_info=True)
            raise
    else:
        try:
            # For non-streaming, directly invoke and yield the content as a string.
            ai_response = await llm.ainvoke(messages)
            yield str(ai_response.content)
        except Exception as e:
            logger.error(f"LLM call for string output (non-streaming) failed. Error: {e}", exc_info=True)
            raise

async def invoke_llm_for_json_output(
    llm: BaseChatModel,
    system_prompt_template_name: str,
    placeholder_values: Dict[str, str],
    user_message_content: str,
    message_history: Optional[List[BaseMessage]] = None,
    json_schema: Optional[Type[BaseModel]] = None,
) -> Dict[str, Any]:
    if not json_schema:
        logger.error("json_schema must be provided to invoke_llm_for_json_output.")
        return {"error": "json_schema must be provided to invoke_llm_for_json_output."}

    filled_system_prompt = get_filled_prompt(system_prompt_template_name, placeholder_values)
    if not filled_system_prompt:
        logger.error(f"Failed to load or fill system prompt: {system_prompt_template_name}")
        return {"error": f"Failed to load or fill system prompt: {system_prompt_template_name}"}

    messages: List[BaseMessage] = [HumanMessage(content=filled_system_prompt)]
    if message_history:
        messages.extend(message_history)
    messages.append(HumanMessage(content=user_message_content))

    logger.info(f"Invoking LLM. System prompt template: {system_prompt_template_name}, Expecting JSON for schema: {json_schema.__name__}")
    structured_llm = llm.with_structured_output(json_schema)
    raw_output_for_debug = "Not available or attempt failed."
    try:
        ai_response = await structured_llm.ainvoke(messages)
        
        if ai_response is None:
            logger.error(f"LLM with_structured_output for schema {json_schema.__name__} returned None. This is unexpected.")
            try:
                logger.info(f"Attempting to get raw output after structured_llm returned None for schema {json_schema.__name__}...")
                raw_output_msg = await llm.ainvoke(messages)
                raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
                logger.info(f"Raw output obtained after None from structured_llm: {raw_output_for_debug[:500]}...")
            except Exception as e_raw_after_none:
                logger.error(f"Failed to get raw output after structured_llm returned None for schema {json_schema.__name__}. Error: {e_raw_after_none}", exc_info=True)
                raw_output_for_debug = f"Failed to fetch raw output after None: {e_raw_after_none}"
            return {"error": f"LLM with_structured_output returned None for schema {json_schema.__name__}.", "raw_output": raw_output_for_debug}

        if isinstance(ai_response, BaseModel):
            return ai_response.dict(exclude_none=True)
        else:
            logger.error(f"LLM with_structured_output did not return a Pydantic model instance for schema {json_schema.__name__}. Got type: {type(ai_response)}. Value: {str(ai_response)[:200]}...")
            try:
                logger.info(f"Attempting to get raw output after receiving non-Pydantic type {type(ai_response)} for schema {json_schema.__name__}...")
                raw_output_msg = await llm.ainvoke(messages)
                raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
                logger.info(f"Raw output obtained after non-Pydantic response: {raw_output_for_debug[:500]}...")
            except Exception as e_raw_non_pydantic:
                logger.error(f"Failed to get raw output after non-Pydantic response for schema {json_schema.__name__}. Error: {e_raw_non_pydantic}", exc_info=True)
                raw_output_for_debug = f"Failed to fetch raw output after non-Pydantic: {e_raw_non_pydantic}"
            return {"error": f"LLM structured output did not return a Pydantic model for schema {json_schema.__name__}. Got type: {type(ai_response)}", "raw_output": raw_output_for_debug}

    except Exception as e:
        logger.error(f"LLM call with_structured_output failed for schema {json_schema.__name__}. Error: {e}", exc_info=True)
        try:
            logger.info(f"Attempting to get raw output after structured_output exception for schema {json_schema.__name__}...")
            raw_output_msg = await llm.ainvoke(messages)
            raw_output_for_debug = str(raw_output_msg.content) if hasattr(raw_output_msg, 'content') else str(raw_output_msg)
            logger.info(f"Raw output obtained after exception: {raw_output_for_debug[:500]}...")
        except Exception as e_raw:
            logger.error(f"Failed to get raw output from LLM after structured output error for schema {json_schema.__name__}. Error: {e_raw}", exc_info=True)
            raw_output_for_debug = f"Failed to fetch raw output after exception: {e_raw}"
        return {"error": f"LLM call with_structured_output failed for schema {json_schema.__name__}.", "details": str(e), "raw_output": raw_output_for_debug} 