## backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse # Not used directly in provided snippet, keep if used elsewhere
import sys
import os
import logging # Keep for getting logger instances
from pathlib import Path
# import logging.handlers # No longer directly used here
import time # 导入 time
import uuid # ADDED
import datetime # ADDED
from typing import Optional # ADDED
from fastapi import HTTPException # ADDED
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # ADDED
from backend.config import DB_CONFIG # ADDED - Assuming DB_CONFIG is here or accessible

# --- REMOVE OLD LangChain debug ---
# import langchain
# langchain.debug = True
# logger = logging.getLogger(__name__)
# logger.info("LangChain debug mode enabled.")
# --- END REMOVE ---

# 添加项目根目录到Python路径 (Keep this)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

# --- NEW: Import and call centralized logging configuration ---
from backend.logging_config import setup_app_logging
setup_app_logging() # Configure logging for the entire backend
# --- END NEW ---

# Get a logger instance for this module (backend.app.main)
# This logger will inherit configuration from the 'backend' logger setup in logging_config
logger = logging.getLogger(__name__)

# Imports for Checkpointer
from typing import Optional # ADDED
from fastapi import HTTPException, FastAPI as FastAPIInstance # MODIFIED: Added FastAPIInstance for app.state type hint if needed below
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver # ADDED
from backend.config import DB_CONFIG # ADDED - Assuming DB_CONFIG is here or accessible

# No longer need global CHECKPOINTER_INSTANCE if app.state is used consistently
# CHECKPOINTER_INSTANCE: Optional[AsyncPostgresSaver] = None

# 导入配置 (Keep this)
from backend.config.base import LOG_DIR # LOG_DIR is now primarily for reference if needed
from backend.config.app_config import APP_CONFIG

# 创建logs目录 (This is now handled by logging_config.py or base.py, can be removed or kept for explicitness if preferred)
# log_dir = Path(LOG_DIR)
# log_dir.mkdir(parents=True, exist_ok=True)

# --- REMOVE OLD分散的日志配置 ---
# # 为 app.main logger 创建格式化器
# app_main_formatter = logging.Formatter(
#     '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# # 配置 \'backend.app\' 命名空间下的日志记录器...
# backend_app_logger = logging.getLogger("backend.app")
# backend_app_logger.setLevel(logging.DEBUG)
# general_console_handler = logging.StreamHandler()
# general_console_handler.setFormatter(app_main_formatter)
# general_console_handler.setLevel(logging.DEBUG)
# backend_app_logger.addHandler(general_console_handler)
# backend_app_logger.propagate = False
# # 创建单独的DeepSeek日志记录器
# deepseek_logger = logging.getLogger("backend.deepseek")
# # ... (all old deepseek_logger, workflow_logger, app_main logger (__name__), sas_logger configurations) ...
# logger.propagate = False # 防止 app.main 日志被根记录器（如果将来配置了）重复处理
# # +++ BEGINN ADDITION FOR SAS LOGGER CONFIGURATION +++
# # ... (sas_logger configuration) ...
# # +++ END ADDITION FOR SAS LOGGER CONFIGURATION +++
# logger.info("日志系统已配置 (app.main)，将记录到 %s 和控制台", log_dir)
# --- END REMOVE OLD ---

logger.info("Logging system configured via backend.logging_config.py.") # New log message

# 检查是否使用最小模式 (Keep this section)
MINIMAL_MODE = os.environ.get("SKIP_COMPLEX_ROUTERS", "0") == "1"
if MINIMAL_MODE:
    logger.info("Using minimal mode, skipping some complex routers.")

# 确保 base 模块的 LOG_DIR 已经加载 (Keep for verification if needed)
logger.info(f"LOG_DIR from config: {LOG_DIR}")

logger.info("Importing modules...") # Keep

