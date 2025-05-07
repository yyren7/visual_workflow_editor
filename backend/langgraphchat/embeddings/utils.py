"""
搜索工具函数
"""

import logging
import json
from typing import Dict, Any, List

# 设置logger
logger = logging.getLogger(__name__)

def normalize_json(json_data: Dict[str, Any]) -> str:
    """
    将JSON数据标准化为字符串表示
    
    Args:
        json_data: 要标准化的JSON数据
        
    Returns:
        标准化后的字符串
    """
    # 确保字典被排序并美化输出
    return json.dumps(json_data, sort_keys=True, indent=2, ensure_ascii=False)

def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """
    从文本中提取关键词
    
    Args:
        text: 源文本
        min_length: 最小关键词长度
        
    Returns:
        关键词列表
    """
    # 简单实现：分词并过滤
    # 实际应用中可以使用更复杂的关键词提取算法
    words = text.lower().split()
    return [word for word in words if len(word) >= min_length]

def format_search_result(items: List[Any], with_score: bool = False) -> List[Dict[str, Any]]:
    """
    格式化搜索结果
    
    Args:
        items: 搜索结果项
        with_score: 是否包含分数
        
    Returns:
        格式化后的结果列表
    """
    results = []
    
    for item in items:
        if hasattr(item, 'json_data'):
            result = {
                'id': getattr(item, 'id', None),
                'data': item.json_data
            }
            
            if with_score and hasattr(item, 'score'):
                result['score'] = item.score
                
            results.append(result)
    
    return results 