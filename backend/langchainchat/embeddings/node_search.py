"""
节点搜索功能
提供对节点数据库的搜索功能
"""

import os
import logging
import xml.etree.ElementTree as ET
import random
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

# 导入本地配置和工具
from .config import search_config
from .utils import normalize_json, extract_keywords, format_search_result

# 节点数据库路径常量
NODE_DATABASE_PATH = "/workspace/database/node_database"

# 设置logger
logger = logging.getLogger(__name__)

# 节点缓存
_node_cache = {}

def load_node_database() -> Dict[str, Dict[str, Any]]:
    """
    加载节点数据库中的XML文件
    
    Returns:
        节点缓存字典
    """
    global _node_cache
    
    # 如果缓存已加载，直接返回
    if _node_cache:
        return _node_cache
    
    try:
        # 首先尝试从节点模板服务获取
        template_service = _get_node_template_service()
        if template_service and template_service.templates:
            logger.info(f"从节点模板服务加载节点定义")
            # 将模板转换为节点缓存格式
            for template_id, template in template_service.templates.items():
                node_data = {
                    "id": template.id,
                    "type": template.type,
                    "fields": {field["name"]: field["default_value"] for field in template.fields},
                }
                _node_cache[f"{template_id}.xml"] = {
                    "json_data": node_data,
                    "file_path": os.path.join(template_service.template_dir, f"{template_id}.xml")
                }
            logger.info(f"成功从模板服务加载 {len(_node_cache)} 个节点定义")
            return _node_cache
            
        # 如果无法从模板服务获取，回退到文件系统方法
        if not os.path.exists(NODE_DATABASE_PATH):
            logger.error(f"节点数据库路径不存在: {NODE_DATABASE_PATH}")
            return {}
            
        logger.info(f"从路径加载节点数据库: {NODE_DATABASE_PATH}")
        node_files = [f for f in os.listdir(NODE_DATABASE_PATH) if f.endswith('.xml')]
        
        for file_name in node_files:
            file_path = os.path.join(NODE_DATABASE_PATH, file_name)
            try:
                # 解析XML文件
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # 提取节点信息
                node_data = _extract_node_data(root, file_name)
                
                # 缓存节点数据
                if node_data:
                    _node_cache[file_name] = {
                        "json_data": node_data,
                        "file_path": file_path
                    }
                
            except Exception as e:
                logger.error(f"解析XML文件 {file_name} 时出错: {str(e)}")
        
        logger.info(f"成功加载 {len(_node_cache)} 个节点定义")
        return _node_cache
    except Exception as e:
        logger.error(f"加载节点数据库时出错: {str(e)}")
        return {}

def _get_node_template_service():
    """获取节点模板服务（懒加载）"""
    try:
        from backend.app.services.node_type_prompt_service import get_node_type_prompt_service
        return get_node_type_prompt_service()
    except Exception as e:
        logger.error(f"获取节点模板服务失败: {str(e)}")
        return None

def _extract_node_data(root, file_name):
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

def _create_mock_embedding(node_data, id):
    """创建模拟的嵌入记录对象"""
    # 创建一个具有必要属性的对象
    class MockEmbedding:
        def __init__(self, id, json_data, score=0.0):
            self.id = id
            self.json_data = json_data
            self.score = score
    
    return MockEmbedding(id, node_data)

async def search_nodes(
    query_text: str,
    threshold: float = search_config.DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = search_config.DEFAULT_SEARCH_LIMIT
) -> List[Dict[str, Any]]:
    """
    搜索节点数据库
    
    Args:
        query_text: 查询文本
        threshold: 相似度阈值（此处仅作占位符）
        limit: 返回结果数量限制
        
    Returns:
        搜索结果列表
    """
    try:
        logger.info(f"搜索节点: {query_text}")
        
        # 加载节点缓存
        node_cache = load_node_database()
        
        # 如果缓存为空，返回空列表
        if not node_cache:
            logger.warning("节点缓存为空，无法查找节点")
            return []
        
        # 从查询中提取关键词
        query_text_lower = query_text.lower()
        keywords = extract_keywords(query_text, min_length=search_config.NODE_KEYWORD_MIN_LENGTH)
        
        # 收集匹配的节点
        matches = []
        
        # 遍历节点缓存
        for file_name, node_info in node_cache.items():
            node_data = node_info["json_data"]
            
            # 将节点数据转换为文本
            node_text = normalize_json(node_data).lower()
            
            # 匹配检查
            matched = False
            
            # 完全匹配节点ID
            node_id = node_data.get("id", "").lower()
            if node_id and node_id in query_text_lower:
                matched = True
                
            # 匹配节点类型
            node_type = node_data.get("type", "").lower()
            if node_type and node_type in query_text_lower:
                matched = True
                
            # 关键词匹配
            if not matched:
                for keyword in keywords:
                    if keyword in node_text:
                        matched = True
                        break
            
            if matched:
                # 创建模拟的嵌入记录
                mock_embedding = _create_mock_embedding(node_data, len(matches) + 1)
                matches.append(mock_embedding)
        
        # 如果无法找到精确匹配，尝试宽松匹配
        if not matches:
            for file_name, node_info in node_cache.items():
                node_data = node_info["json_data"]
                
                # 忽略已匹配的节点
                if any(m.json_data.get("id") == node_data.get("id") for m in matches):
                    continue
                    
                # 将字段值连接起来
                field_values = " ".join(str(v) for v in node_data.get("fields", {}).values())
                
                # 检查是否有任何关键词匹配
                for keyword in keywords:
                    if len(keyword) >= search_config.NODE_KEYWORD_MIN_LENGTH and keyword in field_values.lower():
                        mock_embedding = _create_mock_embedding(node_data, len(matches) + 1)
                        matches.append(mock_embedding)
                        break
        
        # 随机打乱结果（代替相似度排序）
        random.shuffle(matches)
        
        # 返回限制数量的结果
        limited_matches = matches[:limit]
        logger.info(f"节点搜索找到 {len(limited_matches)} 个结果")
        
        # 格式化搜索结果
        return format_search_result(limited_matches)
    except Exception as e:
        logger.error(f"节点搜索失败: {str(e)}")
        return [] 