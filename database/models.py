from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
# 对于PostgreSQL数据库，可以使用以下导入
# from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional

from database.connection import Base
from database.embedding.config import embedding_config

logger = logging.getLogger(__name__)

class User(Base):
    """
    Represents a user in the system.
    """
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    # 使用String类型存储UUID，适用于SQLite
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(String, default="true", nullable=False)  # 添加 is_active 字段
    last_selected_flow_id = Column(String(36), ForeignKey("flows.id", ondelete="SET NULL"), nullable=True)
    flows = relationship("Flow", back_populates="owner", foreign_keys="Flow.owner_id")
    last_selected_flow = relationship("Flow", foreign_keys=[last_selected_flow_id])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Flow(Base):
    """
    Represents a flow (diagram) in the system.
    """
    __tablename__ = "flows"
    __table_args__ = {'extend_existing': True}

    # 使用String类型存储UUID，适用于SQLite
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    flow_data = Column(JSON, nullable=False, default={})  # Stores the flow data as a JSON object
    owner_id = Column(String(36), ForeignKey("users.id"))
    owner = relationship("User", back_populates="flows", foreign_keys=[owner_id])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    name = Column(String, nullable=False, default="Untitled Flow")  # Added flow name
    variables = relationship("FlowVariable", back_populates="flow")
    # graph_type = Column(String, nullable=True, index=True) # REMOVED graph_type field

    # --- 修正 'chats' 关系并指定外键 ---
    chats = relationship("Chat", back_populates="flow", foreign_keys="Chat.flow_id")

    # --- 添加 last_interacted_chat_id ---
    last_interacted_chat_id = Column(String(36), ForeignKey('chats.id', ondelete="SET NULL"), nullable=True)
    # --- 结束添加 ---

    # --- 添加 agent_state 用于存储 LangGraph 状态 ---
    # agent_state = Column(JSON, nullable=True, default={})  # REMOVED
    # --- 结束添加 ---

    def __repr__(self):
        return f"<Flow(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"


class Chat(Base):
    """
    聊天记录模型，每个聊天从属于一个流程图
    """
    __tablename__ = "chats"
    __table_args__ = {'extend_existing': True}

    # 使用String类型存储UUID，适用于SQLite
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    chat_data = Column(JSON, nullable=False, default={})  # 存储聊天数据，JSON格式
    flow_id = Column(String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False) # 这个外键是 chats 关系的基础
    flow = relationship("Flow", back_populates="chats", foreign_keys=[flow_id]) # 明确指定 Chat.flow 的外键
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    name = Column(String, nullable=False, default="未命名聊天")  # 聊天名称

    def __repr__(self):
        return f"<Chat(id={self.id}, name='{self.name}', flow_id={self.flow_id})>"


class FlowVariable(Base):
    """流程图变量模型"""
    __tablename__ = "flow_variables"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 建立与Flow的关系
    flow = relationship("Flow", back_populates="variables")

    # 为每个流程图的变量名添加唯一约束
    __table_args__ = (UniqueConstraint('flow_id', 'key', name='uix_flow_variable'),)


class VersionInfo(Base):
    """系统版本信息模型"""
    __tablename__ = "version_info"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False, default="0.0.0")
    last_updated = Column(String, nullable=False, default="未知")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<VersionInfo(version='{self.version}', last_updated='{self.last_updated}')>"


class JsonEmbedding(Base):
    """
    JSON 数据嵌入模型
    """
    __tablename__ = 'json_embeddings'
    __table_args__ = {'extend_existing': True}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 存储原始JSON数据
    json_data = Column(JSONB, nullable=False)
    
    # 使用 pgvector 存储嵌入向量
    # 需要从 embedding_config 获取维度
    embedding_vector = Column(Vector(embedding_config.VECTOR_DIMENSION))
    
    # 嵌入模型名称
    model_name = Column(String(100), nullable=False, index=True)
    
    # 时间戳 (保留 Float 类型，根据原始代码)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    
    # (可选) 元数据，例如来源文档ID、类型等
    meta_data = Column(JSONB, nullable=True)

    # 创建 HNSW 或 IVFFlat 索引以加速相似性搜索
    # HNSW 索引（推荐，适用于高维数据）
    __table_args__ = (
        Index(
            'ix_json_embeddings_embedding_hnsw',
            embedding_vector,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64} # HNSW 参数
        ),
        Index('ix_json_embeddings_model_name', 'model_name'), # 索引模型名称
    )
    
    # IVFFlat 索引（可选，可能在某些场景下更快）
    # __table_args__ = (
    #     Index(
    #         'ix_json_embeddings_embedding_ivfflat',
    #         embedding_vector,
    #         postgresql_using='ivfflat',
    #         postgresql_with={'lists': 100} # 列表数量，通常是 sqrt(N)
    #     ),
    # )

    def __repr__(self):
        return f"<JsonEmbedding(id={self.id}, model='{self.model_name}')>"

# 可选: 流程图变量模型 (如果需要单独管理)
# class FlowVariable(Base):
#     # ... existing code ...
#     pass # 省略未更改部分

# 创建所有表 (通常在应用启动时或迁移脚本中执行)
# from database.connection import engine
# Base.metadata.create_all(bind=engine)
# logger.info("数据库模型已初始化 (如果表不存在则创建)")

# 注意：使用 pgvector 需要在数据库中启用扩展: CREATE EXTENSION vector; 