# 首先导入数据库模型 (Keep this section)
try:
    from database.connection import Base
    logger.info("Successfully imported database.connection.Base")
    from database.models import User, Flow, FlowVariable, VersionInfo, Chat
    logger.info("Successfully imported database.models")
    from backend.config import APP_CONFIG # Keep, though imported earlier too
    logger.info("Successfully imported backend.config.APP_CONFIG")
    from backend.app.routers import (
        user, flow, email, auth, node_templates,
        flow_variables, chat, langgraph_chat, sas_chat
    )
    logger.info("Successfully imported basic routers.")
    if not MINIMAL_MODE:
        try:
            # from backend.app.routers import workflow_router # Example, keep if used
            logger.info("Successfully imported workflow_router (if applicable).")
        except ImportError as e:
            logger.error(f"Failed to import workflow_router: {e}")
    from backend.app.utils import get_version, get_version_info
    logger.info("Successfully imported backend.app.utils.")
    from backend.app.dependencies import get_node_template_service
    logger.info("Successfully imported backend.app.dependencies.")
except Exception as e:
    logger.error(f"Error during module imports: {e}", exc_info=True)
    raise

# --- 新增：导入 Pydantic 模型和依赖 --- (Keep if relevant)
from backend.langgraphchat.memory.db_chat_memory import DbChatMemory
from backend.app.services.chat_service import ChatService

# --- 新增：解析 Pydantic 前向引用 --- (Keep if relevant)
try:
    logger.info("Rebuilding Pydantic models to resolve forward references...")
    DbChatMemory.model_rebuild()
    # ChatService.model_rebuild() # If needed
    logger.info("Pydantic models rebuilt successfully.")
except Exception as e:
    logger.error(f"Error rebuilding Pydantic models: {e}", exc_info=True)

logger.info("Initializing FastAPI application...") # Keep
# Initialize FastAPI app (Keep this section)
app = FastAPI(
    title=APP_CONFIG['PROJECT_NAME'],
    version=get_version(),
)

# 添加这个中间件来记录所有请求 (Modify to use a specific logger)
@app.middleware("http")
async def log_requests_detailed(request: Request, call_next):
    # Get a specific logger for HTTP requests, it will inherit from 'backend.app' -> 'backend'
    http_logger = logging.getLogger("backend.app.http_requests") # Specific logger for http requests
    
    # client_host = request.client.host if request.client else "Unknown" # Covered by logger format
    http_logger.info(f"REQUEST: {request.method} {request.url.path} from {request.client.host if request.client else 'Unknown Client'}")
    # For more detail, use DEBUG level:
    # http_logger.debug(f"Headers: {dict(request.headers)}")

    start_time = time.time()
    try:
        response = await call_next(request) # 调用后续处理或路由
        process_time = time.time() - start_time
        http_logger.info(f"RESPONSE: {request.method} {request.url.path} - STATUS {response.status_code} (took: {process_time:.4f}s)")
        # http_logger.debug(f"Response Headers: {dict(response.headers)}")
    except Exception as e:
        process_time = time.time() - start_time
        # Log error with exception info
        http_logger.error(f"ERROR: {request.method} {request.url.path} - Exception {type(e).__name__} (took: {process_time:.4f}s)", exc_info=True)
        raise e from None # Re-raise to let FastAPI handle it
    return response

# CORS configuration (Keep this section)
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CONFIG['CORS_ORIGINS'],
    allow_credentials=APP_CONFIG.get('CORS_CREDENTIALS', True),
    allow_methods=APP_CONFIG.get('CORS_METHODS', ["*"]),
    allow_headers=APP_CONFIG.get('CORS_HEADERS', ["*"]),
    expose_headers=["*"],
)

logger.info("Registering routers...") # Keep
# Include routers (Keep this section)
try:
    app.include_router(user.router)
    logger.info("Registered user router.")
    app.include_router(flow.router)
    logger.info("Registered flow router.")
    app.include_router(email.router)
    logger.info("Registered email router.")
    app.include_router(auth.router)
    logger.info("Registered auth router.")
    app.include_router(node_templates.router)
    logger.info("Registered node_templates router.")
    
    if not MINIMAL_MODE:
        try:
            # app.include_router(workflow_router.router) # Example
            logger.info("Registered workflow router (if applicable).")
        except Exception as e:
            logger.error(f"Failed to register workflow router: {e}")
    else:
        logger.info("Skipped registering workflow router (minimal mode).")

    app.include_router(flow_variables.router)
    logger.info("Registered flow_variables router.")
    app.include_router(chat.router)
    logger.info("Registered chat router.")
    app.include_router(langgraph_chat.router)
    logger.info("Registered langgraph_chat router.")
    app.include_router(sas_chat.router)
    logger.info("Registered sas_chat router.")
