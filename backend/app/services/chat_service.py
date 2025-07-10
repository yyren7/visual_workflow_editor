from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
from datetime import datetime
import logging
import uuid
import json
import os # 导入 os 模块

from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from database.models import Chat, Flow

from backend.langgraphchat.retrievers.embedding_retriever import EmbeddingRetriever
from database.embedding.service import DatabaseEmbeddingService

# --- 导入 DbChatMemory 和 BaseMessage --- 
from backend.langgraphchat.memory.db_chat_memory import DbChatMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage  # 添加缺失的导入
from langchain_core.runnables import Runnable # 导入 Runnable 类型提示
# 根据官方文档，直接从 langchain_deepseek 导入 ChatDeepSeek
from langchain_deepseek import ChatDeepSeek 
from langchain_google_genai import ChatGoogleGenerativeAI # 导入 Gemini
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph

# --- 从工作流图模块导入编译函数 ---
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
# --- 工具 ---
from backend.langgraphchat.tools import flow_tools

# --- AgentState ---
from backend.langgraphchat.graph.agent_state import AgentState # 确保 AgentState 被导入

# --- 新增导入 ---
from sqlalchemy.dialects.postgresql import JSONB # 如果您确实在用PostgreSQL并希望用JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.attributes import flag_modified
# --- 结束新增导入 ---

logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务，管理聊天记录并与 Agent 系统交互"""
    
    def __init__(self, db: Session):
        self.db = db
        self._compiled_workflow_graph = None # 用于缓存编译后的 LangGraph
    
    def _get_active_llm(self) -> BaseChatModel:
        """根据环境变量选择并实例化活动 LLM。"""
        provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower()
        logger.info(f"Active LLM provider selected: {provider}")

        if provider == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY environment variable not set.")
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            try:
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash-preview-05-20", 
                    google_api_key=api_key, 
                    streaming=True,
                    temperature=0  # 添加温度参数以确保确定性输出
                )
                logger.info("Instantiated ChatGoogleGenerativeAI (Gemini) with streaming and temperature=0.")
                return llm
            except Exception as e:
                logger.error(f"Failed to instantiate ChatGoogleGenerativeAI: {e}", exc_info=True)
                raise ValueError(f"Failed to instantiate Gemini LLM: {e}")

        elif provider == "deepseek":
            try:
                llm = ChatDeepSeek(
                    model="deepseek-chat",
                    temperature=0  # 添加温度参数以确保确定性输出
                )
                logger.info("Instantiated ChatDeepSeek with temperature=0.")
                return llm
            except Exception as e:
                logger.error(f"Failed to instantiate ChatDeepSeek: {e}", exc_info=True)
                raise ValueError(f"Failed to instantiate DeepSeek LLM: {e}")
        else:
            logger.error(f"Unsupported LLM provider specified: {provider}")
            raise ValueError(f"Unsupported LLM provider: {provider}. Choose 'deepseek' or 'gemini'.")

    @property
    def compiled_workflow_graph(self) -> StateGraph:
        """获取或创建编译后的 LangGraph 工作流实例。"""
        if self._compiled_workflow_graph is None:
            logger.info("Compiled LangGraph not initialized. Creating now...")
            try:
                active_llm = self._get_active_llm()
                # flow_tools 是直接从 backend.langgraphchat.tools 导入的列表
                self._compiled_workflow_graph = compile_workflow_graph(llm=active_llm, custom_tools=flow_tools)
                logger.info("Successfully compiled LangGraph workflow.")
            except Exception as e:
                logger.error(f"Failed to compile LangGraph workflow: {e}", exc_info=True)
                raise RuntimeError(f"Could not compile LangGraph workflow: {e}")
        return self._compiled_workflow_graph

    def create_chat(self, flow_id: str, name: str = "新聊天", chat_data: Optional[Dict[str, Any]] = None) -> Optional[Chat]:
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
    
    def update_chat(self, chat_id: str, name: Optional[str] = None, chat_data: Optional[Dict[str, Any]] = None) -> Optional[Chat]:
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
                
            # 更新字段 - 使用setattr避免类型检查问题
            if name is not None:
                setattr(chat, 'name', name)
                
            if chat_data is not None:
                # 安全更新 chat_data，保留其他可能存在的字段
                existing_data = getattr(chat, 'chat_data', None) or {}
                existing_data.update(chat_data)
                setattr(chat, 'chat_data', existing_data)
            
            # 更新时间戳
            setattr(chat, 'updated_at', datetime.utcnow())
            
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"已更新聊天 {chat_id}")
            return chat
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新聊天 {chat_id} 失败: {str(e)}")
            return None
    
    def add_message_to_chat(self, chat_id: str, role: str, content: str) -> Optional[Tuple[Chat, str]]:
        logger.info(f"ChatService: Attempting to add message to chat_id: {chat_id}, role: {role}") # 修改日志前缀以清晰
        try:
            # 1. 查询聊天对象
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"ChatService: Chat {chat_id} not found. Cannot add message.")
                return None
            
            logger.debug(f"ChatService: Chat {chat_id} found. Current chat_data before modification: {getattr(chat, 'chat_data', None)}") # 记录修改前的数据

            # 2. 安全地获取和修改 chat_data
            chat_data_dict = getattr(chat, 'chat_data', None) or {}
            
            # 确保有messages数组
            if "messages" not in chat_data_dict:
                chat_data_dict["messages"] = []
            elif not isinstance(chat_data_dict["messages"], list):
                 logger.warning(f"ChatService: Chat {chat_id} messages was not a list, resetting to empty list.")
                 chat_data_dict["messages"] = [] # 如果不是列表，重置
                 
            # 3. 准备新消息
            new_message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat() # 使用 UTC 时间
            }
            logger.debug(f"ChatService: Prepared new message for chat {chat_id}: {{'role': '{role}', 'content': '{content[:50]}...', 'timestamp': '{new_message['timestamp']}'}}") # 记录准备好的消息（内容截断）
                 
            # 4. 添加新消息到列表
            chat_data_dict["messages"].append(new_message)
            logger.debug(f"ChatService: Appended new message to chat_data_dict for chat {chat_id}. New messages count: {len(chat_data_dict['messages'])}")
            
            # 5. 更新聊天对象的属性
            setattr(chat, 'chat_data', chat_data_dict)
            # ---- 显式标记 chat_data 已修改 ----
            flag_modified(chat, "chat_data") # <--- 添加此行
            logger.debug(f"ChatService: chat.chat_data assigned and explicitly flagged as modified for chat {chat_id}.")
            
            setattr(chat, 'updated_at', datetime.utcnow())
            
            # 6. 提交到数据库
            self.db.add(chat) # 通常在对象已从会话加载后，修改会自动跟踪，但 add() 无害
            logger.info(f"ChatService: Attempting commit for chat {chat_id} after adding/modifying message...")
            self.db.commit()
            logger.info(f"ChatService: Commit successful for chat {chat_id}.")
            
            # --- 调试：提交后立即用同一会话查询并记录 ---
            # 首先刷新当前 chat 实例以获取数据库的最新状态
            logger.info(f"ChatService: Attempting to refresh chat object {chat_id} in current session...")
            self.db.refresh(chat)
            logger.info(f"ChatService: Chat {chat_id} refreshed. Verifying data in current session: chat.chat_data.messages count = {len(getattr(chat, 'chat_data', {}).get('messages', []))}")
            current_chat_data = getattr(chat, 'chat_data', {})
            if current_chat_data.get('messages'):
                # 记录最后一条消息的部分内容以供验证
                last_msg_preview = current_chat_data['messages'][-1].get('content', '')[:50]
                last_msg_role = current_chat_data['messages'][-1].get('role')
                logger.debug(f"ChatService: Last message in current session after refresh for {chat_id}: {{'role': '{last_msg_role}', 'content': '{last_msg_preview}...'}}")
            # --- 结束调试 ---

            logger.info(f"ChatService: Successfully added and committed '{role}' message to chat {chat_id}.")
            # 返回包含新消息时间戳的Chat对象或仅消息本身
            return (chat, new_message["timestamp"])

        except Exception as e:
            self.db.rollback()
            logger.error(f"ChatService: Error adding message to chat {chat_id}: {e}", exc_info=True) # 保持 exc_info=True
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

    def edit_user_message_and_truncate(self, chat_id: str, message_timestamp: str, new_content: str) -> Optional[Chat]:
        """
        编辑用户消息，删除此消息之后的所有消息，并以新内容重新生成用户消息。

        Args:
            chat_id: 聊天ID
            message_timestamp: 要编辑的用户消息的时间戳
            new_content: 用户消息的新内容

        Returns:
            更新后的Chat对象，如果失败则返回None
        """
        logger.info(f"ChatService: Attempting to edit message in chat_id: {chat_id} at timestamp: {message_timestamp}")
        try:
            chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.error(f"ChatService: Chat {chat_id} not found. Cannot edit message.")
                return None

            chat_data_variable = MutableDict.as_mutable(chat.chat_data) if chat.chat_data else MutableDict()
            if "messages" not in chat_data_variable or not isinstance(chat_data_variable["messages"], list):
                logger.error(f"ChatService: Chat {chat_id} has no messages or messages are not a list. Cannot edit.")
                return None

            messages: List[Dict[str, Any]] = chat_data_variable["messages"]
            target_message_index = -1
            for i, msg in enumerate(messages):
                if msg.get("timestamp") == message_timestamp and msg.get("role") == "user":
                    target_message_index = i
                    break
            
            if target_message_index == -1:
                logger.error(f"ChatService: User message with timestamp {message_timestamp} not found in chat {chat_id}.")
                return None

            logger.debug(f"ChatService: Found user message at index {target_message_index} for editing.")

            # 删除目标消息及之后的所有消息
            truncated_messages = messages[:target_message_index]
            logger.debug(f"ChatService: Messages truncated. Kept {len(truncated_messages)} messages.")

            # 添加编辑后的用户消息
            edited_message = {
                "role": "user",
                "content": new_content,
                "timestamp": datetime.utcnow().isoformat() # 使用新的时间戳
            }
            truncated_messages.append(edited_message)
            logger.debug(f"ChatService: Added edited user message. Total messages now: {len(truncated_messages)}")
            
            chat_data_variable["messages"] = truncated_messages
            chat.chat_data = chat_data_variable
            flag_modified(chat, "chat_data")
            chat.updated_at = datetime.utcnow()

            self.db.add(chat)
            self.db.commit()
            self.db.refresh(chat)
            
            logger.info(f"ChatService: Successfully edited message in chat {chat_id} at timestamp {message_timestamp}.")
            return chat

        except Exception as e:
            logger.error(f"ChatService: Error editing message in chat {chat_id}: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception as rb_err:
                logger.error(f"ChatService: Rollback FAILED while editing message in chat {chat_id}: {rb_err}", exc_info=True)
            return None 

    def get_chat_history(self, chat_id: str) -> List[BaseMessage]:
        # Implementation of get_chat_history method
        pass 

    async def invoke_workflow_for_chat(self, chat_id: str, user_input: str, current_flow_id: Optional[str] = None) -> AgentState:
        """
        为给定的聊天调用主LangGraph工作流，并处理SAS子图状态的持久化。

        Args:
            chat_id: 当前聊天的ID。
            user_input: 用户提供的最新输入。
            current_flow_id: 当前流程图的ID (可选，如果可以从chat对象获取则更好)。

        Returns:
            图执行后的最终 AgentState。
        """
        logger.info(f"ChatService: Invoking workflow for chat_id: {chat_id} with user_input: '{user_input[:50]}...'")

        chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            logger.error(f"ChatService: Chat {chat_id} not found. Cannot invoke workflow.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

        if not chat.chat_data:
            chat.chat_data = MutableDict()
        
        # 确保 chat_data 中有 messages 列表
        if "messages" not in chat.chat_data or not isinstance(chat.chat_data["messages"], list):
            chat.chat_data["messages"] = []

        # 1. 从 chat.chat_data 加载持久化的 SAS 状态  
        persisted_sas_state = chat.chat_data.get("persisted_sas_state")
        if persisted_sas_state:
            logger.info(f"ChatService: Found persisted SAS state for chat {chat_id}.")
        else:
            logger.info(f"ChatService: No persisted SAS state found for chat {chat_id}.")

        # 2. 准备 AgentState
        #   a. 获取完整的消息历史 (这里简单地从chat_data中的messages转换，实际应用中 DbChatMemory 更好)
        #      注意：DbChatMemory 通常在图的 AgentState 内部或图的入口节点使用。
        #      这里，我们直接使用存储在 chat.chat_data['messages'] 中的消息历史。
        
        raw_message_history = chat.chat_data.get("messages", [])
        #  转换原始消息历史为 BaseMessage 对象列表 (如果需要)
        #  这里假设 LangGraph 的 AgentState 可以直接处理 HumanMessage/AIMessage 字典，
        #  或者在 AgentState 初始化时进行转换。
        #  为了简单起见，我们假设 compiled_workflow_graph 的输入 AgentState 可以接受 HumanMessage
        
        #  确保最新的用户输入被添加为 HumanMessage
        #  在实际应用中，你可能已经通过 add_message_to_chat 将用户消息持久化了。
        #  这里的逻辑是假设我们正在处理一个刚刚收到的用户输入。
        current_messages_for_graph = []
        for msg_data in raw_message_history:
            if msg_data.get("role") == "user":
                current_messages_for_graph.append(HumanMessage(content=msg_data.get("content", "")))
            elif msg_data.get("role") == "assistant" or msg_data.get("role") == "ai": # Langchain 通常用 'ai'
                 current_messages_for_graph.append(AIMessage(content=msg_data.get("content", "")))
            # 可以根据需要处理其他类型的消息

        # 添加当前的用户输入
        current_messages_for_graph.append(HumanMessage(content=user_input))

        #  b. 构建 AgentState 输入字典
        #  注意：AgentState 已移除 sas_planner_subgraph_state 字段
        agent_state_input = {
            "messages": current_messages_for_graph,
            "input": user_input, # 当前用户的直接输入
            "user_id": chat_id, # 可以用 chat_id 作为 user_id 或会话标识
            "current_flow_id": current_flow_id or chat.flow_id, # 使用提供的或从chat对象获取
            "flow_context": {}, # 根据需要填充流程上下文
            "chat_history_in_db_for_summary": True, # 示例：指示图可以使用数据库历史
            "input_processed": False, # 通常在图的 input_handler 中设置为 True
            # 注入恢复的状态 - sas_planner_subgraph_state字段已移除
            # 其他 AgentState 中定义的字段，根据需要提供默认值或从chat对象加载
            "task_route_decision": None, 
            "user_request_for_router": None,
            "completion_status": None,
            "clarification_question": None,
            "is_error": False,
            "error_message": None,
        }
        
        # 确保所有 AgentState 的必填字段都有值，这里我们创建 AgentState 实例以验证
        try:
            # 尝试创建 AgentState 实例以确保所有字段都已提供或有默认值
            # 如果 AgentState 有严格的 schema，这里可能会抛出错误
            AgentState(**agent_state_input) 
        except Exception as e_state:
            logger.error(f"ChatService: Error creating AgentState instance from input dict for chat {chat_id}: {e_state}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error preparing agent state: {e_state}")


        logger.info(f"ChatService: Invoking compiled_workflow_graph for chat {chat_id}...")
        # 3. 调用 LangGraph 工作流
        #    compiled_workflow_graph 需要 AgentState 的字典形式作为输入
        output_state_dict = await self.compiled_workflow_graph.ainvoke(
            agent_state_input, 
            {"recursion_limit": 25} # 根据需要调整递归限制
        )
        
        # 将输出字典转换回 AgentState 对象
        output_agent_state = AgentState(**output_state_dict)
        logger.info(f"ChatService: Workflow invocation completed for chat {chat_id}. Status: {output_agent_state.completion_status}")

        # 4. 根据返回的 AgentState 更新或清除持久化的 SAS 状态
        if output_agent_state.completion_status == "needs_clarification":
            logger.info(f"ChatService: SAS needs clarification for chat {chat_id}. Persisting SAS state.")
            chat.chat_data["persisted_sas_state"] = persisted_sas_state  # 保持现有状态
        else:
            if "persisted_sas_state" in chat.chat_data:
                logger.info(f"ChatService: SAS status is '{output_agent_state.completion_status}'. Clearing persisted SAS state for chat {chat_id}.")
                del chat.chat_data["persisted_sas_state"]
            else:
                logger.info(f"ChatService: SAS status is '{output_agent_state.completion_status}'. No persisted SAS state to clear for chat {chat_id}.")

        # 5. 更新 chat_data 中的消息历史 (可选，如果图的输出消息需要合并)
        #    通常，图的 AgentState 的 "messages" 字段会包含最新的完整对话历史。
        #    我们应该用这个来更新数据库中的消息。
        updated_messages_for_db = []
        for msg in output_agent_state.messages:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            if isinstance(msg, AIMessage) and msg.tool_calls: # 处理工具调用消息的存储
                # Langchain 的 AIMessage.tool_calls 是一个列表，每个元素包含 id, name, args
                # 你可能需要将其转换为适合存储的格式
                 tool_calls_content = json.dumps([tc for tc in msg.tool_calls]) # 示例：直接转为JSON字符串
                 updated_messages_for_db.append({
                    "role": role, 
                    "content": msg.content, # 主要文本内容
                    "tool_calls": tool_calls_content, # 存储工具调用信息
                    "timestamp": datetime.utcnow().isoformat() # 或者从消息对象中获取时间戳
                })
            else:
                 updated_messages_for_db.append({
                    "role": role, 
                    "content": str(msg.content), # 确保内容是字符串
                    "timestamp": datetime.utcnow().isoformat()
                })

        chat.chat_data["messages"] = updated_messages_for_db
        
        # 6. 更新Flow的agent_state（已移除sas_planner_subgraph_state字段）
        flow = self.db.query(Flow).filter(Flow.id == chat.flow_id).first()
        if flow:
            # SAS相关的agent_state更新逻辑已简化，因为不再使用subgraph状态
            logger.info(f"ChatService: Flow {flow.id} found for chat {chat_id}, but agent_state update is skipped")
        
        # 7. 保存对 chat 对象的更改
        try:
            flag_modified(chat, "chat_data") # 显式标记 chat_data 已修改
            self.db.add(chat) # 虽然 chat 是从会话加载的，但 add() 无害
            self.db.commit()
            self.db.refresh(chat) # 获取数据库的最新状态
            logger.info(f"ChatService: Successfully updated chat {chat_id} with new SAS state and messages.")
        except Exception as e_commit:
            self.db.rollback()
            logger.error(f"ChatService: Error committing changes for chat {chat_id} after workflow invocation: {e_commit}", exc_info=True)
            # 根据错误处理策略，可能需要将错误信息加入到 output_agent_state 中
            # 这里简单地重新抛出，或者返回一个包含错误信息的 AgentState
            output_agent_state.is_error = True
            output_agent_state.error_message = f"Failed to save chat state: {e_commit}"
            # 不再抛出 HTTPException，而是让调用者处理 AgentState 中的错误

        return output_agent_state
# --- END of invoke_workflow_for_chat method --- 