import json
import time
import os
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
# 注释掉模型导入
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_community.vectorstores import DocArrayInMemorySearch
# from langchain.schema.runnable import RunnableMap
# from langchain.prompts import ChatPromptTemplate
# from langchain.schema.output_parser import StrOutputParser
from openai import OpenAI
import logging
import xml.etree.ElementTree as ET

# 改为延迟导入，避免循环导入
# from .models import JsonEmbedding
from .utils import normalize_json, calculate_similarity
from .config import embedding_config
from backend.app.config import Config

# 设置logger
logger = logging.getLogger(__name__)

# 添加一个全局变量存储单例实例
_embedding_service_instance = None
# 添加初始化标记，避免重复打印初始化消息
_model_initialized = {}
# 添加DeepSeek客户端缓存
_deepseek_client = None

# 添加节点数据库路径常量
NODE_DATABASE_PATH = "database/node_database"

class EmbeddingService:
    def __init__(self, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        """
        初始化EmbeddingService
        
        Args:
            model_name: 要使用的嵌入模型名称（现在仅用作标识符）
        """
        self.model_name = model_name
        logger.info(f"初始化EmbeddingService，使用node_database目录而非模型: {model_name}")
        
        # 注释掉模型加载代码
        """
        # 初始化BAAI embedding模型，使用缓存避免重复加载
        global _embeddings_models, _model_initialized
        if model_name not in _embeddings_models:
            if model_name not in _model_initialized:
                logger.info(f"初始化嵌入模型: {model_name}")
                _model_initialized[model_name] = True
            try:
                _embeddings_models[model_name] = HuggingFaceEmbeddings(model_name=model_name)
                logger.info(f"嵌入模型 {model_name} 初始化成功")
            except Exception as e:
                logger.error(f"初始化嵌入模型 {model_name} 失败: {str(e)}")
                raise
        else:
            logger.debug(f"使用缓存的嵌入模型: {model_name}")
            
        self.embeddings = _embeddings_models[model_name]
        """
        
        # 初始化节点缓存
        self.node_cache = {}
        # 加载节点数据库
        self.load_node_database()
        
        # 初始化向量数据库
        self.vectordb = None
        
        # DeepSeek客户端和模型配置
        self.llm_model = Config.DEEPSEEK_MODEL if Config.USE_DEEPSEEK else None
    
    def load_node_database(self):
        """加载节点数据库中的XML文件"""
        try:
            if not os.path.exists(NODE_DATABASE_PATH):
                logger.error(f"节点数据库路径不存在: {NODE_DATABASE_PATH}")
                return
                
            logger.info(f"从路径加载节点数据库: {NODE_DATABASE_PATH}")
            node_files = [f for f in os.listdir(NODE_DATABASE_PATH) if f.endswith('.xml')]
            
            for file_name in node_files:
                file_path = os.path.join(NODE_DATABASE_PATH, file_name)
                try:
                    # 解析XML文件
                    tree = ET.parse(file_path)
                    root = tree.getroot()
                    
                    # 提取节点信息
                    node_data = self._extract_node_data(root, file_name)
                    
                    # 缓存节点数据
                    if node_data:
                        self.node_cache[file_name] = {
                            "json_data": node_data,
                            "file_path": file_path
                        }
                    
                except Exception as e:
                    logger.error(f"解析XML文件 {file_name} 时出错: {str(e)}")
            
            logger.info(f"成功加载 {len(self.node_cache)} 个节点定义")
        except Exception as e:
            logger.error(f"加载节点数据库时出错: {str(e)}")
    
    def _extract_node_data(self, root, file_name):
        """从XML根元素提取节点数据"""
        try:
            # 查找block元素
            blocks = root.findall(".//block")
            if not blocks:
                return None
                
            # 获取第一个block元素
            block = blocks[0]
            
            # 提取类型
            node_type = block.get("type", "unknown")
            
            # 提取字段
            fields = {}
            for field in block.findall("./field"):
                name = field.get("name", "")
                value = field.text or ""
                fields[name] = value
            
            # 构建节点数据
            node_data = {
                "id": file_name.replace(".xml", ""),
                "type": node_type,
                "fields": fields,
            }
            
            return node_data
        except Exception as e:
            logger.error(f"提取节点数据时出错: {str(e)}")
            return None
            
    @classmethod
    def get_instance(cls, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        """
        获取EmbeddingService的单例实例
        
        Args:
            model_name: 要使用的嵌入模型名称
            
        Returns:
            EmbeddingService实例
        """
        global _embedding_service_instance
        if _embedding_service_instance is None:
            logger.info(f"创建EmbeddingService单例实例，使用node_database")
            _embedding_service_instance = cls(model_name)
        return _embedding_service_instance

    async def create_embedding(self, db: Session, json_data: Dict[str, Any]):
        """
        为JSON数据创建embedding（现在直接将数据存储到数据库，不生成实际的embedding）
        
        Args:
            db: 数据库会话
            json_data: 要嵌入的JSON数据
            
        Returns:
            创建的嵌入记录
        """
        # 延迟导入避免循环导入
        from .models import JsonEmbedding
        
        try:
            # 标准化JSON数据
            normalized_data = normalize_json(json_data)
            
            # 注释掉使用模型创建embedding
            # embedding_vector = self.embeddings.embed_query(normalized_data)
            
            # 使用占位符向量（全0）
            placeholder_vector = [0.0] * embedding_config.VECTOR_DIMENSION
            
            current_time = time.time()
            
            embedding = JsonEmbedding(
                json_data=json_data,
                embedding_vector=placeholder_vector,  # 使用占位符
                model_name=self.model_name,
                created_at=current_time,
                updated_at=current_time
            )
            
            db.add(embedding)
            db.commit()
            db.refresh(embedding)
            
            return embedding
        except Exception as e:
            logger.error(f"创建嵌入时出错: {str(e)}")
            db.rollback()
            raise

    async def find_similar(
        self, 
        db: Session, 
        query_json: Dict[str, Any], 
        threshold: float = embedding_config.DEFAULT_SIMILARITY_THRESHOLD,
        limit: int = embedding_config.DEFAULT_SEARCH_LIMIT
    ):
        """
        查找相似的节点数据（现在直接从node_database读取）
        
        Args:
            db: 数据库会话（现在不使用）
            query_json: 查询JSON
            threshold: 相似度阈值（现在不使用）
            limit: 返回结果数量限制
            
        Returns:
            相似文档列表
        """
        try:
            # 延迟导入避免循环导入
            from .models import JsonEmbedding
            
            # 如果节点缓存为空，重新加载
            if not self.node_cache:
                self.load_node_database()
            
            # 如果仍然为空，返回空列表
            if not self.node_cache:
                logger.warning("节点缓存为空，无法查找相似节点")
                return []
            
            # 简单的关键词匹配
            query_text = normalize_json(query_json).lower()
            matches = []
            
            # 遍历节点缓存
            for file_name, node_info in self.node_cache.items():
                node_data = node_info["json_data"]
                
                # 将节点数据转换为文本
                node_text = normalize_json(node_data).lower()
                
                # 简单的文本匹配检查（至少包含一个关键词）
                keywords = query_text.split()
                matched = False
                
                # 任何关键词匹配都算匹配
                for keyword in keywords:
                    if len(keyword) > 3 and keyword in node_text:  # 仅考虑3个字符以上的关键词
                        matched = True
                        break
                
                if matched:
                    # 创建一个模拟的JsonEmbedding对象
                    embedding = JsonEmbedding(
                        id=len(matches) + 1,
                        json_data=node_data,
                        embedding_vector=[0.0] * embedding_config.VECTOR_DIMENSION,
                        model_name=self.model_name,
                        created_at=time.time(),
                        updated_at=time.time()
                    )
                    matches.append(embedding)
            
            # 随机打乱结果（代替相似度排序）
            import random
            random.shuffle(matches)
            
            # 返回限制数量的结果
            return matches[:limit]
        except Exception as e:
            logger.error(f"查找相似文档时出错: {str(e)}")
            return []

    async def query_with_llm(
        self,
        db: Session,
        question: str,
        context_limit: int = 1
    ) -> str:
        """
        使用DeepSeek模型回答基于相似文档的问题
        
        Args:
            db: 数据库会话
            question: 问题
            context_limit: 上下文限制
            
        Returns:
            LLM回答
        """
        if not Config.USE_DEEPSEEK:
            logger.error("DeepSeek API未启用")
            raise ValueError("DeepSeek API未启用")
            
        try:
            # 懒加载DeepSeek客户端（使用全局缓存）
            global _deepseek_client
            if _deepseek_client is None and Config.USE_DEEPSEEK:
                logger.info("初始化DeepSeek客户端")
                _deepseek_client = OpenAI(
                    api_key=Config.DEEPSEEK_API_KEY, 
                    base_url=Config.DEEPSEEK_BASE_URL
                )
            
            # 使用全局客户端
            client = _deepseek_client
                
            # 使用关键词搜索而非向量检索
            similar_nodes = await self.find_similar(db, {"query": question}, limit=context_limit)
            
            # 如果没有找到相关节点，返回默认回答
            if not similar_nodes:
                return "我找不到相关的节点信息来回答您的问题。您可以尝试更具体的描述。"
                
            # 构建上下文
            context_items = []
            for node in similar_nodes:
                node_data = node.json_data
                node_desc = f"节点ID: {node_data.get('id', 'unknown')}\n类型: {node_data.get('type', 'unknown')}"
                
                # 添加字段信息
                fields = node_data.get("fields", {})
                if fields:
                    field_info = "\n".join([f"{key}: {value}" for key, value in fields.items()])
                    node_desc += f"\n字段: \n{field_info}"
                    
                context_items.append(node_desc)
                
            context = "\n\n---\n\n".join(context_items)
            
            # 构建提示
            prompt = f"""根据以下上下文回答问题，请用完整的句子作答：
            上下文：{context}
            问题：{question}
            """
            
            # 调用DeepSeek API
            messages = [
                {"role": "system", "content": "你是一个专业的流程图节点助手，能够基于现有节点提供简明的解释。"},
                {"role": "user", "content": prompt}
            ]
            
            response = client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"使用LLM查询时出错: {str(e)}")
            return f"处理您的问题时出错: {str(e)}" 