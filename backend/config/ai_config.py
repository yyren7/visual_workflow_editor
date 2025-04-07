"""
AI提供商配置模块

管理不同AI服务提供商的配置，包括DeepSeek, Google AI等。
"""

import os
from .base import get_env_bool

# AI提供商基础配置
_AI_CONFIG = {
    "USE_DEEPSEEK": get_env_bool("USE_DEEPSEEK", "1"),
    "USE_GOOGLE_AI": get_env_bool("USE_GOOGLE_AI", "0"),
    "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
    "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", "")
}

# 计算LLM API设置函数
def get_llm_api_url(_ai_config=None):
    if _ai_config is None:
        _ai_config = _AI_CONFIG
    
    if _ai_config["USE_DEEPSEEK"]:
        return _ai_config["DEEPSEEK_BASE_URL"]
    return os.getenv("LLM_API_URL", "http://localhost:8001")

def get_llm_api_key(_ai_config=None):
    if _ai_config is None:
        _ai_config = _AI_CONFIG
        
    if _ai_config["USE_DEEPSEEK"]:
        return _ai_config["DEEPSEEK_API_KEY"]
    if _ai_config["USE_GOOGLE_AI"]:
        return _ai_config["GOOGLE_API_KEY"]
    return os.getenv("LLM_API_KEY", "your_llm_api_key")

def get_llm_model(_ai_config=None):
    if _ai_config is None:
        _ai_config = _AI_CONFIG
        
    if _ai_config["USE_DEEPSEEK"]:
        return _ai_config["DEEPSEEK_MODEL"]
    return os.getenv("LLM_MODEL", "")

# 导出带有计算字段的完整配置
AI_CONFIG = _AI_CONFIG.copy()
AI_CONFIG.update({
    "LLM_API_URL": get_llm_api_url(_AI_CONFIG),
    "LLM_API_KEY": get_llm_api_key(_AI_CONFIG),
    "LLM_MODEL": get_llm_model(_AI_CONFIG)
}) 