except Exception as e:
    logger.error(f"Error registering routers: {e}", exc_info=True)
    raise

logger.info("FastAPI application initialization complete. Ready for requests...") # Keep

@app.on_event("startup") # Keep this section
async def startup_event():
    log_id = str(uuid.uuid4())
    current_time = datetime.datetime.now().isoformat()
    # Use the main app logger or a specific startup logger
    startup_logger = logging.getLogger("backend.app.startup_event")
    startup_logger.info(f"🚀 STARTUP EVENT 1 (startup_event) CALLED - ID: {log_id} at {current_time}")
    template_service = get_node_template_service()
    startup_logger.info(f"Node templates loaded by startup_event (ID: {log_id}).")

@app.on_event("startup")
async def initialize_checkpointer():
    """
    Initializes the LangGraph AsyncPostgresSaver checkpointer instance at application startup
    and stores both the context manager and the instance in app.state.
    """
    checkpointer_logger = logging.getLogger("backend.app.checkpointer_init")
    app.state.saver_context_manager = None  # Initialize to None
    app.state.checkpointer_instance = None  # Initialize to None
    try:
        db_url = DB_CONFIG.get('DATABASE_URL')
        # Log the actual DB_URL being used
        checkpointer_logger.info(f"Attempting to initialize checkpointer with DATABASE_URL: {db_url}")
        if db_url:
            # Convert SQLAlchemy format to standard PostgreSQL format for AsyncPostgresSaver
            # Remove the "+psycopg2" dialect from the URL
            if db_url.startswith('postgresql+psycopg2://'):
                db_url_for_checkpointer = db_url.replace('postgresql+psycopg2://', 'postgresql://')
                checkpointer_logger.info(f"Converted URL for AsyncPostgresSaver: {db_url_for_checkpointer}")
            else:
                db_url_for_checkpointer = db_url
            
            # Get the async context manager
            app.state.saver_context_manager = AsyncPostgresSaver.from_conn_string(db_url_for_checkpointer)
            # Enter the context manager to get the actual instance
            app.state.checkpointer_instance = await app.state.saver_context_manager.__aenter__()
            # Now call setup on the actual instance
            await app.state.checkpointer_instance.setup()
            checkpointer_logger.info("Successfully initialized AsyncPostgresSaver (checkpointer) and stored in app.state.")
        else:
            checkpointer_logger.error("DATABASE_URL not found in DB_CONFIG. Checkpointer cannot be initialized.")
    except Exception as e:
        checkpointer_logger.error(f"Error initializing AsyncPostgresSaver (checkpointer): {e}", exc_info=True)
        # If initialization failed, ensure instance is None so get_checkpointer dependency fails cleanly
        app.state.checkpointer_instance = None 
        if app.state.saver_context_manager: # If context manager was created but enter/setup failed
            try:
                # Attempt to clean up the context manager if __aenter__ was called or partially succeeded
                # This might not be strictly necessary if __aenter__ itself failed, but good for robustness
                await app.state.saver_context_manager.__aexit__(type(e), e, e.__traceback__)
            except Exception as exit_e:
                checkpointer_logger.error(f"Error during __aexit__ in checkpointer initialization failure: {exit_e}", exc_info=True)
            app.state.saver_context_manager = None # Ensure it's None after failed attempt

