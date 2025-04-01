"""
嵌入向量工具函数
"""

import json
import numpy as np
from typing import Dict, Any, List

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

def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量之间的余弦相似度
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        
    Returns:
        余弦相似度值
    """
    # 转换为numpy数组
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    # 计算点积
    dot_product = np.dot(vec1_np, vec2_np)
    
    # 计算L2范数
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    # 避免除零错误
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    # 计算余弦相似度
    return dot_product / (norm1 * norm2) 