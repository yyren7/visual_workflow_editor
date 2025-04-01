from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# 对于PostgreSQL数据库，可以使用以下导入
# from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

from database.connection import Base

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
    chats = relationship("Chat", back_populates="flow")  # 添加与Chat的关系

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
    flow_id = Column(String(36), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False)
    flow = relationship("Flow", back_populates="chats")  # 与Flow的关系
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