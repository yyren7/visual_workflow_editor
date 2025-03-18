import json
from typing import Any, Dict, List
import numpy as np

def normalize_json(data: Dict[str, Any]) -> str:
    """
    将JSON数据标准化为字符串形式
    这对于确保相同的JSON数据（即使键的顺序不同）产生相同的embedding很重要
    """
    return json.dumps(data, sort_keys=True)

def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量之间的余弦相似度
    """
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    return dot_product / (norm1 * norm2)

def flatten_json(data: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
    """
    将嵌套的JSON结构展平为单层结构
    这对于某些embedding模型可能很有用
    """
    items: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            items.update(flatten_json(value, new_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    items.update(flatten_json(item, f"{new_key}.{i}"))
                else:
                    items[f"{new_key}.{i}"] = str(item)
        else:
            items[new_key] = str(value)
            
    return items 