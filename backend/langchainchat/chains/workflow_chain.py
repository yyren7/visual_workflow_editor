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
from backend.langchainchat.prompts.chat_prompts import PROMPT_EXPANSION_TEMPLATE
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

logger = logging.getLogger(__name__)

# 定义链的输入和输出模型
class WorkflowChainInput(BaseModel):
    user_input: str
    db_session: Session # 用于访问应用层服务
    flow_id: Optional[str] = None # 添加 flow_id
    # conversation_id: Optional[str] = None # 内存管理应由 Memory 组件处理

    # 允许任意类型，例如 SQLAlchemy Session
    model_config = ConfigDict(arbitrary_types_allowed=True)

class WorkflowChainOutput(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = "" # Will hold text summary OR final message after tools
    error: Optional[str] = None
    # NEW: Add a field for the stream generator if applicable
    stream_generator: Optional[AsyncGenerator[str, None]] = None
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
    
    # 注入的依赖组件
    llm: DeepSeekLLM
    # Removed prompt_expander attribute
    # prompt_expander: Optional[PromptExpansion] = None
    retriever: Optional[EmbeddingRetriever] = None    # 检索器 (可选)
    tool_executor: Optional[ToolExecutor] = None      # 工具执行器 (可选)
    output_parser: Optional[StructuredOutputParser] = None # 结构化输出解析器 (可选)
    # memory: Optional[BaseChatMemory] = None # 内存组件 (可选)
    
    # 注入的应用服务 (需要通过外部机制传入 db_session)
    # flow_service: Optional[FlowService] = None
    # user_service: Optional[UserService] = None
    # variable_service: Optional[FlowVariableService] = None

    @property
    def input_keys(self) -> List[str]:
        return [self.input_key, self.db_session_key, self.flow_id_key]

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
        """ 异步执行链的主要逻辑。 """
        user_input = inputs.get(self.input_key)
        db_session = inputs.get(self.db_session_key)
        flow_id = inputs.get(self.flow_id_key) # 获取 flow_id
        
        if not user_input:
            logger.error("WorkflowChain received no user_input.")
            return {"result": WorkflowChainOutput(summary="请输入您的问题或指令。", error="Missing user input")}
        if not db_session:
             logger.error("WorkflowChain received no db_session.")
             return {"result": WorkflowChainOutput(summary="处理请求时发生内部错误。", error="Missing database session")}
        if not flow_id:
            logger.warning("WorkflowChain did not receive flow_id. Tools might default to the latest flow.")

        logger.info(f"WorkflowChain processing input: {user_input[:50]}... for flow_id: {flow_id}")
        
        try:
            # --- Step 1: Initial non-streaming call to check for tool usage --- 
            logger.info("Making initial non-streaming LLM call to check for tool usage...")
            messages_for_llm = [
                {"role": "system", "content": "You are an AI assistant for creating flowcharts. You can use tools to create nodes, connect them, set properties, or ask for more information. Respond in Chinese."}, 
                {"role": "user", "content": user_input}
            ]
            tool_definitions = deepseek_tools_definition # Or get dynamically
            
            initial_response_data, success = await self.llm.chat_completion(
                messages=messages_for_llm,
                tools=tool_definitions,
                json_mode=False # Ensure not in JSON mode for tool check
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
                                 ai_summary += "\n\n" + tool_result.result_data # Append generated text
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
                        ai_summary = "我已经根据您的请求执行了以下操作:\n- " + "\n- ".join(tool_results_summary_list)
                elif tool_execution_errors:
                    ai_summary = "处理您的请求时遇到一些问题:\n- " + "\n- ".join(tool_execution_errors) + "\n请检查您的指令或稍后再试。"

                # --- Return result for tool call path --- 
                final_output = WorkflowChainOutput(
                    summary=ai_summary,
                    nodes=nodes_updated or None,
                    connections=connections_updated or None,
                    error="; ".join(tool_execution_errors) if tool_execution_errors else None,
                    stream_generator=None, # No stream for tool calls
                    tool_calls_info=tool_calls_info, # Include info about calls
                    tool_results_info=tool_results_details # Include info about results
                )
                logger.info("WorkflowChain finished processing tool calls.")
                return {"result": final_output}

            # --- Step 3b: Handle Direct Text Response (No Tool Calls) --- 
            else:
                logger.info("No tool calls detected or tool executor not available. Proceeding with streaming text response.")
                # LLM didn't request tools, or we don't have an executor.
                # Now, make a streaming call to get the text response.
                # We use the original messages again, but this time without tools.
                
                stream_generator = self.llm.stream_chat_completion(
                    messages=messages_for_llm, # Use the same initial messages
                    # No tools parameter for simple streaming
                    # Other parameters like temperature could be passed if needed
                )
                
                # Return the stream generator
                final_output = WorkflowChainOutput(
                    summary="", # Summary will be built by consuming the stream
                    stream_generator=stream_generator, # Pass the generator
                    error=None,
                    tool_calls_info=None,
                    tool_results_info=None
                )
                logger.info("WorkflowChain returning stream generator for text response.")
                return {"result": final_output}

        except Exception as e:
            logger.error(f"Error in WorkflowChain execution: {e}", exc_info=True)
            return {"result": WorkflowChainOutput(summary="处理您的请求时发生意外错误。", error=str(e))}

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
             summary_parts.append("\n发生错误:")
             summary_parts.extend([f"- {msg}" for msg in error_messages])
             
        if not summary_parts:
             return "已处理请求，但没有具体操作或输出。"
             
        return "\n".join(summary_parts) 