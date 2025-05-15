import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Import specific config objects and base variables needed
from backend.config import LANGCHAIN_CONFIG, LOG_DIR

def setup_logging(name: str = "backend.langgraphchat") -> logging.Logger:
    """
    配置LangChain模块的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    # Removed incorrect import from inside the function
    # from langgraphchat.config import settings
    
    # 获取日志级别 using LANGCHAIN_CONFIG
    log_level_str = LANGCHAIN_CONFIG.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 防止日志记录重复
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # 创建文件处理器 using LANGCHAIN_CONFIG
    log_file = LANGCHAIN_CONFIG.get("LANGCHAIN_LOG_FILE")
    if not log_file:
        logger.warning("LANGCHAIN_LOG_FILE not found in config, logging to console only.")
        logger.addHandler(console_handler)
        return logger
    
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    logger.info(f"日志已配置: 级别={log_level_str}, 文件={log_file}")
    
    # 记录配置信息 (Accessing LANGCHAIN_CONFIG)
    # Example: logger.info(f"DeepSeek Model: {LANGCHAIN_CONFIG.get('CHAT_MODEL_NAME')}")
    # Example: logger.info(f"Vector Store Path: {LANGCHAIN_CONFIG.get('VECTOR_STORE_PATH')}")
    # Example: logger.info(f"Max History Length: {LANGCHAIN_CONFIG.get('MAX_HISTORY_LENGTH')}")
    
    # 配置LangChain的日志
    langchain_logger = logging.getLogger("langchain")
    langchain_logger.setLevel(log_level)
    langchain_logger.addHandler(console_handler)
    langchain_logger.addHandler(file_handler)
    
    # 配置LangChain调试日志 using LANGCHAIN_CONFIG and LOG_DIR
    if LANGCHAIN_CONFIG.get("LOG_LLM_CALLS", False):
        debug_log_file = Path(LOG_DIR) / "langchain_debug.log"
        debug_file_handler = RotatingFileHandler(
            debug_log_file, 
            maxBytes=20*1024*1024,  # 20MB
            backupCount=10,
            encoding='utf-8'
        )
        debug_file_handler.setLevel(logging.DEBUG)
        debug_file_handler.setFormatter(formatter)
        
        # Log calls specifically from langchain.api or potentially others
        langchain_api_logger = logging.getLogger("langchain.api") # Or adjust logger name if needed
        langchain_api_logger.setLevel(logging.DEBUG)
        langchain_api_logger.addHandler(debug_file_handler)
        logger.info(f"Langchain debug logging enabled, writing to {debug_log_file}")
    
    return logger

# 创建主日志记录器
logger = setup_logging() 