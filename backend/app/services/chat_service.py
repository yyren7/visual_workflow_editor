from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import logging
import uuid
import json

from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import Chat, Flow

# 导入 RAG 链/Agent (假设路径和名称)
# from backend.langchainchat.chains.rag_chain import RAGChain # 或者 Agent
# 导入 WorkflowChain (如果 chat service 需要直接触发工作流修改)
from backend.langchainchat.chains.workflow_chain import WorkflowChain, WorkflowChainOutput
# 导入构建 RAG/Workflow 链所需的依赖 (这些通常在应用启动时初始化并注入)
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM
from backend.langchainchat.tools.executor import ToolExecutor
# from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
# from database.embedding.service import DatabaseEmbeddingService

# --- RAG 相关导入 ---
from backend.langchainchat.chains.rag_chain import create_rag_chain, RAGInput
from backend.langchainchat.retrievers.embedding_retriever import EmbeddingRetriever
from database.embedding.service import DatabaseEmbeddingService

logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务，管理聊天记录并与 RAG/Workflow 系统交互"""
    
    def __init__(self, db: Session):
        self.db = db
        # 初始化 LLM 客户端 (应考虑单例或共享实例)
        self.llm = DeepSeekLLM()
        
        # 初始化 WorkflowChain
        self.workflow_chain: WorkflowChain = self._initialize_workflow_chain()
        # 初始化 RAGChain
        self.rag_chain = self._initialize_rag_chain() # RAGChain 返回的是 Runnable
    
    def _initialize_workflow_chain(self) -> WorkflowChain:
        """ 初始化 WorkflowChain (示例，实际应使用依赖注入) """
        # 这里仅为示例，实际需要正确初始化和配置所有依赖
        logger.info("Initializing WorkflowChain in ChatService (example setup)")
        # llm 实例已在 __init__ 中创建
        tool_executor = ToolExecutor(llm_client=self.llm)
        # 其他依赖如 prompt_expander, retriever 等需要实例化
        # embedding_service = DatabaseEmbeddingService()
        # retriever = EmbeddingRetriever(db_session=self.db, embedding_service=embedding_service)
        
        # 创建 WorkflowChain 实例
        chain = WorkflowChain(
            llm=self.llm,
            tool_executor=tool_executor
            # retriever=retriever, # 添加其他需要的组件
            # ... 其他依赖
        )
        return chain

    def _initialize_rag_chain(self):
        """ 初始化 RAG Chain (示例，实际应使用依赖注入) """
        logger.info("Initializing RAGChain in ChatService (example setup)")
        # llm 实例已在 __init__ 中创建
        embedding_service = DatabaseEmbeddingService() # 创建嵌入服务实例
        
        retriever = EmbeddingRetriever(db_session=self.db, embedding_service=embedding_service)
        
        # 使用工厂函数创建 RAG 链
        rag_chain = create_rag_chain(llm=self.llm, retriever=retriever)
        return rag_chain

    def create_chat(self, flow_id: str, name: str = "新聊天", chat_data: Dict[str, Any] = None) -> Optional[Chat]:
        """
        创建新的聊天记录
        
        Args:
            flow_id: 关联的流程图ID
            name: 聊天名称
            chat_data: 聊天数据，默认为空字典
            
        Returns:
            创建的Chat对象，如果失败则返回None
        """
        try:
            # 验证流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.error(f"流程图 {flow_id} 不存在，无法创建聊天")
                return None
                
            # 创建聊天记录
            chat = Chat(
                id=str(uuid.uuid4()),
                flow_id=flow_id,
                name=name,
                chat_data=chat_data or { "messages": [] } # 确保有 messages
            )
            
            self.db.add(chat)
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已为流程图 {flow_id} 创建聊天 {chat.id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建聊天失败: {str(e)}")
            return None
    
    def get_chat(self, chat_id: str) -> Optional[Chat]:
        """
        获取聊天记录
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            Chat对象，如果不存在则返回None
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            return chat
        except Exception as e:
            logger.error(f"获取聊天 {chat_id} 失败: {str(e)}")
            return None
    
    def get_chats_for_flow(self, flow_id: str, skip: int = 0, limit: int = 100) -> List[Chat]:
        """
        获取流程图的所有聊天记录
        
        Args:
            flow_id: 流程图ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            Chat对象列表
        """
        try:
            chats = self.db.query(Chat)\
                .filter(Chat.flow_id == flow_id)\
                .order_by(desc(Chat.updated_at))\
                .offset(skip)\
                .limit(limit)\
                .all()
            
            return chats
        except Exception as e:
            logger.error(f"获取流程图 {flow_id} 的聊天记录失败: {str(e)}")
            return []
    
    def update_chat(self, chat_id: str, name: str = None, chat_data: Dict[str, Any] = None) -> Optional[Chat]:
        """
        更新聊天记录
        
        Args:
            chat_id: 聊天ID
            name: 新的聊天名称（可选）
            chat_data: 新的聊天数据（可选）
            
        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"聊天 {chat_id} 不存在，无法更新")
                return None
                
            # 更新字段
            if name is not None:
                chat.name = name
                
            if chat_data is not None:
                # 安全更新 chat_data，保留其他可能存在的字段
                existing_data = chat.chat_data or {}
                existing_data.update(chat_data)
                chat.chat_data = existing_data
            
            # 更新时间戳
            chat.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已更新聊天 {chat_id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新聊天 {chat_id} 失败: {str(e)}")
            return None
    
    def add_message_to_chat(self, chat_id: str, role: str, content: str) -> Optional[Chat]:
        """
        向聊天添加一条消息
        
        Args:
            chat_id: 聊天ID
            role: 消息发送者角色 (user/assistant/system)
            content: 消息内容
            
        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"聊天 {chat_id} 不存在，无法添加消息")
                return None
            
            # 获取现有聊天数据
            # 使用 mutable_flag 技巧处理 JSON/JSONB 修改
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy.ext.mutable import MutableDict
            chat_data = MutableDict.as_mutable(chat.chat_data) if chat.chat_data else MutableDict()
            
            # 确保有messages数组
            if "messages" not in chat_data:
                chat_data["messages"] = []
            elif not isinstance(chat_data["messages"], list):
                 logger.warning(f"Chat {chat_id} messages is not a list, resetting.")
                 chat_data["messages"] = [] # 如果不是列表，重置
                 
            # 添加新消息
            chat_data["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # 更新聊天数据和时间戳
            chat.chat_data = chat_data 
            chat.updated_at = datetime.utcnow()
            
            self.db.add(chat) # 确保添加到 session
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已向聊天 {chat_id} 添加一条 {role} 消息")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"向聊天 {chat_id} 添加消息失败: {str(e)}", exc_info=True) # 添加 exc_info=True
            return None

    async def process_chat_message(self, chat_id: str, user_message: str) -> WorkflowChainOutput | Dict[str, Any]:
        """
        处理新的聊天消息，调用 WorkflowChain。
        如果返回流，则直接传递生成器，由路由层处理保存。
        如果返回工具结果，则处理并保存。

        Args:
            chat_id: 当前聊天ID。
            user_message: 用户发送的消息。

        Returns:
            WorkflowChainOutput 对象 (可能包含原始 stream_generator 或工具信息) 
            或在初始错误时返回包含 error 的字典。
        """
        logger.info(f"Processing message for chat {chat_id}: {user_message[:50]}...")
        
        # 1. 将用户消息添加到聊天记录
        updated_chat = self.add_message_to_chat(chat_id, "user", user_message)
        if not updated_chat:
             return {"error": "无法将用户消息添加到聊天记录", "ai_response": None, "nodes": None, "connections": None}

        # 2. 调用 WorkflowChain 处理输入
        try:
            # 获取当前聊天关联的 flow_id
            current_flow_id = updated_chat.flow_id
            if not current_flow_id:
                logger.error(f"Chat {chat_id} is not associated with a flow_id. Cannot proceed.")
                return {"error": "聊天未关联流程图", "ai_response": None, "nodes": None, "connections": None}
            
            logger.info(f"Chat {chat_id} associated with flow_id: {current_flow_id}")
            
            chain_input = {
                "user_input": user_message,
                "db_session": self.db,
                "flow_id": current_flow_id  # 将 flow_id 传递给链
            }
            logger.debug(f"Invoking WorkflowChain for chat {chat_id} with input: {chain_input}") # 更新日志记录
            chain_result = await self.workflow_chain.ainvoke(chain_input)
            logger.debug(f"WorkflowChain returned type: {type(chain_result)}")

            # --- Parse the result to get WorkflowChainOutput object --- 
            chain_output_obj: Optional[WorkflowChainOutput] = None
            if isinstance(chain_result, WorkflowChainOutput):
                chain_output_obj = chain_result
            elif isinstance(chain_result, dict) and "result" in chain_result and isinstance(chain_result["result"], WorkflowChainOutput):
                 chain_output_obj = chain_result["result"]
            elif isinstance(chain_result, dict) and all(key in chain_result for key in WorkflowChainOutput.model_fields.keys()):
                try:
                    chain_output_obj = WorkflowChainOutput(**chain_result)
                except Exception as pydantic_err:
                    logger.error(f"Failed to create WorkflowChainOutput from dict: {pydantic_err}")
                    chain_output_obj = None # Failed to parse
            
            if not chain_output_obj:
                 logger.error(f"WorkflowChain ainvoke returned unexpected structure: {chain_result}")
                 raise Exception("WorkflowChain returned unexpected output structure.")
            # --- End Parsing --- 

            # 3. Check if the output contains a stream generator
            if chain_output_obj.stream_generator:
                logger.info(f"WorkflowChain returned a stream generator for chat {chat_id}. Returning it directly.")
                # Return the object with the wrapped generator
                return chain_output_obj 
            else:
                # 4. Process non-streaming response (tool calls or direct text error)
                logger.info(f"WorkflowChain returned non-streaming output for chat {chat_id}. Processing...")
                ai_summary = chain_output_obj.summary
                error = chain_output_obj.error
                nodes_to_update = chain_output_obj.nodes
                connections_to_update = chain_output_obj.connections
                
                if error:
                    logger.error(f"WorkflowChain returned an error: {error}")
                    self.add_message_to_chat(chat_id, "assistant", error)
                    return chain_output_obj
                    
                if ai_summary:
                    self.add_message_to_chat(chat_id, "assistant", ai_summary)
                else:
                     logger.warning(f"WorkflowChain returned no summary and no error for chat {chat_id}")

                if nodes_to_update or connections_to_update:
                    logger.info(f"Updating flow based on WorkflowChain output: {len(nodes_to_update) if nodes_to_update else 0} nodes, {len(connections_to_update) if connections_to_update else 0} connections")
                    flow_update_result = self._update_flow_in_db(updated_chat.flow_id, nodes_to_update, connections_to_update)
                    if not flow_update_result.get("success"):
                        logger.error(f"Failed to update flow {updated_chat.flow_id} in database: {flow_update_result.get('message')}")
                        chain_output_obj.error = (chain_output_obj.error + "; " if chain_output_obj.error else "") + "Flow update failed."

                logger.info(f"Returning processed non-streaming output for chat {chat_id}")
                return chain_output_obj

        except Exception as e:
            logger.error(f"Error in process_chat_message for chat {chat_id}: {e}", exc_info=True)
            error_response = "抱歉，处理您的消息时遇到问题。"
            try:
                self.add_message_to_chat(chat_id, "assistant", error_response)
            except Exception as log_err:
                 logger.error(f"Failed to add error message to chat {chat_id} after main processing error: {log_err}")
            return {"error": str(e), "ai_response": error_response, "nodes": None, "connections": None}

    def _update_flow_in_db(self, flow_id: str, nodes: Optional[List[Dict]], connections: Optional[List[Dict]]) -> Dict:
        """将 WorkflowChain 生成的节点和连接更新到数据库中的 Flow 对象。"""
        try:
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                return {"success": False, "message": f"Flow {flow_id} not found for update."}
            
            # 获取当前流程图数据
            # 使用 MutableDict 处理 JSONB 修改
            from sqlalchemy.ext.mutable import MutableDict
            flow_data = MutableDict.as_mutable(flow.flow_data) if flow.flow_data else MutableDict()
            
            # 如果没有 flow_data，初始化基本结构
            if not flow_data:
                 flow_data = MutableDict({"nodes": [], "connections": [], "variables": {}})
            elif "nodes" not in flow_data:
                 flow_data["nodes"] = []
            elif "connections" not in flow_data:
                 flow_data["connections"] = []

            # 更新节点和连接 (这里简单地用新的替换旧的，实际可能需要更复杂的合并逻辑)
            # 注意：这会丢失旧节点/连接。如果需要合并，逻辑会复杂得多。
            if nodes is not None: # 允许只更新其中之一
                 flow_data["nodes"] = nodes
            if connections is not None:
                 flow_data["connections"] = connections
                 
            # 更新数据库
            flow.flow_data = flow_data
            flow.updated_at = datetime.utcnow()
            self.db.add(flow)
            self.db.commit()
            logger.info(f"Successfully updated flow {flow_id} in database.")
            return {"success": True, "message": "Flow updated successfully."}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating flow {flow_id} in DB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"Database error during flow update: {e}"}

    # --- 新增 RAG 交互方法 ---
    async def get_rag_response(self, chat_id: str, question: str) -> Optional[Dict[str, Any]]:
        """
        获取 RAG 响应并更新聊天记录。

        Args:
            chat_id: 聊天ID。
            question: 用户提出的问题。

        Returns:
            包含 RAG 响应内容的字典，如果失败则返回 None。
            例如: {"answer": "...", "context": [...]}
        """
        logger.info(f"正在为聊天 {chat_id} 获取 RAG 响应，问题: '{question[:50]}...'")
        try:
            chat = self.get_chat(chat_id)
            if not chat:
                logger.error(f"聊天 {chat_id} 未找到，无法获取 RAG 响应")
                return None

            if not self.rag_chain:
                logger.error("RAG 链未初始化，无法获取响应")
                # 尝试重新初始化？或者直接返回错误
                # self.rag_chain = self._initialize_rag_chain()
                # if not self.rag_chain: # 如果再次失败
                return None

            # 1. 提取聊天历史 (如果需要传递给 RAG 链)
            # 注意：当前的 RAGChain 实现 (create_rag_chain) 可能只需要问题和检索到的文档
            # chat_history = chat.chat_data.get("messages", [])
            # 可以选择性地格式化或截断历史记录
            # formatted_history = format_history_for_rag(chat_history) # 示例

            # 2. 准备 RAG 链的输入
            rag_input = RAGInput(
                question=question,
                # chat_history=formatted_history # 如果 RAG 链需要历史记录
            )

            # 3. 调用 RAG 链 (异步)
            # rag_chain 是一个 Runnable 对象
            logger.debug(f"Invoking RAG chain for chat {chat_id} with input: {rag_input.dict()}")
            response = await self.rag_chain.ainvoke(rag_input.dict())
            logger.debug(f"RAG chain response received for chat {chat_id}: {response}")


            # 4. 处理响应
            # 响应的结构取决于 RAG 链的定义，通常包含 'answer' 和 'context'
            answer = response.get("answer", "抱歉，我无法回答这个问题。")
            context_docs = response.get("context", []) # 检索到的文档

            logger.info(f"成功为聊天 {chat_id} 获取 RAG 响应。答案: '{answer[:50]}...'")

            # 5. 将用户问题和 RAG 回答添加到聊天记录 (异步添加?)
            # 注意：add_message_to_chat 是同步的，在异步方法中调用需要注意
            # 最好将数据库操作也异步化，或使用 asyncio.to_thread
            # 这里暂时保持同步调用，但标记为潜在的阻塞点
            user_msg_added = self.add_message_to_chat(chat_id, role="user", content=question)
            if user_msg_added:
                 assistant_msg_added = self.add_message_to_chat(chat_id, role="assistant", content=answer) # 只记录答案
                 if not assistant_msg_added:
                     logger.error(f"Failed to add assistant message to chat {chat_id}")
            else:
                 logger.error(f"Failed to add user message to chat {chat_id}")


            # 6. 返回响应给调用者 (例如 API 端点)
            # 确保 Document 对象可以被序列化
            serializable_context = []
            if context_docs:
                try:
                    serializable_context = [doc.dict() if hasattr(doc, 'dict') else repr(doc) for doc in context_docs]
                except Exception as serialize_err:
                    logger.warning(f"Could not serialize context documents for chat {chat_id}: {serialize_err}")
                    serializable_context = [repr(doc) for doc in context_docs] # Fallback to repr


            return {
                "answer": answer,
                "context": serializable_context # 返回可序列化的上下文
            }

        except Exception as e:
            logger.error(f"为聊天 {chat_id} 获取 RAG 响应时出错: {str(e)}", exc_info=True)
            # 异步地添加错误消息
            try:
                self.add_message_to_chat(chat_id, role="user", content=question)
                self.add_message_to_chat(chat_id, role="assistant", content=f"处理您的问题时遇到错误，请稍后再试。")
            except Exception as log_err:
                 logger.error(f"Failed to add error message to chat {chat_id}: {log_err}")
            return None

    def delete_chat(self, chat_id: str) -> bool:
        """
        删除聊天记录及其关联数据

        Args:
            chat_id: 聊天ID
            
        Returns:
            是否成功删除
        """
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.warning(f"聊天 {chat_id} 不存在，无需删除")
                return False
                
            self.db.delete(chat)
            self.db.commit()
            
            logger.info(f"已删除聊天 {chat_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除聊天 {chat_id} 失败: {str(e)}")
            return False 