import json
import time
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from langchain.embeddings import HuggingFaceBgeEmbeddings
from langchain.vectorstores import DocArrayInMemorySearch
from langchain.schema.runnable import RunnableMap
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from .models import JsonEmbedding
from .utils import normalize_json, calculate_similarity
from .config import embedding_config

class EmbeddingService:
    def __init__(self, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        self.model_name = model_name
        # 初始化BAAI embedding模型
        self.embeddings = HuggingFaceBgeEmbeddings(model_name=model_name)
        # 初始化向量数据库
        self.vectordb = None
        # 初始化Gemini模型
        if embedding_config.GOOGLE_API_KEY:
            self.llm = ChatGoogleGenerativeAI(model="gemini-pro")
        else:
            self.llm = None

    async def create_embedding(self, db: Session, json_data: Dict[str, Any]) -> JsonEmbedding:
        """为JSON数据创建embedding"""
        # 标准化JSON数据
        normalized_data = normalize_json(json_data)
        
        # 使用BAAI模型创建embedding
        embedding_vector = self.embeddings.embed_query(normalized_data)
        
        current_time = time.time()
        
        embedding = JsonEmbedding(
            json_data=json_data,
            embedding_vector=embedding_vector,
            model_name=self.model_name,
            created_at=current_time,
            updated_at=current_time
        )
        
        db.add(embedding)
        db.commit()
        db.refresh(embedding)
        
        return embedding

    async def find_similar(
        self, 
        db: Session, 
        query_json: Dict[str, Any], 
        threshold: float = embedding_config.DEFAULT_SIMILARITY_THRESHOLD,
        limit: int = embedding_config.DEFAULT_SEARCH_LIMIT
    ) -> List[JsonEmbedding]:
        """查找相似的JSON数据"""
        # 获取所有现有的embeddings
        all_embeddings = db.query(JsonEmbedding).all()
        
        # 如果没有数据，返回空列表
        if not all_embeddings:
            return []
            
        # 为查询创建embedding
        query_text = normalize_json(query_json)
        query_embedding = self.embeddings.embed_query(query_text)
        
        # 计算相似度并过滤结果
        similar_embeddings = []
        for embedding in all_embeddings:
            similarity = calculate_similarity(
                query_embedding,
                embedding.embedding_vector
            )
            if similarity >= threshold:
                similar_embeddings.append((embedding, similarity))
        
        # 按相似度排序并返回前N个结果
        similar_embeddings.sort(key=lambda x: x[1], reverse=True)
        return [emb for emb, _ in similar_embeddings[:limit]]

    async def query_with_llm(
        self,
        db: Session,
        question: str,
        context_limit: int = 1
    ) -> str:
        """使用Gemini模型回答基于相似文档的问题"""
        if not self.llm:
            raise ValueError("Gemini API key not configured")
            
        # 创建检索器
        all_embeddings = db.query(JsonEmbedding).all()
        texts = [normalize_json(emb.json_data) for emb in all_embeddings]
        
        self.vectordb = DocArrayInMemorySearch.from_texts(
            texts,
            embedding=self.embeddings
        )
        retriever = self.vectordb.as_retriever(search_kwargs={"k": context_limit})
        
        # 创建prompt模板
        template = """根据以下上下文回答问题，请用完整的句子作答：
        上下文：{context}
        问题：{question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        
        # 创建chain
        chain = RunnableMap({
            "context": lambda x: retriever.get_relevant_documents(x["question"]),
            "question": lambda x: x["question"]
        }) | prompt | self.llm | StrOutputParser()
        
        # 执行chain
        response = await chain.ainvoke({"question": question})
        return response 