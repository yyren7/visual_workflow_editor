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
    db_session: Session # 用于访问应用层服务
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
    db_session_key: str = "db_session" # 定义数据库会话键
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
        # <--- 添加 history_key
        return [self.input_key, self.db_session_key, self.flow_id_key, self.chat_id_key, self.history_key]

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
        db_session = inputs.get(self.db_session_key)
        flow_id = inputs.get(self.flow_id_key)
        chat_id = inputs.get(self.chat_id_key)
        history_messages_from_input = inputs.get(self.history_key, []) # <--- 从输入获取 history

        # --- 输入验证 (添加 history 类型检查) ---
        if not user_input:
            logger.error("WorkflowChain received no user_input.")
            return {"result": WorkflowChainOutput(summary="请输入您的问题或指令。", error="Missing user input")}
        if not db_session:
             logger.error("WorkflowChain received no db_session.")
             return {"result": WorkflowChainOutput(summary="处理请求时发生内部错误。", error="Missing database session")}
        if not isinstance(history_messages_from_input, list) or not all(isinstance(m, BaseMessage) for m in history_messages_from_input):
            logger.error(f"WorkflowChain received invalid history format (type: {type(history_messages_from_input)}). Proceeding with empty history.")
            history_messages_from_input = [] # 使用空历史
        # 对 chat_id 的检查移到后面，即使没有 chat_id 也可能继续（无历史）

        logger.info(f"WorkflowChain processing input: {user_input[:50]}... for flow_id: {flow_id}, chat_id: {chat_id}")
        logger.info(f"WorkflowChain received {len(history_messages_from_input)} history messages from input.") # 添加日志

        try:
            # --- Step 0: Load History using DbChatMemory --- (移除此代码块)

            # --- Step 0.5: Apply History Truncation/Windowing --- (修改：使用 history_messages_from_input)
            if len(history_messages_from_input) > self.history_max_messages:
                logger.warning(f"History for chat {chat_id} exceeds limit ({self.history_max_messages}). Truncating.")
                history_messages_for_prompt = history_messages_from_input[-self.history_max_messages:]
            else:
                history_messages_for_prompt = history_messages_from_input # <--- 使用来自输入的历史
            logger.info(f"Number of history messages prepared for prompt: {len(history_messages_for_prompt)}") # 添加日志

            # --- Step 0.7: Get Current Flow Context --- (新增)
            flow_context_str = "当前没有可用的流程图信息。"
            if flow_id:
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
                    {"id": tc.id, "name": tc.function.name, "args": tc.function.arguments}
                    for tc in tool_calls_detected
                ]

                # --- Execute Tools ---
                for tool_call in tool_calls_detected:
                    tool_call_id = tool_call.id
                    function_info = tool_call.function
                    if not function_info or not tool_call_id:
                        logger.warning(f"Skipping invalid tool call format: {tool_call}")
                        continue

                    tool_name = function_info.name
                    tool_args_str = function_info.arguments

                    if not tool_name or tool_args_str is None:
                         logger.warning(f"Skipping tool call with missing name or arguments: {tool_call}")
                         continue

                    try:
                        tool_args = json.loads(tool_args_str)
                        logger.info(f"Executing tool '{tool_name}' with args: {tool_args}")

                        tool_result = await self.tool_executor.execute(
                            tool_name=tool_name,
                            parameters=tool_args,
                            db_session=db_session, # Pass session if needed by tools
                            flow_id=flow_id # 将 flow_id 传递给执行器
                        )

                        logger.info(f"Tool '{tool_name}' executed. Success: {tool_result.success}, Result: {str(tool_result.result_data)[:100]}...")

                        result_detail = {
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "success": tool_result.success,
                            "result": tool_result.result_data if tool_result.success else None,
                            "error": tool_result.error_message if not tool_result.success else None
                        }
                        tool_results_details.append(result_detail)

                        if tool_result.success:
                            tool_results_summary_list.append(f"成功执行 {tool_name}。")
                            # --- (Aggregate results based on tool type - same logic as before) ---
                            if tool_name == "create_node" and isinstance(tool_result.result_data, dict):
                                nodes_updated.append(tool_result.result_data)
                            elif tool_name == "connect_nodes" and isinstance(tool_result.result_data, dict):
                                connections_updated.append(tool_result.result_data)
                            # ... (handle set_properties, ask_more_info, generate_text) ...
                            elif tool_name == "ask_more_info" and isinstance(tool_result.result_data, str):
                                 ai_summary = tool_result.result_data # Use question as final summary
                            elif tool_name == "generate_text" and isinstance(tool_result.result_data, str):
                                 ai_summary += "\\n\\n" + tool_result.result_data # Append generated text
                        else:
                            error_msg = f"执行工具 '{tool_name}' 失败: {tool_result.error_message}"
                            logger.error(error_msg)
                            tool_execution_errors.append(error_msg)
                            tool_results_summary_list.append(f"尝试执行 {tool_name} 时出错。")

                    except json.JSONDecodeError:
                         error_msg = f"无法解析工具 '{tool_name}' 的参数: {tool_args_str}"
                         logger.error(error_msg)
                         tool_execution_errors.append(error_msg)
                    except Exception as tool_exec_err:
                        error_msg = f"执行工具 '{tool_name}' 时发生意外错误: {tool_exec_err}"
                        logger.error(error_msg, exc_info=True)
                        tool_execution_errors.append(error_msg)

                # --- Generate final summary after tool execution ---
                if tool_results_summary_list and not tool_execution_errors:
                    # Avoid overwriting ask_more_info result
                    if not any(tc.function.name == 'ask_more_info' for tc in tool_calls_detected):
                        ai_summary = "我已经根据您的请求执行了以下操作:\\n- " + "\\n- ".join(tool_results_summary_list)
                elif tool_execution_errors:
                    ai_summary = "处理您的请求时遇到一些问题:\\n- " + "\\n- ".join(tool_execution_errors) + "\\n请检查您的指令或稍后再试。"

                # --- Return result for tool call path ---
                final_output = WorkflowChainOutput(
                    summary=ai_summary,
                    nodes=nodes_updated or None,
                    connections=connections_updated or None,
                    error="; ".join(tool_execution_errors) if tool_execution_errors else None,
                    event_stream=None, # <--- Ensure this uses event_stream=None
                    tool_calls_info=tool_calls_info, # Include info about calls
                    tool_results_info=tool_results_details # Include info about results
                )
                logger.info("WorkflowChain finished processing tool calls.")
                return {"result": final_output}

            # --- Step 3b: Handle Text/Streaming Response (no tool calls) ---
            else:
                logger.info(f"No tool calls detected. Making streaming LLM call (with history & flow context) for chat {chat_id}...")

                async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
                    """Wraps the LLM stream to yield structured events."""
                    try:
                        # Get the original text stream generator from the LLM
                        text_stream = self.llm.stream_chat_completion(
                            messages=messages_for_llm # 使用格式化后的字典列表
                        )
                        async for chunk in text_stream:
                            if chunk: # Ensure chunk is not empty
                                yield {"type": "llm_chunk", "data": {"text": chunk}}
                        # Optionally yield a final 'stream_end' event if needed by frontend
                        yield {"type": "stream_end", "data": {}}
                        logger.info(f"LLM text stream finished for chat {chat_id}")
                    except Exception as stream_err:
                        logger.error(f"Error during LLM streaming for chat {chat_id}: {stream_err}", exc_info=True)
                        # Yield an error event
                        yield {"type": "error", "data": {"message": f"Streaming error: {stream_err}"}}

                # Create the event stream generator
                event_stream_gen = event_generator()

                # --- 返回包含事件流生成器的结果 ---
                final_output_object = WorkflowChainOutput(
                    summary="", # Summary will be built on the frontend from chunks
                    event_stream=event_stream_gen # Pass the new event generator
                )
                return {"result": final_output_object}

        except Exception as e:
            logger.error(f"Error in WorkflowChain _acall for chat {chat_id}: {e}", exc_info=True)
            # Also yield an error event in the main exception handler if possible?
            # This is tricky because we don't have the generator structure here.
            # Returning a non-streaming error is safer for now.
            final_output_object = WorkflowChainOutput(
                 summary="处理您的请求时遇到内部错误。",
                 error=f"Chain execution failed: {str(e)}",
                 event_stream=None # Ensure event_stream is None on error
            )
            return {"result": final_output_object}

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