import logging
from typing import Dict, Any, List, Optional
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
    # conversation_id: Optional[str] = None # 内存管理应由 Memory 组件处理

    # 允许任意类型，例如 SQLAlchemy Session
    model_config = ConfigDict(arbitrary_types_allowed=True)

class WorkflowChainOutput(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
    # 可以添加更多调试信息
    # expanded_prompt: Optional[str] = None
    # steps_taken: List[str] = Field(default_factory=list)
    # tool_calls: List[Dict] = Field(default_factory=list)

class WorkflowChain(Chain):
    """
    负责处理用户输入，编排 LLM 调用、上下文检索、工具执行，
    最终生成流程图节点/连接或自然语言回复。
    """
    input_key: str = "user_input"  # 定义主要的文本输入键
    output_key: str = "result"     # 定义主要的输出键
    db_session_key: str = "db_session" # 定义数据库会话键
    
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
        return [self.input_key, self.db_session_key]

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
        db_session = inputs.get(self.db_session_key) # 假设 db_session 通过输入传递
        
        if not user_input:
            logger.error("WorkflowChain received no user_input.")
            return {"result": WorkflowChainOutput(summary="请输入您的问题或指令。", error="Missing user input")}
        if not db_session:
             logger.error("WorkflowChain received no db_session.")
             return {"result": WorkflowChainOutput(summary="处理请求时发生内部错误。", error="Missing database session")}

        logger.info(f"WorkflowChain processing input: {user_input[:50]}...")

        # 1. (可选) 扩展 Prompt (如果需要)
        # expanded_prompt = await self.prompt_expander.expand(user_input)
        # logger.info(f"Expanded prompt: {expanded_prompt[:50]}...")
        current_prompt = user_input # 暂时不扩展

        # 2. (可选) 检索上下文 (如果需要RAG)
        # context = await self._gather_context(current_prompt)
        # logger.info(f"Gathered context: {len(context)} documents")
        context_str = "" # 暂时不使用上下文

        # 3. 调用 LLM (初始调用，可能用于判断意图或直接回答)
        #    这里简化为直接调用 LLM，实际可能需要更复杂的逻辑判断是否需要工具
        try:
            # 准备 LLM 消息 (这里简化，实际应包含上下文、历史等)
            messages_for_llm = [
                {"role": "system", "content": "You are an AI assistant for creating flowcharts. You can use tools to create nodes, connect them, set properties, or ask for more information. Respond in Chinese."},
                # {"role": "system", "content": f"Context:\n{context_str}"}, # 包含上下文（如果使用）
                {"role": "user", "content": current_prompt}
            ]
            
            # 获取工具定义 (用于 function calling)
            # tool_definitions = self.tool_executor.get_tool_definitions() # 假设 ToolExecutor 有此方法
            # 暂时硬编码工具定义 (需要从 definitions.py 获取)
            # 修正导入的名称
            from backend.langchainchat.tools.definitions import deepseek_tools_definition
            tool_definitions = deepseek_tools_definition

            # 调用 LLM 并期望它可能返回工具调用请求
            logger.info("Calling LLM with prompt and tools...")
            llm_response_content, success = await self.llm.chat_completion(
                messages=messages_for_llm,
                tools=tool_definitions
                # 传递其他参数，如 temperature 等
            )

            if not success:
                raise Exception("LLM chat completion failed.")

            # 解析 LLM 响应，判断是否需要工具调用
            # DeepSeek/OpenAI 返回的工具调用在 message.tool_calls 中
            # 这里需要解析 llm_response_content，假设它是 JSON 字符串或字典
            # TODO: 实际需要根据 self.llm.chat_completion 的返回值调整解析逻辑
            # 假设 llm_response_content 可能是包含 tool_calls 的 AssistantMessage 字典形式
            
            tool_calls_detected = []
            ai_summary = llm_response_content # 默认将 LLM 的直接回复作为总结

            try:
                # 尝试解析响应，查找工具调用
                # 注意：openai client v1.x 返回的是 Pydantic 对象或字典，而不是纯字符串
                # 我们需要适配 DeepSeekClient 返回的具体格式
                # 假设 chat_completion 返回的是包含 message 对象的元组
                # response_message: ChatCompletionMessage = llm_response_content # 假设是这个类型
                # if response_message and response_message.tool_calls:
                #     tool_calls_detected = response_message.tool_calls
                #     ai_summary = response_message.content or "正在执行工具..." # 如果有工具调用，可能没有直接内容
                
                # -- 临时模拟解析，需要替换为真实逻辑 --
                if isinstance(llm_response_content, str) and 'tool_calls' in llm_response_content:
                     # 非常简化的假设，需要更健壮的解析
                     try:
                          response_data = json.loads(llm_response_content)
                          if isinstance(response_data, dict) and 'tool_calls' in response_data:
                               tool_calls_detected = response_data['tool_calls']
                               ai_summary = response_data.get('content', "正在执行工具...")
                          elif isinstance(response_data, dict) and 'content' in response_data:
                              ai_summary = response_data['content']
                              # else: ai_summary 保持原样
                     except json.JSONDecodeError:
                          ai_summary = llm_response_content # 解析失败，用原始字符串
                # -- 结束模拟解析 --

                logger.info(f"LLM direct response/summary: {ai_summary[:100]}...")
                if tool_calls_detected:
                    logger.info(f"Detected {len(tool_calls_detected)} tool calls.")
                else:
                    logger.info("No tool calls detected in LLM response.")

            except Exception as parse_err:
                logger.error(f"Error parsing LLM response for tool calls: {parse_err}", exc_info=True)
                # 即使解析失败，也继续，使用原始回复
                ai_summary = llm_response_content if isinstance(llm_response_content, str) else str(llm_response_content)


            # 4. 如果需要工具调用，执行工具
            nodes_updated = []
            connections_updated = []
            tool_execution_errors = []
            tool_results_summary = [] # 收集工具执行结果的简单描述

            if tool_calls_detected:
                ai_summary = "正在处理您的请求..." # 更新摘要，提示正在执行操作
                for tool_call in tool_calls_detected:
                    # TODO: 从 tool_call 中提取 tool_name 和 arguments
                    # tool_call 的结构依赖于 LLM 返回格式 (OpenAI/DeepSeek)
                    # 假设 tool_call 是类似 {'id': 'call_abc', 'function': {'name': 'create_node', 'arguments': '{...}'}, 'type': 'function'}
                    
                    tool_call_id = tool_call.get('id')
                    function_info = tool_call.get('function')
                    if not function_info or not tool_call_id:
                        logger.warning(f"Skipping invalid tool call format: {tool_call}")
                        continue
                        
                    tool_name = function_info.get('name')
                    tool_args_str = function_info.get('arguments')
                    
                    if not tool_name or tool_args_str is None:
                         logger.warning(f"Skipping tool call with missing name or arguments: {tool_call}")
                         continue

                    try:
                        # 解析参数字符串为字典
                        tool_args = json.loads(tool_args_str)
                        logger.info(f"Executing tool '{tool_name}' with args: {tool_args}")
                        
                        # 使用 ToolExecutor 执行
                        tool_result = await self.tool_executor.execute(
                            tool_name=tool_name,
                            parameters=tool_args,
                            # db_session=db_session # 确保 ToolExecutor 或其调用的函数能接收 db_session
                        )
                        
                        logger.info(f"Tool '{tool_name}' executed. Success: {tool_result.success}, Result: {str(tool_result.result_data)[:100]}...")

                        if tool_result.success:
                            tool_results_summary.append(f"成功执行 {tool_name}。")
                            # 根据工具类型聚合结果
                            if tool_name == "create_node" and isinstance(tool_result.result_data, dict):
                                nodes_updated.append(tool_result.result_data)
                            elif tool_name == "connect_nodes" and isinstance(tool_result.result_data, dict):
                                connections_updated.append(tool_result.result_data)
                            elif tool_name == "set_properties" and isinstance(tool_result.result_data, dict):
                                # set_properties 可能返回更新后的节点或仅确认
                                # 这里假设它不直接修改 nodes_updated/connections_updated
                                # 但可以添加到 summary
                                element_id = tool_result.result_data.get('element_id', '未知元素')
                                tool_results_summary.append(f"已设置 {element_id} 的属性。")
                            elif tool_name == "ask_more_info" and isinstance(tool_result.result_data, str):
                                 # 如果是提问，将问题设为最终的 AI 回复
                                 ai_summary = tool_result.result_data 
                            elif tool_name == "generate_text" and isinstance(tool_result.result_data, str):
                                 # 如果是文本生成，可以附加到 summary 或替换它
                                 ai_summary += "\n\n" + tool_result.result_data
                        else:
                            error_msg = f"执行工具 '{tool_name}' 失败: {tool_result.error_message}"
                            logger.error(error_msg)
                            tool_execution_errors.append(error_msg)
                            tool_results_summary.append(f"尝试执行 {tool_name} 时出错。")
                            
                    except json.JSONDecodeError:
                        error_msg = f"无法解析工具 '{tool_name}' 的参数: {tool_args_str}"
                        logger.error(error_msg)
                        tool_execution_errors.append(error_msg)
                    except Exception as tool_exec_err:
                        error_msg = f"执行工具 '{tool_name}' 时发生意外错误: {tool_exec_err}"
                        logger.error(error_msg, exc_info=True)
                        tool_execution_errors.append(error_msg)

                # 如果有工具执行，可以基于执行结果生成最终摘要
                if tool_results_summary and not tool_execution_errors:
                    # 如果没有提问工具覆盖 ai_summary，则生成一个总结性回复
                    if not any(call.get('function', {}).get('name') == 'ask_more_info' for call in tool_calls_detected):
                        ai_summary = "我已经根据您的请求执行了以下操作:\n- " + "\n- ".join(tool_results_summary)
                elif tool_execution_errors:
                    ai_summary = "处理您的请求时遇到一些问题:\n- " + "\n- ".join(tool_execution_errors) 
                    ai_summary += "\n请检查您的指令或稍后再试。"

            # 5. 聚合结果并返回
            final_output = WorkflowChainOutput(
                summary=ai_summary,
                nodes=nodes_updated or None, # 如果列表为空，返回 None
                connections=connections_updated or None,
                error="; ".join(tool_execution_errors) if tool_execution_errors else None
            )
            
            logger.info("WorkflowChain finished processing.")
            # LangChain 期望返回一个包含输出键的字典
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