@app.on_event("shutdown")
async def shutdown_checkpointer():
    """
    Cleans up the LangGraph checkpointer resources on application shutdown.
    """
    shutdown_logger = logging.getLogger("backend.app.checkpointer_shutdown")
    if hasattr(app.state, 'saver_context_manager') and app.state.saver_context_manager is not None:
        shutdown_logger.info("Shutting down AsyncPostgresSaver (checkpointer)...")
        try:
            # Call __aexit__ on the stored context manager
            # Pass None, None, None for a clean exit
            await app.state.saver_context_manager.__aexit__(None, None, None)
            shutdown_logger.info("AsyncPostgresSaver (checkpointer) shutdown successfully.")
        except Exception as e:
            shutdown_logger.error(f"Error during AsyncPostgresSaver (checkpointer) shutdown: {e}", exc_info=True)
        finally:
            app.state.saver_context_manager = None
            app.state.checkpointer_instance = None
    else:
        shutdown_logger.info("AsyncPostgresSaver (checkpointer) context manager not found in app.state, skipping shutdown.")

@app.get("/") # Keep this section
async def root():
    return {"message": "Flow Editor API"}

@app.get("/version") # 移除 /api 前缀
async def version(request: Request):
    version_logger = logging.getLogger("backend.app.version_endpoint")
    origin = request.headers.get("origin", "Unknown Origin")
    # version_logger.info(f"Version request received from: {origin}") # Example of logging
    version_data = get_version_info()
    # version_logger.info(f"Returning version info: {version_data}") # Example of logging
    return version_data

@app.on_event("startup") # Keep this section (ensure it's distinct if multiple startup events)
async def validate_api_configuration():
    log_id = str(uuid.uuid4())
    current_time = datetime.datetime.now().isoformat()
    config_validation_logger = logging.getLogger("backend.app.config_validation")
    config_validation_logger.info(f"🚀 STARTUP EVENT 2 (validate_api_configuration) CALLED - ID: {log_id} at {current_time}")
    
    from backend.config import APP_CONFIG as app_cfg, AI_CONFIG, DB_CONFIG # Renamed to avoid conflict
    
    if AI_CONFIG.get('USE_DEEPSEEK', False): # Use .get for safety
        config_validation_logger.info("Validating DeepSeek API configuration...")
        api_key = AI_CONFIG.get('DEEPSEEK_API_KEY')
        invalid_key = not api_key or api_key == "your_deepseek_api_key_here" or api_key.startswith("sk-if-you-see-this")
        
        if invalid_key:
            config_validation_logger.warning("⚠️ No valid DeepSeek API key set. Please set DEEPSEEK_API_KEY environment variable.")
        else:
            config_validation_logger.info(f"✓ DeepSeek API key is set (ends with: ...{api_key[-4:] if api_key else 'N/A'}).") # Masked
            
        base_url = AI_CONFIG.get('DEEPSEEK_BASE_URL', '').rstrip('/')
        config_validation_logger.info(f"DeepSeek API Base URL: {base_url}")
        
        if '/v1/' in base_url or base_url.endswith('/v1'):
            config_validation_logger.warning(f"⚠️ Base URL contains /v1: {base_url}. This might cause duplicate paths as code often adds /v1/chat/completions.")
            
        config_validation_logger.info(f"DeepSeek Model: {AI_CONFIG.get('DEEPSEEK_MODEL')}")
        
        try:
            from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM # Verify import
            config_validation_logger.info("✓ DeepSeekLLM client module imported successfully.")
        except Exception as e:
            config_validation_logger.error(f"⚠️ Failed to import or validate DeepSeekLLM client module: {str(e)}", exc_info=True)
    
    db_url = DB_CONFIG.get('DATABASE_URL')
    config_validation_logger.info(f"Database URL: {'Set' if db_url else 'Not Set (Using default or in-memory if applicable)'}") # Simplified
    
    if app_cfg.get('DEBUG', False): # Use .get for safety
        config_validation_logger.info("⚠️ Debug mode is ENABLED.")
    else:
        config_validation_logger.info("✓ Debug mode is DISABLED.")
        
    config_validation_logger.info(f"API Prefix: {app_cfg.get('API_PREFIX')}")
    config_validation_logger.info(f"CORS Allowed Origins: {', '.join(app_cfg.get('CORS_ORIGINS', []))}")

# Ensure all logger calls like print() are replaced with logger.info(), logger.debug() etc.
# For example, in /api/version, print() statements should be logger calls.
