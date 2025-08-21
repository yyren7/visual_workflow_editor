from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from typing import List
from app.database import Base
from langchain_huggingface import HuggingFaceEmbeddings

class JsonEmbedding(Base):
    """存储JSON数据的embedding信息"""
    __tablename__ = "json_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    json_data = Column(JSON, nullable=False)
    embedding_vector = Column(JSON, nullable=False)  # 存储embedding向量
    embedding_metadata = Column(JSON, nullable=True)  # 可选的元数据
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
    model_name = Column(String, nullable=False)  # 使用的embedding模型名称
    created_at = Column(Float, nullable=False)  # Unix timestamp
    updated_at = Column(Float, nullable=False)  # Unix timestamp 