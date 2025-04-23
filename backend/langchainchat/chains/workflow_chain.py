import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
import json

from langchain.chains.base import Chain
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableConfig
from langchain_core.output_parsers import StrOutputParser
# from backend.langchainchat.prompts.prompt_expansion import PromptExpansion
from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
from backend.langchainchat.tools.executor import ToolExecutor
from backend.langchainchat.output_parsers.structured_parser import StructuredOutputParser # 虽然在 ToolExecutor 中使用，但链本身可能也需要
# 从 pydantic 导入 BaseModel
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from database.connection import get_db_context # <--- 新增导入

# 导入依赖组件
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM
# Removed import of non-existent PromptExpansion service
# from backend.langchainchat.prompts.expansion_service import PromptExpansion # 假设此类存在
# Import the template directly if needed
from backend.langchainchat.prompts.chat_prompts import WORKFLOW_CHAT_PROMPT_TEMPLATE_WITH_CONTEXT
# 导入工具定义 (如果链需要直接访问它们)
from backend.langchainchat.tools.definitions import deepseek_tools_definition, ToolResult, NodeParams, ConnectionParams
# 导入内存组件 (假设存在)
# from backend.langchainchat.memory.base import BaseChatMemory
# 导入应用层服务 (需要调整路径和依赖注入方式)
# from backend.app.services.flow_service import FlowService
# from backend.app.services.user_service import UserService
# from backend.app.services.flow_variable_service import FlowVariableService

# 导入 CallbackManagerForChainRun
from langchain_core.callbacks.manager import CallbackManagerForChainRun

# 不再需要在此导入 DbChatMemory
# from backend.langchainchat.memory.db_chat_memory import DbChatMemory

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage # 确保导入
from database.models import Flow # 导入 Flow 模型用于查询上下文

logger = logging.getLogger(__name__)

# 定义链的输入和输出模型
class WorkflowChainInput(BaseModel):
    user_input: str
    # db_session: Session # <-- 不再需要 db_session
    flow_id: Optional[str] = None # 添加 flow_id
    chat_id: Optional[str] = None # <--- 添加 chat_id
    history: List[BaseMessage] = Field(default_factory=list) # <--- 新增 history 字段

    # 允许任意类型，例如 SQLAlchemy Session
    model_config = ConfigDict(arbitrary_types_allowed=True)

