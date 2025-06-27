# backend/logging_config.py
import logging
import logging.handlers
import sys
import os
from pathlib import Path

# BASE_DIR should point to the workspace root.
# If logging_config.py is in backend/, then __file__ is backend/logging_config.py.
# .parent is backend/, .parent.parent is the workspace root.
BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure backend.config can be found. This assumes /workspace is in sys.path,
# which run_backend.py should handle.
from backend.config.base import (
    DEFAULT_LOG_LEVEL,
    LOG_DIR, 
    BACKEND_LOG_FILE,
    DEEPSEEK_LOG_FILE,
    LANGGRAPHCHAT_DEBUG_LOG_FILE,
)
from backend.config import LANGCHAIN_CONFIG

def setup_app_logging():
    """
    配置整个后端应用的日志系统。
    """
    logger_this_module = logging.getLogger(__name__) # For messages from this setup function

    general_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(process)d-%(thread)d - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    backend_logger = logging.getLogger("backend")
    effective_log_level_str = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    log_level_int = getattr(logging, effective_log_level_str, logging.INFO)

    # Handle Uvicorn reload: if handlers exist, just update levels.
    if backend_logger.handlers:
        logger_this_module.info(f"Backend logger already configured. Current level: {logging.getLevelName(backend_logger.getEffectiveLevel())}.")
        if backend_logger.getEffectiveLevel() != log_level_int:
            backend_logger.setLevel(log_level_int)
            logger_this_module.info(f"Backend logger level updated to: {effective_log_level_str}.")
        
        handlers_level_updated = False
        for handler in backend_logger.handlers:
            if handler.level != log_level_int:
                handler.setLevel(log_level_int)
                handlers_level_updated = True
        if handlers_level_updated:
            logger_this_module.info(f"Backend logger handlers' levels also updated to: {effective_log_level_str}.")
        # return # No need to return if just updating levels, let specific handlers below also check.

    else: # First time setup for backend_logger
        backend_logger.setLevel(log_level_int)
        backend_logger.propagate = False 

        backend_console_handler = logging.StreamHandler(sys.stdout)
        backend_console_handler.setFormatter(general_formatter)
        backend_console_handler.setLevel(log_level_int)
        backend_logger.addHandler(backend_console_handler)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        backend_file_handler = logging.handlers.RotatingFileHandler(
            BACKEND_LOG_FILE, maxBytes=20 * 1024 * 1024, backupCount=5, encoding='utf-8'
        )
        backend_file_handler.setFormatter(general_formatter)
        backend_file_handler.setLevel(log_level_int)
        backend_logger.addHandler(backend_file_handler)
        logger_this_module.info("Backend logger configured with console and file handlers.")

    # Configure 'backend.deepseek' logger
    deepseek_logger = logging.getLogger("backend.deepseek")
    deepseek_logger.setLevel(logging.DEBUG) # Specific level for deepseek if needed, otherwise inherits from 'backend'
    
    # Ensure LOG_DIR exists for deepseek log file
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    deepseek_specific_file_handler = logging.handlers.RotatingFileHandler(
        DEEPSEEK_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    deepseek_specific_file_handler.setFormatter(general_formatter)
    deepseek_specific_file_handler.setLevel(logging.DEBUG) # Handler level for deepseek
    
    # Add handler only if a similar one isn't already present
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) and h.baseFilename == str(DEEPSEEK_LOG_FILE) for h in deepseek_logger.handlers):
        deepseek_logger.addHandler(deepseek_specific_file_handler)
        logger_this_module.info(f"Deepseek logger configured with file handler: {DEEPSEEK_LOG_FILE}")
    # deepseek_logger.propagate = False # Optional: if deepseek logs should ONLY go to its file

    # Configure 'langchain' logger for LLM calls
    if LANGCHAIN_CONFIG.get("LOG_LLM_CALLS", False):
        langchain_llm_logger = logging.getLogger("langchain") # Or a more specific "langchain.llms"
        langchain_llm_logger.setLevel(logging.DEBUG) # Ensure DEBUG for LLM calls
        
        # Ensure LOG_DIR exists for langchain debug log file
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        langchain_debug_file_handler = logging.handlers.RotatingFileHandler(
            LANGGRAPHCHAT_DEBUG_LOG_FILE, maxBytes=20 * 1024 * 1024, backupCount=10, encoding='utf-8'
        )
        langchain_debug_file_handler.setFormatter(general_formatter)
        langchain_debug_file_handler.setLevel(logging.DEBUG)

        if not any(isinstance(h, logging.handlers.RotatingFileHandler) and h.baseFilename == str(LANGGRAPHCHAT_DEBUG_LOG_FILE) for h in langchain_llm_logger.handlers):
            langchain_llm_logger.addHandler(langchain_debug_file_handler)
            logger_this_module.info(f"Langchain LLM call logger configured with file handler: {LANGGRAPHCHAT_DEBUG_LOG_FILE}")
        # langchain_llm_logger.propagate = False # Optional

    # Uvicorn loggers
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(uvicorn_logger_name)
        # If Uvicorn's default handlers are fine, just ensure level.
        # If we want them to use our handlers, we'd clear theirs and add ours.
        # For now, just align level and let them use their own handlers if they add them.
        if not uvicorn_logger.handlers: # If uvicorn didn't add any, they might propagate
             pass # Or add our handlers: uvicorn_logger.addHandler(backend_console_handler) etc.
        uvicorn_logger.setLevel(log_level_int) 

    logger_this_module.info(
        f"Logging setup complete. Effective level for 'backend': {effective_log_level_str}. Main Log File: {BACKEND_LOG_FILE}"
    ) 