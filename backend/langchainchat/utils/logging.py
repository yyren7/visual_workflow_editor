import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging(name: str = "langchain_chat") -> logging.Logger:
    """
    配置LangChain模块的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    # 在函数内部导入以避免循环导入
    from langchainchat.config import settings
    
    # 获取日志级别
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
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
    
    # 创建文件处理器
    log_file = settings.langchain_log_file
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
    
    logger.info(f"日志已配置: 级别={settings.LOG_LEVEL}, 文件={log_file}")
    
    # 记录配置信息
    logger.info(f"LangChain模块配置: DeepSeek模型={settings.DEEPSEEK_MODEL}")
    logger.info(f"向量存储设置: 类型={settings.VECTOR_STORE_TYPE}, 路径={settings.VECTOR_STORE_PATH}")
    logger.info(f"记忆设置: 最大历史长度={settings.MAX_HISTORY_LENGTH}")
    
    # 配置LangChain的日志
    langchain_logger = logging.getLogger("langchain")
    langchain_logger.setLevel(log_level)
    langchain_logger.addHandler(console_handler)
    langchain_logger.addHandler(file_handler)
    
    # 配置LangChain调试日志
    if settings.LOG_LLM_CALLS:
        # 配置额外的调试文件处理器
        debug_log_file = Path(settings.LOG_DIR) / "langchain_debug.log"
        debug_file_handler = RotatingFileHandler(
            debug_log_file, 
            maxBytes=20*1024*1024,  # 20MB
            backupCount=10,
            encoding='utf-8'
        )
        debug_file_handler.setLevel(logging.DEBUG)
        debug_file_handler.setFormatter(formatter)
        
        langchain_debug_logger = logging.getLogger("langchain.api")
        langchain_debug_logger.setLevel(logging.DEBUG)
        langchain_debug_logger.addHandler(debug_file_handler)
    
    return logger

# 创建主日志记录器
logger = setup_logging() 