class WorkflowChainOutput(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = "" # Will hold text summary OR final message after tools
    error: Optional[str] = None
    # NEW: Change stream_generator to event_stream yielding dictionaries
    event_stream: Optional[AsyncGenerator[Dict[str, Any], None]] = None
    tool_calls_info: Optional[List[Dict[str, Any]]] = None # Info about tools being called
    tool_results_info: Optional[List[Dict[str, Any]]] = None # Info about tool execution results

    # Allow AsyncGenerator type
    model_config = ConfigDict(arbitrary_types_allowed=True)

class WorkflowChain(Chain):
    """
    负责处理用户输入，编排 LLM 调用、上下文检索、工具执行，
    最终生成流程图节点/连接或自然语言回复。
    """
    input_key: str = "user_input"  # 定义主要的文本输入键
    output_key: str = "result"     # 定义主要的输出键
    # db_session_key: str = "db_session" # <-- 移除
    flow_id_key: str = "flow_id" # 定义流程图 ID 键
    chat_id_key: str = "chat_id" # <--- 新增 chat_id 键
    history_key: str = "history" # <--- 新增 history 输入键

    # 注入的依赖组件
    llm: DeepSeekLLM
    # Removed prompt_expander attribute
    # prompt_expander: Optional[PromptExpansion] = None
    retriever: Optional[EmbeddingRetriever] = None    # 检索器 (可选)
    tool_executor: Optional[ToolExecutor] = None      # 工具执行器 (可选)
    output_parser: Optional[StructuredOutputParser] = None # 结构化输出解析器 (可选)
    # memory: Optional[BaseChatMemory] = None # 不再需要内部 memory

    # 注入的应用服务 (需要通过外部机制传入 db_session)
    # flow_service: Optional[FlowService] = None
    # user_service: Optional[UserService] = None
    # variable_service: Optional[FlowVariableService] = None

    # --- 新增：配置历史消息数量限制 ---
    history_max_messages: int = 10 # 例如，只保留最近10条消息 (user + assistant)

    @property
    def input_keys(self) -> List[str]:
        # <--- 移除 db_session_key
        return [self.input_key, self.flow_id_key, self.chat_id_key, self.history_key]

    @property
    def output_keys(self) -> List[str]:
        return [self.output_key]

    def _call(self,
              inputs: Dict[str, Any],
              run_manager: Optional[CallbackManagerForChainRun] = None
              ) -> Dict[str, Any]:
        """ 同步执行链（不支持）。 """
        # 由于主要逻辑是异步的，同步调用通常不被支持或需要特殊处理
        # 这里我们明确抛出 NotImplementedError
        raise NotImplementedError(
            "WorkflowChain does not support synchronous execution. Use `ainvoke` instead."
        )

    async def _acall(self,
                   inputs: Dict[str, Any],
                   run_manager: Optional[CallbackManagerForChainRun] = None
                   ) -> Dict[str, Any]:
        """ 异步执行链的主要逻辑 (包含对话记忆和流程上下文)。 """
        # --- 添加调试日志 ---
        logger.critical(f"WorkflowChain _acall received input keys: {list(inputs.keys())}")
        logger.critical(f"WorkflowChain defined input_keys: {self.input_keys}")
        # --- 结束调试日志 ---

        user_input = inputs.get(self.input_key)
        # db_session = inputs.get(self.db_session_key) # <-- 移除
        flow_id = inputs.get(self.flow_id_key)
        chat_id = inputs.get(self.chat_id_key)
        history_messages_from_input = inputs.get(self.history_key, []) # <--- 从输入获取 history

        # --- 输入验证 (添加 history 类型检查) ---
        if not user_input:
            logger.error("WorkflowChain received no user_input.")
            return {"result": WorkflowChainOutput(summary="请输入您的问题或指令。", error="Missing user input")}
        # 不再需要检查 db_session 输入
        if not isinstance(history_messages_from_input, list) or not all(isinstance(m, BaseMessage) for m in history_messages_from_input):
            logger.error(f"WorkflowChain received invalid history format (type: {type(history_messages_from_input)}). Proceeding with empty history.")
            history_messages_from_input = [] # 使用空历史
        # 对 chat_id 的检查移到后面，即使没有 chat_id 也可能继续（无历史）

        logger.info(f"WorkflowChain processing input: {user_input[:50]}... for flow_id: {flow_id}, chat_id: {chat_id}")
        logger.info(f"WorkflowChain received {len(history_messages_from_input)} history messages from input.") # 添加日志

        try:
            # --- Step 0: Load History using DbChatMemory --- (移除此代码块)

            # --- Step 0.5: Apply History Truncation/Windowing --- (修改：使用 history_messages_from_input)
            history_messages_for_prompt = history_messages_from_input # <--- 使用来自输入的历史
            if len(history_messages_from_input) > self.history_max_messages:
                logger.warning(f"History for chat {chat_id} exceeds limit ({self.history_max_messages}). Truncating.")
                history_messages_for_prompt = history_messages_from_input[-self.history_max_messages:]
            logger.info(f"Number of history messages prepared for prompt: {len(history_messages_for_prompt)}") # 添加日志

            # --- Step 0.7: Get Current Flow Context (使用内部获取的 db_session) --- (新增)
            flow_context_str = "当前没有可用的流程图信息。"
            if flow_id:
                # <<< 使用 get_db_context 获取会话 >>>
                with get_db_context() as db_session:
                    try:
                        flow = db_session.query(Flow).filter(Flow.id == flow_id).first()
                        if flow and flow.flow_data:
                            nodes_summary = f"节点数量: {len(flow.flow_data.get('nodes', []))}"
                            connections_summary = f"连接数量: {len(flow.flow_data.get('connections', []))}"
                            flow_context_str = f"流程图名称: {flow.name}\\n{nodes_summary}\\n{connections_summary}"
                            logger.info(f"Successfully fetched flow context for flow {flow_id}")
                        elif flow:
                             flow_context_str = f"流程图名称: {flow.name} (内容为空)"
                        else:
                             logger.warning(f"Flow with id {flow_id} not found in DB.")
                    except Exception as flow_err:
                        logger.error(f"Failed to fetch flow context for flow {flow_id}: {flow_err}", exc_info=True)
                        flow_context_str = "获取流程图信息时出错。"
            else:
                 logger.warning("flow_id not provided, cannot fetch flow context.")

            # --- Step 1: Construct messages for LLM using Template --- (修改：history 变量名)
            try:
                messages_for_llm_objects = WORKFLOW_CHAT_PROMPT_TEMPLATE_WITH_CONTEXT.format_messages(
                    flow_context=flow_context_str,
                    history=history_messages_for_prompt, # <--- 使用准备好的历史 (传递 BaseMessage 列表)
                    input=user_input
                )
                logger.info(f"Formatted prompt using template. Total messages: {len(messages_for_llm_objects)}")
                # 将 LangChain Message 对象转换为 LLM 需要的字典列表
                messages_for_llm = []
                for msg_obj in messages_for_llm_objects:
                    role = None
                    content = ""
                    if isinstance(msg_obj, SystemMessage):
                        role = "system"
                        content = msg_obj.content
                    elif isinstance(msg_obj, HumanMessage):
                        role = "user"
                        content = msg_obj.content
                    elif isinstance(msg_obj, AIMessage):
                        role = "assistant"
                        content = msg_obj.content

                    if role:
                        messages_for_llm.append({"role": role, "content": content})
                    else:
                        logger.warning(f"Could not determine role for message object: {type(msg_obj)}")
            except Exception as fmt_err:
                 logger.error(f"Failed to format messages using template: {fmt_err}", exc_info=True)
                 return {"result": WorkflowChainOutput(summary="构建请求时出错。", error="Prompt formatting failed")}

            # --- Step 1.5: Initial non-streaming call to check for tool usage (using history) --- (修改此部分)
            logger.info(f"Making initial non-streaming LLM call (with history & flow context) for chat {chat_id}...")
            tool_definitions = deepseek_tools_definition

            initial_response_data, success = await self.llm.chat_completion(
                messages=messages_for_llm, # 使用格式化后的字典列表
                # tools=tool_definitions, # <--- 暂时注释掉，排查错误
                json_mode=False
            )

            if not success:
                raise Exception(f"Initial LLM call failed: {initial_response_data}")

            # --- Step 2: Analyze response - Tool Calls or Text? ---
            tool_calls_detected = []
            is_tool_call_response = False
            try:
                # Attempt to parse as JSON (as returned by our modified chat_completion)
                if initial_response_data.strip().startswith('{'):
                     from openai.types.chat import ChatCompletionMessage
                     response_message = ChatCompletionMessage.model_validate_json(initial_response_data)
                     if response_message.tool_calls:
                          tool_calls_detected = response_message.tool_calls
                          is_tool_call_response = True
                          logger.info(f"Detected {len(tool_calls_detected)} tool calls from initial response.")
                     # else: it was JSON but not tool calls, treat as text below
            except (json.JSONDecodeError, Exception) as parse_err:
                 # Not valid JSON or not ChatCompletionMessage format - likely plain text
                 logger.info(f"Initial response is not a tool call JSON ({parse_err}). Treating as text.")
                 pass # Keep is_tool_call_response as False

            # --- Step 3a: Handle Tool Calls (if detected) ---
            if is_tool_call_response and self.tool_executor:
                logger.info("Handling detected tool calls...")
                nodes_updated = []
                connections_updated = []
                tool_execution_errors = []
                tool_results_summary_list = [] # Store simple summaries
                tool_results_details = [] # Store more detailed results

                ai_summary = "正在处理您的请求并执行相关工具..." # Intermediate message

                # Prepare info about the calls themselves
                tool_calls_info = [
                    {
                        "id": call.id,
                        "function_name": call.function.name,
                        "function_args": call.function.arguments # Keep as string initially
                    }
                    for call in tool_calls_detected
                ]
                # Log the raw arguments for debugging
                for call_info in tool_calls_info:
                    logger.debug(f"Tool call prepared: ID={call_info['id']}, Func={call_info['function_name']}, Args={call_info['function_args']}")

                # Execute tools (assuming ToolExecutor handles async execution)
                # <<< ToolExecutor 不需要 db_session >>>
                tool_results = await self.tool_executor.execute(tool_calls_detected)

                # Process results
                for result in tool_results:
                    if result.is_error:
                        tool_execution_errors.append(f"Error executing {result.tool_name}: {result.output}")
                    if isinstance(result.output, dict):
                        # Extract nodes and connections if present
                        nodes_updated.extend(result.output.get("nodes", []))
                        connections_updated.extend(result.output.get("connections", []))
                        # Add simple summary if available
                        summary = result.output.get("summary")
                        if summary:
                            tool_results_summary_list.append(summary)
                    elif isinstance(result.output, str):
                         tool_results_summary_list.append(result.output)
                    
                    # Store detailed result
                    tool_results_details.append({"tool_name": result.tool_name, "output": result.output, "is_error": result.is_error})

                if tool_execution_errors:
                    ai_summary = f"执行工具时遇到问题: {'; '.join(tool_execution_errors)}"
                elif tool_results_summary_list:
                     ai_summary = "\n".join(tool_results_summary_list)
                else:
                     ai_summary = "工具已执行，但没有返回文本摘要。"

                # --- Step 4: Return Result (for Tool Calls path) ---
                return {"result": WorkflowChainOutput(nodes=nodes_updated, connections=connections_updated, summary=ai_summary, error="; ".join(tool_execution_errors) if tool_execution_errors else None, tool_calls_info=tool_calls_info, tool_results_info=tool_results_details)}

            # --- Step 3b: Handle Text Response (Streaming) --- 
            elif not is_tool_call_response:
                logger.info(f"No tool calls detected. Proceeding with final response generation (was previously streaming logic).")
                # In non-streaming _acall, we just need the final text from the initial call
                final_summary = initial_response_data # Use the text from the initial call
                # Clean up potential JSON wrapping if it wasn't a tool call
                try:
                    from openai.types.chat import ChatCompletionMessage
                    if final_summary.strip().startswith('{'):
                         response_message = ChatCompletionMessage.model_validate_json(final_summary)
                         if response_message.content:
                              final_summary = response_message.content
                except Exception:
                     pass # Keep original text if parsing fails
                
                logger.info(f"_acall returning final text summary (length: {len(final_summary)}): {final_summary[:100]}...")
                return {"result": WorkflowChainOutput(summary=final_summary)}

        except Exception as e:
            logger.error(f"Error in WorkflowChain _acall: {e}", exc_info=True)
            return {"result": WorkflowChainOutput(summary="处理请求时发生意外错误。", error=str(e))}

    # 临时保留旧的上下文收集方法，需要重构为依赖注入
    async def _gather_context(self, query: str) -> List[Dict]:
        """ (示例) 异步检索上下文。 """
        # if self.retriever:
        #     docs = await self.retriever.aget_relevant_documents(query)
        #     # 将 Document 对象转换为字典或其他格式
        #     return [doc.dict() for doc in docs]
        logger.warning("Context gathering (_gather_context) is not fully implemented.")
        return []

    def _generate_summary_from_tools(self, tool_results: List[ToolResult]) -> str:
        """根据工具执行结果生成摘要。"""
        success_messages = []
        error_messages = []
        ask_info_message = None

        for result in tool_results:
            if result.success:
                if result.data.get("formatted_text") and "ask_more_info" in result.message.lower(): # 特殊处理 ask_more_info
                    ask_info_message = result.data["formatted_text"]
                else:
                    success_messages.append(result.message)
            else:
                error_messages.append(result.message)

        if ask_info_message:
             return ask_info_message # 优先返回询问信息

        summary_parts = []
        if success_messages:
            summary_parts.append("操作成功完成:")
            summary_parts.extend([f"- {msg}" for msg in success_messages])
        if error_messages:
             summary_parts.append("\\n发生错误:")
             summary_parts.extend([f"- {msg}" for msg in error_messages])

        if not summary_parts:
             return "已处理请求，但没有具体操作或输出。"

        return "\\n".join(summary_parts) 