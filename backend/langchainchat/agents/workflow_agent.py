import logging # Ensure logging is imported

logger = logging.getLogger(__name__) # Setup logger earlier

from typing import Dict, Any, List, Optional, Type, Tuple
# import logging # Remove redundant import later

from langchain_core.runnables import Runnable, RunnableConfig, RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder # Removed PromptTemplate import if not needed elsewhere
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool, BaseTool # Import BaseTool as well
from langchain.agents import AgentExecutor, create_structured_chat_agent # Import AgentExecutor and constructor
# Removed unused format_tools_for_llm and parse_llm_output placeholders
# from langchain.agents.format_scratchpad.structured_chat import format_to_structured_chat_scratchpad # Might not be needed directly
# from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
from langchain_core.agents import AgentAction, AgentActionMessageLog, AgentFinish # Need AgentActionMessageLog for type hint
from langchain.tools.render import render_text_description
# --- Try importing the parser again from the original path --- 
# from langchain.agents.output_parsers.structured_chat import StructuredChatOutputParser # Original path incorrect
# --- Try importing from langchain_core ---
# from langchain_core.output_parsers.structured_chat import StructuredChatOutputParser # Also incorrect
# --- Import using the exact path from documentation ---
from langchain.agents.structured_chat.output_parser import StructuredChatOutputParser

# 导入 LangChain 工具列表
from backend.langchainchat.tools.flow_tools import flow_tools

# 根据官方文档，直接从 langchain_deepseek 导入 ChatDeepSeek (注意大小写)
from langchain_deepseek import ChatDeepSeek 
# Import Gemini class (ensure you have 'langchain-google-genai' installed)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    # Define a placeholder if not installed, so the code doesn't break
    # but clearly indicates Gemini support is missing.
    ChatGoogleGenerativeAI = Type['ChatGoogleGenerativeAI'] # type: ignore
    logger.warning("langchain-google-genai not installed. Gemini agent support will be unavailable.")

# 导入新的 Agent Prompt
from backend.langchainchat.prompts.chat_prompts import STRUCTURED_CHAT_AGENT_PROMPT

# --- Import specific formatter and other necessary components ---
# from langchain.agents import create_structured_chat_agent # Remove this if not used
# from langchain.agents.format_scratchpad.log_to_messages import format_log_to_messages # Try this formatter - Incorrect import?
import langchain.agents.format_scratchpad.log_to_messages as log_formatter_module # Import module instead

# --- Internal function specifically for DeepSeek/Structured Chat Agent ---
def _create_deepseek_structured_agent_runnable(llm: BaseChatModel, tools: List[BaseTool]) -> Runnable:
    """
    Internal helper using manual chain construction with format_log_to_messages.
    """
    prompt = STRUCTURED_CHAT_AGENT_PROMPT
    logger.debug(f"Using imported STRUCTURED_CHAT_AGENT_PROMPT for DeepSeek agent.")

    # --- Manually construct the agent chain --- 
    agent = (
        RunnablePassthrough.assign(
            # Calculate agent_scratchpad using format_log_to_messages from the imported module
            agent_scratchpad=lambda x: log_formatter_module.format_log_to_messages(x.get("intermediate_steps", [])),
            tools=lambda x: render_text_description(tools),
            tool_names=lambda x: ", ".join([t.name for t in tools])
        )
        | prompt
        | llm
        # --- Add back the Output Parser ---
        | StructuredChatOutputParser(tool_names=[t.name for t in tools])
    )
    logger.debug(f"Manually constructed agent runnable using format_log_to_messages and Output Parser.")

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors="Check your output and make sure it conforms to the JSON format instructions in the system prompt!",
        max_iterations=10,
        return_intermediate_steps=True, # Required for the lambda to get intermediate_steps
    )
    return agent_executor

# --- Factory function to create the appropriate agent based on LLM type --- 
def create_workflow_agent_runnable(llm: BaseChatModel) -> Runnable:
    """
    Factory function to create the appropriate workflow agent runnable 
    based on the provided LLM type.
    """
    # 直接使用导入的 tools 列表
    tools: List[BaseTool] = flow_tools
    if not tools:
        logger.warning("No Langchain tools were found in flow_tools. Agent might not function correctly.")

    # --- Select Agent Strategy based on LLM type --- 
    
    # Example: Check for Gemini first (requires langchain-google-genai)
    if isinstance(llm, ChatGoogleGenerativeAI):
        logger.info("Detected Gemini model. Creating Gemini-specific agent (Not Implemented Yet).")
        # TODO: Implement agent creation logic suitable for Gemini's Tool Calling
        # This might involve a different prompt and potentially a different agent constructor 
        # like create_openai_tools_agent or similar, adapted for Gemini.
        # Example placeholder:
        # from langchain.agents import create_openai_tools_agent
        # gemini_prompt = ChatPromptTemplate.from_messages([...]) # Simpler prompt for tool calling
        # gemini_agent = create_openai_tools_agent(llm, tools, gemini_prompt)
        # agent_executor = AgentExecutor(agent=gemini_agent, tools=tools, verbose=True, ...)
        # return agent_executor
        
        # For now, raise an error or fall back to the default
        # Option 1: Raise Error
        # raise NotImplementedError("Agent creation for Gemini models is not yet implemented.")
        
        # Option 2: Fallback to structured agent (might work, might not be optimal)
        logger.warning("Falling back to structured chat agent for Gemini. This might not be optimal.")
        agent_executor = _create_deepseek_structured_agent_runnable(llm, tools)
        
    # Assume DeepSeek or other models requiring structured chat approach
    # (You could add more specific checks like isinstance(llm, ChatDeepSeek))
    else:
        logger.info(f"Detected model type: {type(llm).__name__}. Creating DeepSeek/Structured Chat agent.")
        agent_executor = _create_deepseek_structured_agent_runnable(llm, tools)

    # --- Return the configured AgentExecutor --- 
    logger.info(f"Created AgentExecutor with {len(tools)} tools for {type(llm).__name__}.")
    return agent_executor

# Example Input structure expected by the AgentExecutor call:
# {
#     "input": "User's message",
#     "chat_history": [HumanMessage(...), AIMessage(...)],
#     "flow_context": {"nodes": [...], "edges": [...]}
# } 