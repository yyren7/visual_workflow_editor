"""
LMStudio API客户端
用于调用外部嵌入模型
"""

import requests
import logging
from typing import List, Optional

# 设置logger
logger = logging.getLogger(__name__)

class LMStudioClient:
    """LMStudio API客户端，用于调用外部嵌入模型"""
    
    def __init__(self, api_base_url: str, api_key: Optional[str] = None):
        """
        初始化LMStudio客户端
        
        Args:
            api_base_url: LMStudio API的基础URL，例如: "http://localhost:1234/v1"
            api_key: API密钥（如果需要）
        """
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        
        # 如果提供了API密钥，添加到headers中
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
            
        logger.info(f"初始化LMStudio客户端，API基础URL: {api_base_url}")
    
    def create_embedding(self, text: str) -> List[float]:
        """
        调用LMStudio API创建文本的嵌入向量
        
        Args:
            text: 要进行嵌入的文本
            
        Returns:
            嵌入向量（浮点数列表）
        """
        try:
            # 构建API请求URL
            url = f"{self.api_base_url}/embeddings"
            
            # 构建请求数据
            payload = {
                "input": text,
                "model": "embedding"  # 可能需要根据LMStudio的实际配置调整
            }
            
            # 发送POST请求
            response = requests.post(url, headers=self.headers, json=payload)
            
            # 检查响应状态
            if response.status_code == 200:
                # 解析响应JSON
                result = response.json()
                
                # 根据OpenAI API格式提取嵌入向量
                # 注意：此处假设LMStudio返回与OpenAI兼容的格式
                # 可能需要根据实际情况调整
                if "data" in result and len(result["data"]) > 0:
                    embedding = result["data"][0]["embedding"]
                    return embedding
                else:
                    logger.error(f"无法从LMStudio响应中提取嵌入向量: {result}")
                    raise ValueError("无法从响应中提取嵌入向量")
            else:
                logger.error(f"LMStudio API请求失败: {response.status_code}, {response.text}")
                raise ValueError(f"API请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"调用LMStudio API创建嵌入向量时出错: {str(e)}")
            raise
            
    def batch_create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量创建多个文本的嵌入向量
        
        Args:
            texts: 要进行嵌入的文本列表
            
        Returns:
            嵌入向量列表
        """
        try:
            # 构建API请求URL
            url = f"{self.api_base_url}/embeddings"
            
            # 构建请求数据
            payload = {
                "input": texts,
                "model": "embedding"  # 可能需要根据LMStudio的实际配置调整
            }
            
            # 发送POST请求
            response = requests.post(url, headers=self.headers, json=payload)
            
            # 检查响应状态
            if response.status_code == 200:
                # 解析响应JSON
                result = response.json()
                
                # 提取所有嵌入向量
                if "data" in result and len(result["data"]) > 0:
                    embeddings = [item["embedding"] for item in result["data"]]
                    return embeddings
                else:
                    logger.error(f"无法从LMStudio响应中提取嵌入向量: {result}")
                    raise ValueError("无法从响应中提取嵌入向量")
            else:
                logger.error(f"LMStudio API批量请求失败: {response.status_code}, {response.text}")
                raise ValueError(f"API批量请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"批量调用LMStudio API创建嵌入向量时出错: {str(e)}")
            raise 