"""
AI提供商配置模块

管理不同AI服务提供商的配置，包括DeepSeek, Google AI等。
"""

import os

def get_env_bool(env_var_name: str, default: str = "0") -> bool:
    """从环境变量获取布尔值，'1' 被认为是 True。"""
    return os.getenv(env_var_name, default) == "1"

# AI提供商基础配置
_AI_CONFIG = {
    "USE_DEEPSEEK": get_env_bool("USE_DEEPSEEK", "1"),
    "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    "ACTIVE_LLM_PROVIDER": os.getenv("ACTIVE_LLM_PROVIDER", "deepseek").lower(),
    "DEFAULT_TEMPERATURE": float(os.getenv("DEFAULT_TEMPERATURE", 0.3)),
    "DEFAULT_MAX_TOKENS": int(os.getenv("DEFAULT_MAX_TOKENS", 1500)),
    "DEFAULT_CONTEXT_WINDOW": int(os.getenv("DEFAULT_CONTEXT_WINDOW", 1000)),
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

# --- 配置验证 --- (移到这里，避免多次打印)
def _validate_ai_config(config):
    print("--- 正在验证 AI 配置 ---")
    provider = config.get("ACTIVE_LLM_PROVIDER")
    if provider == 'deepseek':
        if not config.get("DEEPSEEK_API_KEY"):
            print("警告：ACTIVE_LLM_PROVIDER 设置为 'deepseek'，但 DEEPSEEK_API_KEY 未设置。")
    elif provider == 'gemini':
        if not config.get("GOOGLE_API_KEY"):
            print("警告：ACTIVE_LLM_PROVIDER 设置为 'gemini'，但 GOOGLE_API_KEY 未设置。")
    else:
        print(f"警告：不支持的 LLM 提供商 '{provider}'。请设置为 'deepseek' 或 'gemini'。")
    print("--- AI 配置验证结束 ---")

# 启动时验证一次
_validate_ai_config(_AI_CONFIG)

def get_ai_config():
    """获取当前的 AI 配置字典。"""
    # 可以在这里添加逻辑，例如根据需要重新加载配置
    return _AI_CONFIG

def get_ai_config_for_user():
    """获取用户可用的 AI 配置字典。"""
    # 这里可以根据需要添加更多的过滤逻辑
    return {k: v for k, v in AI_CONFIG.items() if k not in ["DEEPSEEK_API_KEY", "GOOGLE_API_KEY"]} 