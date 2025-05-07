from typing import List, Optional
import logging

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict

# 导入 ChatService 以便与数据库交互
# 注意：这里的导入路径可能需要根据您的项目结构调整
# 理想情况下，ChatService 实例应该通过依赖注入传入
# 将导入移到方法内部以避免循环导入

logger = logging.getLogger(__name__)

class DbChatMemory(BaseChatMessageHistory, BaseModel):
    """
    使用数据库作为后端的聊天记录管理。
    通过 ChatService 与数据库中的 Chat 模型交互。
    """
    chat_id: str
    db_session: Session = Field(exclude=True) # 排除在模型序列化之外
    chat_service: Optional['ChatService'] = Field(exclude=True, default=None) # 可选，允许延迟初始化

    # Pydantic V2 配置：允许任意类型（如 SQLAlchemy Session）
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 用于存储从数据库加载的消息 - 重命名避免 Pydantic 错误
    internal_messages: List[BaseMessage] = Field(default_factory=list, exclude=True)
    # 标记是否已从数据库加载 - 重命名避免 Pydantic 错误
    is_initialized: bool = Field(default=False, exclude=True)

    def _get_chat_service(self) -> 'ChatService': # 使用字符串类型提示避免导入
        """获取或初始化 ChatService 实例。"""
        if self.chat_service is None:
             # 如果未提供，则尝试使用 db_session 初始化
             logger.debug(f"Initializing ChatService within DbChatMemory for chat_id: {self.chat_id}")
             # 在方法内部导入以打破循环
             from backend.app.services.chat_service import ChatService
             self.chat_service = ChatService(db=self.db_session)
        return self.chat_service

    def _load_messages(self):
        """从数据库加载消息 (如果尚未加载)。"""
        if not self.is_initialized:
            logger.debug(f"Loading messages from DB for chat_id: {self.chat_id}")
            service = self._get_chat_service()
            chat = service.get_chat(self.chat_id)
            if chat and chat.chat_data and isinstance(chat.chat_data.get("messages"), list):
                # 将数据库中的字典转换为 LangChain BaseMessage 对象
                raw_messages = chat.chat_data["messages"]
                try:
                    # 注意：确保数据库中存储的格式与 messages_from_dict 兼容
                    # 通常包含 'type' 和 'data' 键
                    # 如果您的格式是 {'role': 'user', 'content': '...'}，需要转换
                    converted_messages = []
                    for msg_data in raw_messages:
                        role = msg_data.get("role")
                        content = msg_data.get("content")
                        if role == "user":
                            converted_messages.append({"type": "human", "data": {"content": content}})
                        elif role == "assistant":
                             converted_messages.append({"type": "ai", "data": {"content": content}})
                        elif role == "system":
                             converted_messages.append({"type": "system", "data": {"content": content}})
                        else:
                             logger.warning(f"Unknown message role '{role}' in chat {self.chat_id}")
                             # 可以选择添加为通用消息或跳过
                             # converted_messages.append({"type": "chat", "data": {"content": content, "role": role}})

                    self._messages = messages_from_dict(converted_messages)
                    self.internal_messages = messages_from_dict(converted_messages)
                    logger.info(f"Loaded {len(self._messages)} messages for chat {self.chat_id}.")
                    logger.info(f"Loaded {len(self.internal_messages)} messages for chat {self.chat_id}.")
                except Exception as e:
                     logger.error(f"Failed to convert DB messages to LangChain messages for chat {self.chat_id}: {e}")
                     self.internal_messages = [] # 加载失败则清空
            else:
                logger.info(f"No existing messages found or invalid format for chat {self.chat_id}. Starting new history.")
                self.internal_messages = []
            self.is_initialized = True

    @property
    def messages(self) -> List[BaseMessage]:
        """获取消息列表，按插入顺序。"""
        self._load_messages() # 确保消息已加载
        return self.internal_messages

    def add_message(self, message: BaseMessage) -> None:
        """将消息添加到内存中的消息列表。数据库保存由外部处理。"""
        # self._load_messages() # Ensure messages loaded before appending, though likely already loaded if chain accessed .messages
        logger.debug(f"Adding message to in-memory list for DbChatMemory instance (chat_id: {self.chat_id})")
        self.internal_messages.append(message)
        # 注意：不执行数据库保存操作，由外部 ChatService 处理。

    def clear(self) -> None:
        """清除内存中的消息列表。数据库清除由外部处理。"""
        logger.debug(f"Clearing in-memory messages for DbChatMemory instance (chat_id: {self.chat_id}). DB clear handled externally.")
        self.internal_messages = []
        self.is_initialized = True # 清除后标记为已初始化（空状态）
        # 注意：不执行数据库清除操作，由外部 ChatService 处理。


# --- 使用示例 (假设在 Chain 或 Agent 中) ---

# def get_session(): # 你的 SQLAlchemy session 工厂
#     db = SessionLocal() 
#     try:
#         yield db
#     finally:
#         db.close()

# db_session = next(get_session())
# chat_id = "some_chat_uuid" 

# memory = DbChatMemory(chat_id=chat_id, db_session=db_session)

# # 添加消息
# memory.add_user_message("你好！")
# memory.add_ai_message("你好！有什么可以帮您的？")

# # 获取历史记录
# history = memory.messages 
# print(history)

# # 清除历史
# # memory.clear() 