import json
import time
import os
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
import logging
import xml.etree.ElementTree as ET
from openai import OpenAI

# 导入工具和配置
from .utils import normalize_json, calculate_similarity
from .config import embedding_config
from config import Config

# 导入LMStudio客户端
from .lmstudio_client import LMStudioClient

# 设置logger
logger = logging.getLogger(__name__)

# 添加全局缓存变量
_embedding_service_instance = None
_deepseek_client = None
_lmstudio_client = None

# 节点数据库路径常量
# NODE_DATABASE_PATH = "database/node_database"
NODE_DATABASE_PATH = "/workspace/database/node_database"

class EmbeddingService:
    def __init__(self, model_name: str = embedding_config.DEFAULT_MODEL_NAME):
        """
        初始化EmbeddingService
        
        Args:
            model_name: 要使用的嵌入模型名称（现在仅用作标识符）
        """
        self.model_name = model_name
        
        # 检查是否使用LMStudio
        if embedding_config.USE_LMSTUDIO:
            logger.info(f"初始化EmbeddingService，使用LMStudio API: {embedding_config.LMSTUDIO_API_BASE_URL}")
            # 初始化LMStudio客户端
            global _lmstudio_client
            if _lmstudio_client is None:
                _lmstudio_client = LMStudioClient(
                    api_base_url=embedding_config.LMSTUDIO_API_BASE_URL,
                    api_key=embedding_config.LMSTUDIO_API_KEY
                )
            self.lmstudio_client = _lmstudio_client
        else:
            logger.info(f"初始化EmbeddingService，使用关键词匹配方法而非嵌入模型")
        
        # 初始化节点缓存
        self.node_cache = {}
        # 加载节点数据库
        self.load_node_database()
        
        # DeepSeek客户端和模型配置
        self.llm_model = Config.DEEPSEEK_MODEL if Config.USE_DEEPSEEK else None
    
    def get_node_template_service(self):
        """获取节点模板服务（懒加载）"""
        try:
            from dependencies import get_node_template_service
            return get_node_template_service()
        except Exception as e:
            logger.error(f"获取节点模板服务失败: {str(e)}")
            return None

    def load_node_database(self):
        """加载节点数据库中的XML文件"""
        try:
            # 尝试从NodeTemplateService获取节点模板
            template_service = self.get_node_template_service()
            if template_service and template_service.templates:
                logger.info(f"从节点模板服务加载节点定义")
                # 将模板转换为节点缓存格式
                for template_id, template in template_service.templates.items():
                    node_data = {
                        "id": template.id,
                        "type": template.type,
                        "fields": {field["name"]: field["default_value"] for field in template.fields},
                    }
                    self.node_cache[f"{template_id}.xml"] = {
                        "json_data": node_data,
                        "file_path": os.path.join(template_service.template_dir, f"{template_id}.xml")
                    }
                logger.info(f"成功从模板服务加载 {len(self.node_cache)} 个节点定义")
                return
                
            # 如果无法从模板服务获取，回退到文件系统方法
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
            logger.info(f"创建EmbeddingService单例实例")
            _embedding_service_instance = cls(model_name)
        return _embedding_service_instance

    async def create_embedding(self, db: Session, json_data: Dict[str, Any]):
        """
        为JSON数据创建embedding（使用LMStudio API或占位符）
        
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
            
            # 使用LMStudio API或占位符
            if embedding_config.USE_LMSTUDIO:
                try:
                    # 使用LMStudio API生成embedding向量
                    embedding_vector = self.lmstudio_client.create_embedding(normalized_data)
                    logger.info(f"成功使用LMStudio API生成embedding向量，维度: {len(embedding_vector)}")
                except Exception as e:
                    logger.error(f"使用LMStudio生成embedding失败: {str(e)}，将使用占位符")
                    # 如果LMStudio调用失败，使用占位符向量
                    embedding_vector = [0.0] * embedding_config.VECTOR_DIMENSION
            else:
                # 使用占位符向量（全0）
                embedding_vector = [0.0] * embedding_config.VECTOR_DIMENSION
            
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
        查找相似的节点数据（使用LMStudio API或关键词匹配）
        
        Args:
            db: 数据库会话
            query_json: 查询JSON
            threshold: 相似度阈值
            limit: 返回结果数量限制
            
        Returns:
            相似文档列表
        """
        try:
            # 延迟导入避免循环导入
            from .models import JsonEmbedding
            
            # 如果使用LMStudio进行向量搜索
            if embedding_config.USE_LMSTUDIO:
                # 将查询转换为文本并生成embedding
                query_text = normalize_json(query_json)
                try:
                    query_embedding = self.lmstudio_client.create_embedding(query_text)
                    
                    # 从数据库获取所有embedding
                    db_embeddings = db.query(JsonEmbedding).all()
                    
                    # 计算相似度并排序
                    results_with_scores = []
                    for emb in db_embeddings:
                        # 确保embedding_vector不是占位符
                        if all(v == 0 for v in emb.embedding_vector):
                            continue
                            
                        # 计算余弦相似度
                        similarity = calculate_similarity(query_embedding, emb.embedding_vector)
                        if similarity >= threshold:
                            results_with_scores.append((emb, similarity))
                    
                    # 按相似度排序并截取top K结果
                    results_with_scores.sort(key=lambda x: x[1], reverse=True)
                    top_results = [item[0] for item in results_with_scores[:limit]]
                    
                    logger.info(f"使用LMStudio API查找到 {len(top_results)} 个相似结果")
                    return top_results
                    
                except Exception as e:
                    logger.error(f"使用LMStudio查找相似项失败: {str(e)}，将回退到关键词匹配")
                    # 如果LMStudio调用失败，回退到关键词匹配
            
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
            logger.error(f"查找相似项时出错: {str(e)}")
            raise

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